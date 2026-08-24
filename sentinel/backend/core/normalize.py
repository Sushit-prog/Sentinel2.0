"""Entity value normalization.

Normalization is what makes cross-module correlation exact rather than
fuzzy: the same phone number arriving from a citizen report and a police
case must resolve to one entity row.
"""

import re

_PHONE_RE = re.compile(r"\D+")


def normalize_phone(raw: str) -> str | None:
    digits = _PHONE_RE.sub("", raw)
    if len(digits) > 10 and digits.startswith("91"):
        digits = digits[2:]
    if digits.startswith("0") and len(digits) == 11:
        digits = digits[1:]
    if len(digits) == 10 and digits[0] in "6789":
        return digits
    return digits or None


def normalize_account(raw: str) -> str | None:
    cleaned = re.sub(r"[^A-Za-z0-9]", "", raw).upper()
    return cleaned or None


def normalize_device(raw: str) -> str | None:
    cleaned = re.sub(r"[^A-Za-z0-9-]", "", raw).upper()
    return cleaned or None


NORMALIZERS = {
    "phone": normalize_phone,
    "account": normalize_account,
    "device": normalize_device,
}


def normalize_entity(etype: str, raw: str) -> tuple[str, str] | None:
    """Return (type, normalized_value) or None when unusable."""
    fn = NORMALIZERS.get(etype)
    if fn is None:
        return None
    value = fn(raw)
    if not value:
        return None
    return etype, value
