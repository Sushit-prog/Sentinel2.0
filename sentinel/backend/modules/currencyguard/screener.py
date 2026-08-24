"""CURRENCYGuard - heuristic image screening, honestly scoped.

This module does NOT authenticate currency. It applies classical CV
quality and structure checks to flag obvious problems: play/toy notes,
low-resolution images, wrong aspect ratios, missing serial patterns.
Verdicts are screening hints with explicit uncertainty; only a trained
human with the physical note (or a bank's forensic process) can confirm
authenticity. The legacy "vision LLM" framing was removed because the
model never saw the image - it narrated CV numbers.
"""

import logging
import re
import time

import cv2
import numpy as np
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

_ASPECT_RANGES = {
    "50": (1.9, 2.3),
    "100": (2.1, 2.5),
    "200": (2.2, 2.6),
    "500": (2.0, 2.4),
    "2000": (2.0, 2.4),
}
_SERIAL_RE = re.compile(r"[0-9]{1,2}[A-Z][A-Z]?[0-9]{6}")
_PLAY_MARKERS = ("play money", "toy note", "prop money", "movie money", "replica")


class ScreenCheck(BaseModel):
    name: str
    passed: bool | None
    detail: str


class ScreeningResponse(BaseModel):
    case_id: str | None = None
    verdict: str = Field(
        pattern="^(GENUINE_CANDIDATE|SUSPECT|PLAY_MONEY|INCONCLUSIVE)$"
    )
    risk_level: str = Field(pattern="^(LOW|MEDIUM|HIGH)$")
    confidence: float
    checks: list[ScreenCheck]
    disclaimer: str = (
        "Heuristic image screening only. This is NOT an authenticity "
        "guarantee. Verify suspect notes through your bank."
    )
    latency_ms: int = 0


def _decode(image_bytes: bytes) -> np.ndarray | None:
    array = np.frombuffer(image_bytes, dtype=np.uint8)
    return cv2.imdecode(array, cv2.IMREAD_COLOR)


def screen_note(image_bytes: bytes, denomination: str = "unknown") -> ScreeningResponse:
    started = time.monotonic()
    checks: list[ScreenCheck] = []

    image = _decode(image_bytes)
    if image is None:
        return ScreeningResponse(
            verdict="INCONCLUSIVE",
            risk_level="MEDIUM",
            confidence=0.3,
            checks=[
                ScreenCheck(
                    name="decodable_image",
                    passed=False,
                    detail="image could not be decoded",
                )
            ],
            latency_ms=int((time.monotonic() - started) * 1000),
        )

    height, width = image.shape[:2]

    resolution_ok = width >= 600 and height >= 300
    checks.append(
        ScreenCheck(
            name="resolution",
            passed=resolution_ok,
            detail=f"{width}x{height}px; >=600x300 needed for meaningful checks",
        )
    )

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    sharpness = cv2.Laplacian(gray, cv2.CV_64F).variance()
    sharp_ok = sharpness >= 60.0
    checks.append(
        ScreenCheck(
            name="sharpness",
            passed=sharp_ok,
            detail=f"laplacian variance {sharpness:.1f}; >=60 expected",
        )
    )

    aspect = width / max(height, 1)
    expected = _ASPECT_RANGES.get(denomination)
    if expected:
        aspect_ok = expected[0] <= aspect <= expected[1]
        aspect_detail = f"aspect {aspect:.2f} vs expected {expected}"
    else:
        aspect_ok = None
        aspect_detail = (
            f"aspect {aspect:.2f}; no reference for denomination '{denomination}'"
        )
    checks.append(
        ScreenCheck(name="aspect_ratio", passed=aspect_ok, detail=aspect_detail)
    )

    text_region = _extract_text(image)
    play_hit = any(marker in text_region.lower() for marker in _PLAY_MARKERS)
    checks.append(
        ScreenCheck(
            name="play_money_marker",
            passed=False if play_hit else True,
            detail="marker text found" if play_hit else "no play-money markers",
        )
    )
    has_serial = bool(_SERIAL_RE.search(text_region.upper()))
    checks.append(
        ScreenCheck(
            name="serial_number_pattern",
            passed=has_serial if text_region else None,
            detail=(
                "serial-like pattern found"
                if has_serial
                else "no serial pattern detected (OCR may be limited at this quality)"
                if text_region
                else "OCR unavailable; check skipped"
            ),
        )
    )

    return ScreeningResponse(
        verdict=_verdict(checks, play_hit, resolution_ok),
        risk_level=_risk(play_hit, resolution_ok),
        confidence=_confidence(checks),
        checks=checks,
        latency_ms=int((time.monotonic() - started) * 1000),
    )


def _extract_text(image: np.ndarray) -> str:
    try:
        import pytesseract  # optional dependency

        return pytesseract.image_to_string(image)
    except Exception:
        return ""


def _verdict(checks: list[ScreenCheck], play_hit: bool, resolution_ok: bool) -> str:
    if play_hit:
        return "PLAY_MONEY"
    if not resolution_ok:
        return "INCONCLUSIVE"
    failed = sum(1 for c in checks if c.passed is False)
    passed = sum(1 for c in checks if c.passed is True)
    if failed == 0 and passed >= 3:
        return "GENUINE_CANDIDATE"
    if failed >= 2:
        return "SUSPECT"
    return "INCONCLUSIVE"


def _risk(play_hit: bool, resolution_ok: bool) -> str:
    if play_hit:
        return "HIGH"
    if not resolution_ok:
        return "MEDIUM"
    return "LOW"


def _confidence(checks: list[ScreenCheck]) -> float:
    decided = [c for c in checks if c.passed is not None]
    if not decided:
        return 0.2
    agreement = sum(1 for c in decided if c.passed) / len(decided)
    coverage = len(decided) / len(checks)
    return round(0.4 + 0.4 * agreement * coverage, 3)
