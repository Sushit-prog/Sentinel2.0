"""FRAUDGraph API."""

import logging

from fastapi import APIRouter, HTTPException, Path as PathParam
from pydantic import Field

from backend.db.base import session_scope
from backend.modules.fraudgraph.pipeline import FraudPipeline
from backend.modules.fraudgraph.schemas import FraudAnalysisResponse, NetworkInput

logger = logging.getLogger(__name__)
router = APIRouter()

_pipeline: FraudPipeline | None = None


def get_fraud_pipeline() -> FraudPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = FraudPipeline()
    return _pipeline


def set_fraud_pipeline(pipeline: FraudPipeline | None) -> None:
    global _pipeline
    _pipeline = pipeline


class FraudAnalyzeRequest(NetworkInput):
    pass


@router.post("/analyze", response_model=FraudAnalysisResponse)
def analyze_network(request: FraudAnalyzeRequest) -> FraudAnalysisResponse:
    if not request.text and not request.entities:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "empty_input",
                "message": "provide 'text', 'entities', or both",
            },
        )
    try:
        with session_scope() as session:
            return get_fraud_pipeline().analyze(
                NetworkInput(**request.model_dump()), session=session
            )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("fraud network analysis failed")
        raise HTTPException(
            status_code=500,
            detail={
                "code": "analysis_failed",
                "message": "analysis failed; see server logs for details",
            },
        ) from exc


@router.get("/cases/{case_id}", response_model=FraudAnalysisResponse)
def get_case(case_id: str = PathParam(max_length=40)):
    from backend.db.models import Case

    with session_scope() as session:
        case = session.get(Case, case_id)
        if case is None or case.verdict is None or case.kind != "FRAUD":
            raise HTTPException(
                status_code=404,
                detail={"code": "not_found", "message": "case not found"},
            )
        return FraudAnalysisResponse.model_validate(case.verdict)


@router.get("/export/{case_id}")
def export_case_kit(case_id: str):
    """Evidence kit: machine-readable JSON of the full network analysis."""
    import io
    import json
    import zipfile
    from datetime import datetime, timezone

    from fastapi.responses import Response

    from backend.db.models import Case

    with session_scope() as session:
        case = session.get(Case, case_id)
        if case is None or case.verdict is None or case.kind != "FRAUD":
            raise HTTPException(
                status_code=404,
                detail={"code": "not_found", "message": "case not found"},
            )
        verdict = dict(case.verdict)

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("network.json", json.dumps(verdict, indent=2, ensure_ascii=False))
        entity_rows = ["key,etype,role,prior_sightings,cross_module,degree"]
        for n in verdict.get("nodes", []):
            entity_rows.append(
                ",".join(
                    [
                        n["key"],
                        n["etype"],
                        n["role"],
                        str(n.get("prior_sightings", 0)),
                        str(n.get("cross_module", False)),
                        str(n.get("degree", 0)),
                    ]
                )
            )
        zf.writestr("entities.csv", "\n".join(entity_rows))
        manifest = (
            "SENTINEL FRAUDGraph evidence summary\n"
            f"Generated: {datetime.now(timezone.utc).isoformat()}\n"
            f"Case: {verdict['case_id']}\n"
            f"Risk: {verdict['risk_level']} (score {verdict['risk_score']})\n"
            f"Nodes: {verdict['node_count']}  Edges: {verdict['edge_count']}  "
            f"Clusters: {verdict['cluster_count']}\n\n"
            "Method: deterministic normalization + connected-component ring "
            "detection + betweenness hub ranking over analyst-supplied and "
            "LLM-extracted entities. LLM output is schema-constrained; risk "
            "scoring is rule-based.\n"
            "Limitations: entity values are taken at face value; no external "
            "verification is performed by this tool.\n"
        )
        zf.writestr("summary.txt", manifest)
    return Response(
        content=buffer.getvalue(),
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename=FRAUDGraph_{case_id}.zip"
        },
    )
