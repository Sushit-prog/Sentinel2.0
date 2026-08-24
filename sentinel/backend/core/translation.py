"""Citizen-facing translation with deterministic fallbacks.

Tries the fast model first; falls back to reviewed static translations so
a provider outage never leaves a citizen without safety guidance.
"""

import logging

from pydantic import BaseModel, Field

from backend.core.llm import Route, get_llm_client

logger = logging.getLogger(__name__)

LANGUAGE_NAMES = {
    "en": "English",
    "hi": "Hindi",
    "ta": "Tamil",
    "bn": "Bengali",
    "te": "Telugu",
}
SUPPORTED_LANGUAGES = list(LANGUAGE_NAMES.keys())


class TranslatedAlert(BaseModel):
    translated_verdict: str = Field(max_length=500)
    translated_actions: list[str] = Field(default_factory=list, max_length=5)


_FALLBACK_VERDICTS = {
    "hi": {
        "digital_arrest": "यह डिजिटल अरेस्ट स्कैम है। कोई भी सरकारी एजेंसी वीडियो कॉल पर गिरफ्तारी नहीं करती। पैसे ट्रांसफर न करें।",
        "fake_kyc": "यह फर्ज़ी KYC स्कैम है। आपका बैंक कभी OTP या पासवर्ड नहीं मांगता।",
        "fake_investment": "यह फर्ज़ी निवेश स्कैम है। गारंटीशुदा ऊंचे रिटर्न हमेशा धोखाधड़ी होते हैं।",
        "impersonation": "यह प्रतरूपण स्कैम है। संगठन को सीधे आधिकारिक नंबर पर कॉल करके जांचें।",
    },
    "ta": {
        "digital_arrest": "இது டிஜிட்டல் கைது மோசடி. எந்த அரசு நிறுவனமும் வீடியோ அழைப்பில் கைது செய்யாது.",
        "fake_kyc": "இது போலி KYC மோசடி. உங்கள் வங்கி ஒருபோதும் OTP கேட்காது.",
        "impersonation": "இது பாசாங்கு மோசடி. அதிகாரப்பூர்வ எண்ணில் நேரடியாக சரிபார்க்கவும்.",
    },
}


def translate_alert(
    verdict_text: str, actions: list[str], target_language: str
) -> dict:
    if target_language not in SUPPORTED_LANGUAGES or target_language == "en":
        return {
            "translated_verdict": verdict_text,
            "translated_actions": actions,
            "language": "en",
            "mode": "original",
        }

    lang_name = LANGUAGE_NAMES[target_language]
    try:
        client = get_llm_client()
        system = (
            f"Translate a fraud-safety alert into {lang_name}. Keep numbers, "
            "URLs and helpline codes unchanged. Plain, urgent, simple language."
        )
        user = f"VERDICT: {verdict_text}\nACTIONS: " + "\n".join(
            f"- {a}" for a in actions[:4]
        )
        parsed, _ = client.extract(
            TranslatedAlert, user, system=system, route=Route.FAST, max_tokens=400
        )
        return {
            "translated_verdict": parsed.translated_verdict,
            "translated_actions": parsed.translated_actions or actions[:3],
            "language": target_language,
            "mode": "llm",
        }
    except Exception as exc:
        logger.warning(
            "LLM translation failed (%s); using fallback", type(exc).__name__
        )

    for scam_key, text in _FALLBACK_VERDICTS.get(target_language, {}).items():
        if scam_key in verdict_text.lower().replace(" ", "_").replace("-", "_"):
            call_line = {"hi": "1930 पर कॉल करें", "ta": "1930-ஐ அழைக்கவும்"}.get(
                target_language, "Call 1930"
            )
            return {
                "translated_verdict": text,
                "translated_actions": [call_line],
                "language": target_language,
                "mode": "fallback_static",
            }

    return {
        "translated_verdict": verdict_text,
        "translated_actions": actions,
        "language": "en",
        "mode": "unavailable",
    }
