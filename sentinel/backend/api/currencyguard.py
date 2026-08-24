"""CURRENCYGuard screening API."""

import logging

from fastapi import APIRouter, File, Form, HTTPException

from backend.db import repo
from backend.db.base import session_scope
from backend.modules.currencyguard.screener import screen_note

logger = logging.getLogger(__name__)
router = APIRouter()

_ALLOWED_TYPES = ("image/jpeg", "image/png", "image/jpg")


@router.post("/screen")
def screen_currency(
    file: bytes = File(...),
    denomination: str = Form(default="unknown"),
):
    """FastAPI reads the upload into memory before this sync handler runs,
    so the CV work never blocks the event loop (it executes in a worker
    thread). Content-type validation happens at the client boundary; the
    decoder itself rejects non-images."""
    image_bytes = file
    if len(image_bytes) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "payload_too_large",
                "message": "max 10MB",
            },
        )

    result = screen_note(image_bytes, denomination)
    try:
        with session_scope() as session:
            case = repo.create_case(
                session,
                kind="CURRENCY",
                input_digest=repo.digest_input(
                    "CURRENCY", {"size": len(image_bytes), "denomination": denomination}
                ),
                redacted_input=f"note image {len(image_bytes)}B denom={denomination}",
                source_channel="upload",
            )
            result.case_id = case.id
            risk = {"PLAY_MONEY": "HIGH", "SUSPECT": "HIGH"}.get(
                result.verdict, result.risk_level
            )
            repo.record_event(
                session,
                case_id=case.id,
                module="CURRENCYGuard",
                event_type=result.verdict.lower(),
                risk_level=risk,
                summary=f"{denomination} note screened: {result.verdict}",
                payload={"checks": {c.name: c.passed for c in result.checks}},
            )
            repo.finish_case(
                session,
                case,
                status="done",
                risk_level=risk,
                risk_score=None,
                confidence=result.confidence,
                verdict=result.model_dump(),
            )
            session.flush()
    except Exception as exc:
        logger.warning("case persistence failed for screening result: %s", exc)
    return result
