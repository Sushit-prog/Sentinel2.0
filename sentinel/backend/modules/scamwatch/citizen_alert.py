"""Citizen Alert builder — converts scam analysis into shareable alert format."""

import uuid
from datetime import datetime

from backend.models.scam_models import (
    CitizenAlert,
    EmergencyContact,
    MHAAlertPayload,
    ScamAnalysisResponse,
)

# Emergency contacts — static reference data
EMERGENCY_CONTACTS = [
    EmergencyContact(
        name="Cyber Crime Helpline",
        number="1930",
        description="National cyber crime reporting helpline (24/7)",
    ),
    EmergencyContact(
        name="Cyber Crime Portal",
        number="cybercrime.gov.in",
        description="Online complaint filing portal",
        url="https://cybercrime.gov.in",
    ),
    EmergencyContact(
        name="Women Helpline",
        number="181",
        description="For crimes against women (including online harassment)",
    ),
    EmergencyContact(
        name="Police Emergency",
        number="112",
        description="Immediate police assistance",
    ),
    EmergencyContact(
        name="RBI Ombudsman",
        number="14448",
        description="Banking/complaint redressal",
    ),
]

# Scam-type to plain-language verdict mapping
VERDICT_MAP = {
    "digital_arrest": "This is a digital arrest scam. No government agency conducts arrests over video call. Do not transfer any money.",
    "fake_kyc": "This is a fake KYC scam. Your bank will never ask you to share OTP or click links for KYC updates.",
    "fake_investment": "This is a fake investment scam. Guaranteed high returns are always fraudulent. Do not invest.",
    "fake_job": "This is a fake job scam. Legitimate employers never charge registration fees.",
    "fake_lottery": "This is a fake lottery scam. You have not won any prize. Do not pay any processing fee.",
    "impersonation": "This is an impersonation scam. The caller is not who they claim to be. Hang up immediately.",
    "romance_scam": "This is a romance scam. The person you met online is not real. Do not send any money.",
}

# Scam-type to recommended actions mapping
ACTIONS_MAP = {
    "digital_arrest": [
        "Hang up the call immediately — no government agency conducts arrests via video call",
        "Do NOT transfer any money to any account",
        "Block the phone number on your device",
        "Report to Cyber Crime Helpline: 1930",
        "File a complaint at cybercrime.gov.in",
        "Alert your bank if you have already shared account details",
    ],
    "fake_kyc": [
        "Do NOT click any links in the message",
        "Do NOT share your OTP, PIN, or account password",
        "Contact your bank directly using the number on your debit card",
        "Report the phishing message to 1930",
        "Forward the SMS to 7726 (TRAI spam reporting)",
    ],
    "fake_investment": [
        "Do NOT transfer any money to the offered account",
        "Do NOT join any WhatsApp/Telegram investment groups",
        "Report the account number to your bank immediately",
        "File a complaint at cybercrime.gov.in",
        "Block the sender on all platforms",
    ],
    "fake_job": [
        "Do NOT pay any registration or security deposit",
        "Do NOT share Aadhaar, PAN, or bank details",
        "Report the job listing to the platform where you found it",
        "File a complaint at cybercrime.gov.in if money was transferred",
    ],
    "fake_lottery": [
        "Do NOT pay any processing fee to claim a prize",
        "You have not won any lottery — this is a scam",
        "Block the sender and delete the message",
        "Report to Cyber Crime Helpline: 1930",
    ],
    "impersonation": [
        "Hang up immediately — verify independently",
        "Do NOT share OTP, PIN, or install any remote access app",
        "Call your bank or the organization directly using their official number",
        "Report the number to 1930",
    ],
    "romance_scam": [
        "Stop all communication with this person immediately",
        "Do NOT send any more money",
        "Report the profile to the platform (social media/dating app)",
        "File a police complaint if money was transferred",
        "Contact Cyber Crime Helpline: 1930",
    ],
}

DEFAULT_ACTIONS = [
    "Do not transfer any money",
    "Block the sender immediately",
    "Report to Cyber Crime Helpline: 1930",
    "File a complaint at cybercrime.gov.in",
]


def build_citizen_alert(
    analysis: ScamAnalysisResponse,
    channel: str = "unknown",
    language: str = "en",
) -> CitizenAlert:
    """
    Convert a ScamAnalysisResponse into a structured CitizenAlert.
    Pure formatting/derivation — no LLM call, zero additional cost.
    Translations are handled externally if language != "en".
    """
    scam_type = (analysis.scam_type or "unknown").lower().replace(" ", "_")
    risk_level = analysis.risk_level.value

    # One-line verdict
    one_line = VERDICT_MAP.get(
        scam_type,
        f"This appears to be a {scam_type.replace('_', ' ')} scam. Do not transfer any money.",
    )
    # Escalate verdict language for CRITICAL
    if risk_level == "CRITICAL" and scam_type in VERDICT_MAP:
        one_line = "WARNING: " + one_line

    # Recommended actions
    actions = ACTIONS_MAP.get(scam_type, DEFAULT_ACTIONS)

    # MHA alert payload
    indicators_dicts = [
        {
            "indicator": ind.indicator,
            "severity": ind.severity.value,
            "explanation": ind.explanation,
        }
        for ind in analysis.indicators
    ]

    freeze_window = {
        "CRITICAL": 30,
        "HIGH": 60,
        "MEDIUM": 120,
        "LOW": 240,
    }.get(risk_level, 120)

    mha_payload = MHAAlertPayload(
        complainant_channel=channel,
        scam_type=scam_type,
        urgency=risk_level,
        detected_at=datetime.utcnow().isoformat() + "Z",
        indicators=indicators_dicts,
        recommended_freeze_window_minutes=freeze_window,
    )

    # Translation fields
    translated_verdict = analysis.translated_verdict
    translated_actions = analysis.translated_actions

    # If analysis didn't translate (e.g. alert generated separately), do it now
    if language and language != "en" and not translated_verdict:
        try:
            from backend.core.translation import translate_verdict

            translated = translate_verdict(
                one_line_verdict=one_line,
                recommended_actions=actions[:3],
                target_language=language,
            )
            translated_verdict = translated["translated_verdict"]
            translated_actions = translated["translated_actions"]
        except Exception as e:
            logger.warning(f"Alert translation failed: {e}")

    return CitizenAlert(
        alert_id=str(uuid.uuid4())[:12],
        analysis_id=analysis.analysis_id,
        scam_type=scam_type,
        risk_level=risk_level,
        risk_score=analysis.risk_score,
        one_line_verdict=one_line,
        recommended_actions=actions,
        emergency_contacts=EMERGENCY_CONTACTS,
        mha_alert_payload=mha_payload,
        generated_at=datetime.utcnow().isoformat() + "Z",
        translated_verdict=translated_verdict,
        translated_actions=translated_actions,
        target_language=language,
    )
