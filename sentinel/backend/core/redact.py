"""PII redaction for persisted text and logs.

Full-fidelity text exists only in-flight during a pipeline run. Anything
stored at rest (case records, intelligence events, vector store, logs)
passes through redact() first.
"""

import re

_PHONE = re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9](?:[\s-]?\d){9}(?!\d)")
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_CARD = re.compile(r"(?<!\d)\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{1,7}(?!\d)")
_UPI = re.compile(r"\b[A-Za-z0-9._-]{2,}@[A-Za-z]{2,}\b")
_OTP = re.compile(r"(?i)\b(?:otp|pin|password|cvv)\b[^0-9]{0,20}?(\d{4,8})\b")


def _mask_digits(match: re.Match) -> str:
    return "XX" + match.group()[-3:]


def redact(text: str) -> str:
    if not text:
        return text
    text = _OTP.sub(lambda m: m.group().replace(m.group(1), "XXXXX"), text)
    text = _CARD.sub(
        lambda m: "XXXX-XXXX-XXX" + re.sub(r"\D", "", m.group())[-2:], text
    )
    text = _PHONE.sub(_mask_digits, text)
    text = _EMAIL.sub(lambda m: m.group()[0] + "***@" + m.group().split("@")[1], text)
    text = _UPI.sub(lambda m: m.group().split("@")[0][:2] + "***@***", text)
    return text


def content_fingerprint(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode()).hexdigest()[:16]
