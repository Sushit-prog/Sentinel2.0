"""SCAMWatch API. Endpoints are sync `def` on purpose: FastAPI runs them in
the threadpool so multi-second LLM calls never block the event loop."""

import logging

from fastapi import APIRouter, HTTPException, Path as PathParam
from pydantic import BaseModel, Field

from backend.db import repo
from backend.db.base import session_scope
from backend.db.models import Case
from backend.modules.scamwatch.alerts import build_citizen_alert
from backend.modules.scamwatch.patterns import SCAM_PATTERNS
from backend.modules.scamwatch.pipeline import ScamPipeline
from backend.modules.scamwatch.schemas import ScamAnalysisResponse

logger = logging.getLogger(__name__)
router = APIRouter()

_pipeline: ScamPipeline | None = None


def get_pipeline() -> ScamPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = ScamPipeline()
    return _pipeline


def set_pipeline(pipeline: ScamPipeline | None) -> None:
    global _pipeline
    _pipeline = pipeline


class ScamAnalysisRequest(BaseModel):
    text: str = Field(min_length=5, max_length=5000)
    channel: str = Field(default="unknown", max_length=30)
    language: str = Field(default="en", pattern="^(en|hi|ta|bn|te)$")


class CitizenAlertResponse(BaseModel):
    case_id: str
    one_line_verdict: str
    recommended_actions: list[str]
    emergency_contacts: list[dict]
    language: str


@router.post("/analyze", response_model=ScamAnalysisResponse)
def analyze_scam(request: ScamAnalysisRequest) -> ScamAnalysisResponse:
    try:
        with session_scope() as session:
            return get_pipeline().analyze(
                text=request.text,
                channel=request.channel,
                language=request.language,
                session=session,
            )
    except Exception as exc:
        logger.exception("scam analysis failed")
        raise HTTPException(
            status_code=500,
            detail={
                "code": "analysis_failed",
                "message": "analysis failed; see server logs for details",
            },
        ) from exc


@router.get("/patterns")
def get_known_patterns():
    return {
        "total_patterns": len(SCAM_PATTERNS),
        "patterns": [
            {
                "type": key,
                "description": data["description"],
                "severity": data["severity"],
                "typical_channel": data["typical_channel"],
            }
            for key, data in SCAM_PATTERNS.items()
        ],
    }


@router.get("/cases/{case_id}", response_model=ScamAnalysisResponse)
def get_case(case_id: str = PathParam(max_length=40)):
    with session_scope() as session:
        case = session.get(Case, case_id)
        if case is None or case.verdict is None:
            raise HTTPException(
                status_code=404,
                detail={"code": "not_found", "message": "case not found"},
            )
        return ScamAnalysisResponse.model_validate(case.verdict)


@router.post("/alert/{case_id}", response_model=CitizenAlertResponse)
def citizen_alert(case_id: str):
    with session_scope() as session:
        case = session.get(Case, case_id)
        if case is None or case.verdict is None:
            raise HTTPException(
                status_code=404,
                detail={"code": "not_found", "message": "case not found"},
            )
        analysis = ScamAnalysisResponse.model_validate(case.verdict)
        alert = build_citizen_alert(analysis, language=case.language)
        return CitizenAlertResponse(
            case_id=case.id,
            one_line_verdict=alert["one_line_verdict"],
            recommended_actions=alert["recommended_actions"],
            emergency_contacts=alert["emergency_contacts"],
            language=alert.get("language", "en"),
        )
