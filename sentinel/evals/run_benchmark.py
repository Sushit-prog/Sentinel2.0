"""Benchmark runner.

Usage (from sentinel/):
  python -m evals.run_benchmark --backend fake --datasets synthetic
  python -m evals.run_benchmark --backend groq --datasets uci_sms \
      --sample 60 --variants rules_only single_prompt hybrid_full

groq backend performs real API calls; results checkpoint to evals/results/
as JSONL so interrupted runs resume. The fake backend verifies harness
plumbing deterministically and is what CI runs.
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_SENTINEL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_SENTINEL_ROOT))

RESULTS_DIR = Path(__file__).parent / "results"


def _bootstrap_env(backend: str) -> None:
    os.environ.setdefault("APP_ENV", "test")
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    # Fresh database per invocation: case-level replay caching would
    # otherwise short-circuit new measurements within 24h windows.
    db_path = (RESULTS_DIR / "eval.db").as_posix()
    for suffix in ("", "-wal", "-shm"):
        try:
            os.remove(db_path + suffix)
        except FileNotFoundError:
            pass
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    if backend == "fake":
        os.environ.setdefault("GROQ_API_KEY", "fake-key")
        return
    if not os.environ.get("GROQ_API_KEY"):
        env_path = _SENTINEL_ROOT / ".env"
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                if line.startswith("GROQ_API_KEY="):
                    raw = line.split("=", 1)[1].strip()
                    os.environ["GROQ_API_KEY"] = raw.strip('"').strip("'")
                    break


from backend.core.config import get_settings  # noqa: E402
from backend.core.llm import Route, get_llm_client, set_llm_client  # noqa: E402
from backend.core.llm.schemas import LLMResult, Usage  # noqa: E402


class HeuristicFakeLLM:
    """Deterministic pseudo-model so the full harness runs offline.

    Lexical heuristic - deliberately weak on UCI spam so calibration and
    error metrics exercise non-trivial values."""

    _SCAM_WORDS = ("win", "free", "otp", "kyc", "prize", "claim", "urgent")

    @staticmethod
    def _is_scam(text: str) -> bool:
        lowered = text.lower()
        return any(k in lowered for k in HeuristicFakeLLM._SCAM_WORDS)

    @staticmethod
    def _result(text_payload: str) -> LLMResult:
        usage = Usage(
            model="fake-bench",
            prompt_tokens=50,
            completion_tokens=20,
            latency_ms=30,
            est_cost_usd=0.000001,
        )
        return LLMResult(text=text_payload, usage=usage)

    def complete(
        self,
        user,
        *,
        system=None,
        route=Route.STRONG,
        temperature=0.1,
        max_tokens=1024,
        json_mode=False,
    ) -> LLMResult:
        is_scam = self._is_scam(user)
        payload = json.dumps(
            {"is_scam": bool(is_scam), "confidence": 0.85 if is_scam else 0.55}
        )
        return self._result(payload)

    def extract(
        self,
        schema,
        user,
        *,
        system=None,
        route=Route.STRONG,
        temperature=0.0,
        max_tokens=1024,
    ):
        name = schema.__name__
        if name == "ExtractedFacts":
            data = {
                "claims": [user[:200]],
                "phones": [],
                "accounts": [],
                "urgency_level": "high" if self._is_scam(user) else "none",
            }
        elif name == "Verdict":
            is_scam = self._is_scam(user)
            data = {
                "is_scam": is_scam,
                "scam_type": "fake_lottery" if is_scam else "legitimate",
                "confidence": 0.85 if is_scam else 0.7,
                "citations": [],
                "reasoning": "lexical fake",
                "recommended_action": "",
            }
        else:
            raise ValueError(f"HeuristicFakeLLM has no script for {name}")
        return schema.model_validate(data), self._result(json.dumps(data))


def _load_checkpoint(path: Path) -> dict[tuple[str, str], dict]:
    done: dict[tuple[str, str], dict] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
                done[(row["case_id"], row["variant"])] = row
            except (json.JSONDecodeError, KeyError):
                continue
    return done


def _dataset_tag(datasets: list[str], sample: int | None) -> str:
    tag = "_".join(sorted(datasets))
    return f"{tag}_n{sample}" if sample else tag


def _build_report(summary: dict[str, list[dict]]) -> dict:
    from evals.metrics import (
        brier_score,
        classification_metrics,
        expected_calibration_error,
        latency_percentiles,
    )

    report: dict = {"variants": {}, "by_dataset": {}}
    for variant, rows in summary.items():
        valid = [r for r in rows if "error" not in r]
        pairs = [(r["predicted"], r["label"]) for r in valid]
        scores = [r.get("score", 0.0) for r in valid]
        labels = [r["label"] for r in valid]
        entry = {
            **classification_metrics(pairs),
            "ece": expected_calibration_error(scores, labels),
            "brier": brier_score(scores, labels),
            "latency_ms": latency_percentiles([r.get("latency_ms", 0) for r in valid]),
            "total_cost_usd": round(sum(r.get("cost_usd", 0.0) for r in valid), 6),
            "degraded_count": sum(1 for r in valid if r.get("degraded")),
            "needs_review_count": sum(1 for r in valid if r.get("needs_review")),
            "error_count": len(rows) - len(valid),
        }
        report["variants"][variant] = entry
        groups: dict[str, list] = {}
        for r in valid:
            groups.setdefault(r["dataset"], []).append(r)
        report["by_dataset"][variant] = {
            ds: classification_metrics([(x["predicted"], x["label"]) for x in rs])
            for ds, rs in groups.items()
        }
    return report


def _print_table(report: dict) -> None:
    print(
        f"\n{'variant':<18}{'n':>5}{'acc':>7}{'prec':>7}{'rec':>7}{'f1':>7}"
        f"{'FPR':>7}{'ECE':>7}{'p95ms':>8}{'cost$':>9}"
    )
    for variant, m in report["variants"].items():
        print(
            f"{variant:<18}{m['n']:>5}{m['accuracy']:>7.3f}{m['precision']:>7.3f}"
            f"{m['recall']:>7.3f}{m['f1']:>7.3f}{m['fpr']:>7.3f}{m['ece']:>7.3f}"
            f"{m['latency_ms']['p95']:>8}{m['total_cost_usd']:>9.4f}"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", choices=["fake", "groq"], default="fake")
    parser.add_argument(
        "--datasets",
        nargs="+",
        default=["synthetic"],
        choices=["uci_sms", "synthetic", "adversarial"],
    )
    parser.add_argument(
        "--sample", type=int, default=None, help="stratified sample size for uci_sms"
    )
    parser.add_argument(
        "--variants",
        nargs="+",
        default=["rules_only", "single_prompt", "hybrid_noverify", "hybrid_full"],
    )
    parser.add_argument("--rpm", type=int, default=25)
    args = parser.parse_args()

    _bootstrap_env(args.backend)

    from backend.db.base import init_db, session_scope
    from evals import datasets as D
    from evals import variants as V

    settings = get_settings()
    if args.backend == "groq":
        settings.daily_token_budget = 10_000_000

    loaders = {
        "uci_sms": lambda: D.load_uci_sms(sample_size=args.sample),
        "synthetic": D.load_synthetic,
        "adversarial": D.load_adversarial,
    }

    init_db()

    all_cases: list = []
    for name in args.datasets:
        all_cases.extend(loaders[name]())
    print(
        f"[bench] cases={len(all_cases)} variants={args.variants} "
        f"backend={args.backend}"
    )

    if args.backend == "fake":
        set_llm_client(HeuristicFakeLLM())

    throttle_s = 0.0 if args.backend == "fake" else 60.0 / max(args.rpm, 1)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    summary: dict[str, list[dict]] = {}
    for variant in args.variants:
        runner = V.VARIANTS[variant]
        ckpt_path = RESULTS_DIR / (
            f"{args.backend}_{variant}_{_dataset_tag(args.datasets, args.sample)}.jsonl"
        )
        ckpt_path.parent.mkdir(parents=True, exist_ok=True)
        done = _load_checkpoint(ckpt_path)

        rows: list[dict] = []
        failures = 0
        with open(ckpt_path, "a", encoding="utf-8") as ckpt:
            for case in all_cases:
                key = (case.case_id, variant)
                if key in done:
                    rows.append(done[key])
                    continue
                if throttle_s:
                    time.sleep(throttle_s)
                try:
                    with session_scope() as session:
                        result = runner(case.text, session)
                    row = {
                        "case_id": case.case_id,
                        "dataset": case.dataset,
                        "label": case.label,
                        "variant": variant,
                        **result,
                        "ts": datetime.now(timezone.utc).isoformat(),
                    }
                except Exception as exc:
                    failures += 1
                    row = {
                        "case_id": case.case_id,
                        "dataset": case.dataset,
                        "label": case.label,
                        "variant": variant,
                        "error": str(exc)[:200],
                        "ts": datetime.now(timezone.utc).isoformat(),
                    }
                ckpt.write(json.dumps(row, ensure_ascii=False) + "\n")
                ckpt.flush()
                rows.append(row)
        summary[variant] = rows
        print(f"[bench] {variant}: {len(rows)} rows, {failures} failures")

    report = _build_report(summary)
    out_path = RESULTS_DIR / f"report_{args.backend}_{timestamp}.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"[bench] wrote {out_path}")
    _print_table(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
