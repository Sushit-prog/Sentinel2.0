"""Deterministic citizen alert construction.

Alerts are policy-gate output, not model output: wording is selected by
scam type from reviewed templates so a prompt injection in the analyzed
message can never author the safety advice shown to citizens.
"""

from backend.modules.scamwatch.patterns import SAFE_INDICATORS
from backend.modules.scamwatch.schemas import RiskLevel, ScamAnalysisResponse, ScamType

_EMERGENCY_CONTACTS = [
    {"name": "National Cyber Crime Helpline", "contact": "1930", "kind": "phone"},
    {"name": "Cyber Crime Portal", "contact": "cybercrime.gov.in", "kind": "web"},
    {
        "name": "Chakshu / Sanchar Saathi (block numbers)",
        "contact": "sancharsaathi.gov.in",
        "kind": "web",
    },
]

_VERDICT_TEMPLATES = {
    ScamType.DIGITAL_ARREST: "This is a 'digital arrest' scam. No government agency arrests anyone by video call.",
    ScamType.FAKE_KYC: "This looks like a fake KYC scam. Your bank never asks for OTPs or passwords.",
    ScamType.FAKE_INVESTMENT: "This matches investment fraud. Guaranteed high returns are always fake.",
    ScamType.FAKE_JOB: "This matches a job scam. Genuine employers never charge fees.",
    ScamType.FAKE_LOTTERY: "This matches a lottery scam. You cannot win a draw you never entered.",
    ScamType.IMPERSONATION: "This appears to be official impersonation. Verify by calling the organisation directly.",
    ScamType.ROMANCE: "This shows romance-scam patterns. Be very careful about money requests online.",
}

_ACTIONS_BY_RISK = {
    RiskLevel.CRITICAL: [
        "Stop all communication immediately. Do not transfer any money.",
        "If you already shared details, call 1930 within the golden hour.",
        "File a complaint at cybercrime.gov.in and save all evidence.",
    ],
    RiskLevel.HIGH: [
        "Do not share OTPs, passwords, or documents.",
        "Verify independently using official contact details only.",
        "Report the number via Chakshu (sancharsaathi.gov.in).",
    ],
    RiskLevel.MEDIUM: [
        "Stay cautious; verify through official channels before acting."
    ],
    RiskLevel.LOW: ["No immediate action required. Remain alert."],
}


def build_citizen_alert(analysis: ScamAnalysisResponse, language: str = "en") -> dict:
    if analysis.scam_type and analysis.risk_level in (
        RiskLevel.HIGH,
        RiskLevel.CRITICAL,
    ):
        one_liner = _VERDICT_TEMPLATES[analysis.scam_type]
    elif analysis.scam_type:
        one_liner = (
            f"Possible {analysis.scam_type.value.replace('_', ' ')} signals detected."
        )
    else:
        one_liner = "No strong scam indicators found in this message."

    actions = list(_ACTIONS_BY_RISK[analysis.risk_level])
    if analysis.recommended_action and analysis.risk_level != RiskLevel.LOW:
        actions.append(analysis.recommended_action)

    return {
        "case_id": analysis.case_id,
        "one_line_verdict": one_liner,
        "recommended_actions": actions,
        "emergency_contacts": _EMERGENCY_CONTACTS,
        "safety_notes": list(SAFE_INDICATORS[:3]),
        "risk_level": analysis.risk_level.value,
        "needs_review": analysis.verification.needs_review or analysis.degraded,
        "language": language if language in ("en",) else language,
    }
