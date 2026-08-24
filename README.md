# SENTINEL 2.0 — Evidence-Grounded Fraud Intelligence

SENTINEL is an AI fraud-investigation backend built on one principle:

> **Treat the LLM as an unreliable component inside a reliable system.**

Citizens submit suspicious messages; analysts map fraud networks. Every
conclusion the system returns carries citations, calibrated confidence, a
per-stage cost/latency audit trail, and a deterministic policy gate that —
not the model — decides when intelligence is emitted or a citizen alert
fires.

## What makes this different from an "LLM demo"

| Concern | Mechanism | Verified by |
|---|---|---|
| Untrusted input control-flow | Quarantined extraction: raw text only reaches reasoning through a schema-validated boundary; prompts carry explicit data-not-directions containment | `tests/test_adversarial.py` |
| Hallucinated verdicts | Numbered evidence block (retrieved patterns + extracted claims) with required integer citations | `pipeline.py::_privileged_verdict` |
| Model self-dealing | Verification sampling on uncertain verdicts only (selective), bounded confidence penalty | benchmark ablation below |
| Fabricated safety advice | Citizen alerts are 100% template-selected; model text can never reach them (regression-tested after an adversarial test caught exactly this leak) | `alerts.py`, adversarial suite |
| Silent wrong output | Deterministic emission policy: HIGH/CRITICAL + agreement thresholds decide event emission | `pipeline.py::_policy_gate` |
| Provider failure | Retries w/ backoff → budget guard → conservative rules-only degraded result, honestly flagged | live: rate-limit mid-demo produced clean degraded response |
| Unmeasured claims | Benchmark harness over real (UCI SMS) + documented synthetic data, checkpointed JSONL results | `evals/` |

## Benchmark (live Groq run, 62 cases: UCI-SMS n=24 stratified + synthetic Indian typology + adversarial)

| variant | acc | precision | recall | F1 | FPR | ECE | p95 ms | cost/run |
|---|---|---|---|---|---|---|---|---|
| rules_only | 0.532 | 0.833 | 0.151 | 0.256 | **0.035** | 0.252 | ~0 | $0 |
| single_prompt (gpt-oss-120b) | **0.919** | 0.967 | 0.879 | **0.921** | 0.035 | 0.424 | 812 | $0.0066 |
| hybrid_noverify | 0.790 | **1.000** | 0.606 | 0.755 | **0.000** | **0.227** | 5625 | $0.0177 |
| hybrid_full (selective verification) | 0.758 | 0.950 | 0.576 | 0.717 | 0.035 | 0.242 | 8343 | $0.0144 |

**Honest reading of these numbers:**

1. A single strong-model call is the best *classifier* on out-of-domain SMS spam.
2. The pipeline earns its complexity elsewhere: zero false positives at
   threshold (citizens never falsely alarmed), calibrated scores (ECE
   0.23 vs 0.42), entity extraction for cross-module correlation, and an
   audit trail the raw call cannot provide.
3. Unconditional verification sampling **hurt** (recall 0.394, p95 17s in
   ablation). The shipped design verifies selectively and bounds the
   penalty — measured, not assumed.
4. Rules alone are weak but free; they route ~30% of traffic away from any
   API call.

Reproduce: `cd sentinel && python -m evals.run_benchmark --backend groq --datasets uci_sms synthetic adversarial --sample 24` (checkpoints in `evals/results/`, dataset cards in `evals/data/DATASET_CARD.md`).

## Architecture

```
INPUT ─▶ ingest(redact·digest·case) ─▶ prescreen(rules→route)
     RULES_ONLY ────────────────┐
     FAST/STRONG                ▼
   quarantined extraction (schema-validated facts, no tools)
        ▼
   evidence retrieval (ChromaDB kNN over prior confirmed patterns)
        ▼
   privileged verdict (citations required, prescreen hidden)
        ▼
   selective verification (K samples, label-consistency)
        ▼
   policy gate (deterministic emit/escalate decision)
        ▼
   persist(case·entities·event·trace) ─▶ API / Streamlit client
```

Modules: **SCAMWatch** (message triage), **FRAUDGraph** (entity networks,
ring detection via connected components + betweenness hubs, cross-module
correlation through normalized shared entities), **CURRENCYGuard**
(honest heuristic screener with explicit INCONCLUSIVE abstention),
**Analytics v2** (timestamp-derived stats/timeline/correlations).

## Run it

```bash
cd sentinel
python -m venv venv && venv/Scripts/pip install -r requirements.txt   # Windows
cp .env.example .env            # set GROQ_API_KEY
uvicorn backend.main:app --reload          # http://localhost:8000/docs
streamlit run frontend/app.py              # minimal investigation client
pytest                                     # 81 tests, no network needed
```

Models default to `openai/gpt-oss-120b` (strong) / `openai/gpt-oss-20b`
(fast); override via env. SQLite by default; set `DATABASE_URL` to Postgres
for deployment (`app_env=production` requires API keys and rejects SQLite).

## API surface

`POST /api/scamwatch/analyze` · `GET /api/scamwatch/cases/{id}` ·
`POST /api/scamwatch/alert/{id}` · `POST /api/fraudgraph/analyze` ·
`GET /api/fraudgraph/export/{id}` (ZIP evidence kit) ·
`POST /api/currencyguard/screen` · `GET /api/analytics/stats|recent|timeline|correlations`

Every response: typed Pydantic models, request-ID header, per-stage usage
(model, tokens, latency, est. cost). Auth via `X-API-Key` when configured;
rate limiting per identity.

## Docs

- [Threat model](docs/threat_model.md)
- [ADRs](docs/adr/) — model layer, storage, verification design, module surgery
- [Dataset cards](sentinel/evals/data/DATASET_CARD.md)

## Known limitations

- UCI SMS is out-of-domain for Indian multichannel fraud; synthetic set has
  authoring bias toward the rule library. No claim of field performance.
- Verification sampling measures fast-model consistency, not ground truth
  (no NLI entailment clustering yet).
- Rate limiter is per-process; multi-node needs a shared store.
- Voice/deepfake detection: not implemented, no placeholders pretending otherwise.

## Status

81 tests green (no-network CI path) · live Groq smoke-tested end-to-end ·
benchmark checkpointed & reproducible.
