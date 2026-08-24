"""Dataset loading for the evaluation harness.

Sources are documented in evals/data/DATASET_CARD.md. Labels:
1 = deceptive (spam/scam), 0 = benign.
"""

import csv
import random
from dataclasses import dataclass
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"


@dataclass(frozen=True)
class EvalCase:
    text: str
    label: int
    dataset: str
    case_id: str


def load_uci_sms(sample_size: int | None = None, seed: int = 42) -> list[EvalCase]:
    """UCI SMS Spam Collection (Almeida & Gomez Hidalgo, 2011), deduplicated.

    Domain-shift caveat: UK/Singapore SMS spam from ~2010, not Indian
    multichannel fraud. Used as an out-of-domain robustness check.
    """
    path = DATA_DIR / "raw" / "SMSSpamCollection"
    if not path.exists():
        raise FileNotFoundError(
            f"{path} missing - run evals/download_data.py or see DATASET_CARD.md"
        )
    cases = []
    with open(path, encoding="utf-8") as fh:
        for i, line in enumerate(fh):
            parts = line.rstrip("\n").split("\t", 1)
            if len(parts) != 2:
                continue
            label_str, text = parts
            if len(text.strip()) < 5:
                continue
            cases.append(
                EvalCase(
                    text=text[:4000],
                    label=1 if label_str == "spam" else 0,
                    dataset="uci_sms",
                    case_id=f"uci_{i}",
                )
            )
    if sample_size and sample_size < len(cases):
        positives = [c for c in cases if c.label == 1]
        negatives = [c for c in cases if c.label == 0]
        half = sample_size // 2
        rng = random.Random(seed)
        picked = rng.sample(positives, min(half, len(positives))) + rng.sample(
            negatives, min(sample_size - half, len(negatives))
        )
        rng.shuffle(picked)
        return picked
    return cases


def load_synthetic() -> list[EvalCase]:
    """Author-written Indian scam typology + benign controls.

    PROVENANCE: hand-authored by the developer to cover Indian scam families;
    NOT real-world data. Metrics on this set measure coverage of the target
    domain, not field performance. Kept separate from UCI results for that
    reason.
    """
    path = DATA_DIR / "synthetic_indian_scam.csv"
    cases = []
    with open(path, encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for i, row in enumerate(reader):
            cases.append(
                EvalCase(
                    text=row["text"],
                    label=int(row["label"]),
                    dataset="synthetic_indian",
                    case_id=f"syn_{i}",
                )
            )
    return cases


def load_adversarial() -> list[EvalCase]:
    path = DATA_DIR / "adversarial.csv"
    cases = []
    with open(path, encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for i, row in enumerate(reader):
            cases.append(
                EvalCase(
                    text=row["text"],
                    label=int(row["label"]),
                    dataset="adversarial",
                    case_id=f"adv_{i}",
                )
            )
    return cases
