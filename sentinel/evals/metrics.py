"""Classification, calibration and cost metrics. Pure functions."""

import math


def confusion_matrix(pairs: list[tuple[int, int]]) -> dict[str, int]:
    tp = sum(1 for p, a in pairs if a == 1 and p == 1)
    fp = sum(1 for p, a in pairs if a == 0 and p == 1)
    fn = sum(1 for p, a in pairs if a == 1 and p == 0)
    tn = sum(1 for p, a in pairs if a == 0 and p == 0)
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn}


def classification_metrics(pairs: list[tuple[int, int]]) -> dict:
    cm = confusion_matrix(pairs)
    total = max(len(pairs), 1)
    precision = cm["tp"] / (cm["tp"] + cm["fp"]) if (cm["tp"] + cm["fp"]) else 0.0
    recall = cm["tp"] / (cm["tp"] + cm["fn"]) if (cm["tp"] + cm["fn"]) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    fpr = cm["fp"] / (cm["fp"] + cm["tn"]) if (cm["fp"] + cm["tn"]) else 0.0
    fnr = cm["fn"] / (cm["fn"] + cm["tp"]) if (cm["fn"] + cm["tp"]) else 0.0
    accuracy = (cm["tp"] + cm["tn"]) / total
    return {
        "n": len(pairs),
        "accuracy": round(accuracy, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "fpr": round(fpr, 4),
        "fnr": round(fnr, 4),
        **cm,
    }


def expected_calibration_error(
    scores: list[float], labels: list[int], bins: int = 10
) -> float:
    """ECE over predicted scam-probabilities vs binary outcomes."""
    if not scores:
        return 0.0
    bucket_sums = [0.0] * bins
    bucket_counts = [0] * bins
    bucket_labels = [0.0] * bins
    for score, label in zip(scores, labels):
        s = min(max(score, 0.0), 1.0)
        b = min(int(s * bins), bins - 1)
        bucket_counts[b] += 1
        bucket_sums[b] += s
        bucket_labels[b] += label
    ece = 0.0
    n = len(scores)
    for i in range(bins):
        if bucket_counts[i] == 0:
            continue
        confidence = bucket_sums[i] / bucket_counts[i]
        accuracy = bucket_labels[i] / bucket_counts[i]
        ece += (bucket_counts[i] / n) * abs(confidence - accuracy)
    return round(ece, 4)


def brier_score(scores: list[float], labels: list[int]) -> float:
    if not scores:
        return 0.0
    return round(sum((s - l) ** 2 for s, l in zip(scores, labels)) / len(scores), 4)


def latency_percentiles(latencies_ms: list[int]) -> dict:
    if not latencies_ms:
        return {"p50": 0, "p95": 0, "max": 0}
    ordered = sorted(latencies_ms)

    def pct(p: float) -> int:
        idx = min(int(math.ceil(p / 100 * len(ordered))) - 1, len(ordered) - 1)
        return ordered[max(idx, 0)]

    return {"p50": pct(50), "p95": pct(95), "max": ordered[-1]}
