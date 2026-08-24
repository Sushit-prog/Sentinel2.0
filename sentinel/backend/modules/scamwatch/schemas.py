"""Typed contracts for the SCAMWatch pipeline."""

from enum import Enum

from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ScamType(str, Enum):
    DIGITAL_ARREST = "digital_arrest"
    FAKE_KYC = "fake_kyc"
    FAKE_INVESTMENT = "fake_investment"
    FAKE_JOB = "fake_job"
    FAKE_LOTTERY = "fake_lottery"
    IMPERSONATION = "impersonation"
    ROMANCE = "romance"
    LEGITIMATE = "legitimate"


class Route(str, Enum):
    RULES_ONLY = "rules_only"
    FAST = "fast"
    STRONG = "strong"


class PrescreenSignals(BaseModel):
    urgency_hits: list[str] = Field(default_factory=list)
    authority_hits: list[str] = Field(default_factory=list)
    keyword_hits: list[str] = Field(default_factory=list)
    has_url: bool = False
    requests_otp: bool = False
    requests_money: bool = False


class PrescreenResult(BaseModel):
    matched_type: ScamType | None
    signals: PrescreenSignals
    rule_score: float
    route: Route
    reason: str


class ExtractedFacts(BaseModel):
    """Quarantined-stage output. The only channel through which untrusted
    message text reaches downstream reasoning."""

    claims: list[str] = Field(default_factory=list, max_length=10)
    phones: list[str] = Field(default_factory=list, max_length=10)
    accounts: list[str] = Field(default_factory=list, max_length=10)
    impersonated_authority: str | None = None
    money_amount: str | None = None
    requested_action: str | None = None
    urgency_level: str = Field(default="none", pattern="^(none|low|medium|high)$")
    language_detected: str = "en"


class EvidenceCited(BaseModel):
    source: str
    excerpt: str = Field(max_length=300)
    similarity: float | None = None


class Verdict(BaseModel):
    """Privileged-stage output. Citations index into the combined evidence
    block (prior patterns then extracted claims) presented in the prompt."""

    is_scam: bool
    scam_type: ScamType = ScamType.LEGITIMATE
    confidence: float = Field(ge=0.0, le=1.0)
    citations: list[int] = Field(default_factory=list, max_length=8)
    reasoning: str = Field(default="", max_length=600)
    recommended_action: str = Field(default="", max_length=300)


class StageUsage(BaseModel):
    stage: str
    model: str | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int = 0
    est_cost_usd: float = 0.0
    repaired: bool = False


class VerificationSummary(BaseModel):
    samples: int = 0
    agreement_ratio: float = 1.0
    mean_confidence: float = 0.0
    needs_review: bool = False
    method: str = "label_consistency"


class ScamAnalysisResponse(BaseModel):
    case_id: str
    status: str
    risk_level: RiskLevel
    risk_score: float
    confidence: float
    scam_type: ScamType | None
    verdict_reasoning: str
    recommended_action: str
    evidence: list[EvidenceCited]
    verification: VerificationSummary
    prescreen: PrescreenResult
    degraded: bool = False
    usage: list[StageUsage]
    total_cost_usd: float = 0.0
    latency_ms: int = 0
