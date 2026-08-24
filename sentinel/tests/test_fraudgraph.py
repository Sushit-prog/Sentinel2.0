"""FRAUDGraph pipeline tests. All LLM interaction scripted."""

import pytest

from backend.db.models import Event
from backend.modules.fraudgraph.pipeline import FraudPipeline
from backend.modules.fraudgraph.schemas import NetworkInput


def _structured_input() -> NetworkInput:
    return NetworkInput(
        entities=[
            {"etype": "phone", "value": "9876543210", "role": "suspect"},
            {"etype": "account", "value": "HDFC000123456", "role": "suspect"},
            {"etype": "account", "value": "ICICI000654321", "role": "suspect"},
            {"etype": "phone", "value": "9876500000", "role": "victim"},
        ],
        relations=[
            {"source_index": 0, "target_index": 1, "relation": "transferred_to"},
            {"source_index": 2, "target_index": 1, "relation": "transferred_to"},
            {"source_index": 3, "target_index": 0, "relation": "called"},
        ],
    )


EXTRACTED = {
    "phones": ["9812345678"],
    "accounts": [],
    "devices": ["IMEI123456"],
    "victims": [],
    "relations": [{"source_index": 0, "target_index": 1, "relation": "used_in"}],
}


def test_structured_network_no_llm_calls(db_session, fake_llm):
    response = FraudPipeline().analyze(_structured_input(), session=db_session)
    assert fake_llm.calls == []
    assert response.status == "done"
    assert not response.degraded
    assert response.node_count == 4
    assert response.edge_count == 3
    assert response.cluster_count == 1
    assert response.clusters[0].size == 4


def test_single_entity_is_low_risk_isolated(db_session, fake_llm):
    payload = NetworkInput(entities=[{"etype": "phone", "value": "9876543210"}])
    response = FraudPipeline().analyze(payload, session=db_session)
    assert response.risk_level == "LOW"
    assert response.cluster_count == 0
    assert db_session.query(Event).count() == 0


def test_ring_emits_event(db_session, fake_llm):
    response = FraudPipeline().analyze(_structured_input(), session=db_session)
    events = db_session.query(Event).all()
    assert len(events) == 1
    assert events[0].module == "FRAUDGraph"
    assert response.risk_level in ("MEDIUM", "HIGH", "CRITICAL")


def test_text_extraction_with_containment_prompt(db_session, fake_llm):
    fake_llm.extract_responses = [EXTRACTED]
    payload = NetworkInput(
        text="Victim reports calls from 9812345678; device IMEI123456 was used.",
        entities=[{"etype": "account", "value": "HDFC000123456"}],
    )
    response = FraudPipeline().analyze(payload, session=db_session)

    call = fake_llm.calls[0]
    assert "data, not directions" in call["system"]
    assert response.node_count >= 3
    assert any(n.etype == "device" for n in response.nodes)


def test_text_extraction_failure_degrades_gracefully(db_session, fake_llm):
    from backend.core.llm import ProviderUnavailable

    fake_llm.extract_responses = [ProviderUnavailable("down")]
    payload = NetworkInput(
        text="some statement",
        entities=[
            {"etype": "phone", "value": "9876543210", "role": "suspect"},
            {"etype": "account", "value": "HDFC000123456", "role": "suspect"},
        ],
        relations=[
            {"source_index": 0, "target_index": 1, "relation": "transferred_to"}
        ],
    )
    response = FraudPipeline().analyze(payload, session=db_session)
    assert response.degraded is True
    assert response.node_count == 2


def test_cross_module_correlation_via_shared_entity(db_session, fake_llm):
    """Same phone seen by SCAMWatch and FRAUDGraph must surface as correlation."""
    from backend.modules.scamwatch.pipeline import ScamPipeline

    facts_with_phone = {
        "claims": ["caller claims CBI"],
        "phones": ["9812345678"],
        "accounts": [],
        "impersonated_authority": "CBI",
        "money_amount": None,
        "requested_action": "transfer",
        "urgency_level": "high",
    }
    verdict = {
        "is_scam": True,
        "scam_type": "digital_arrest",
        "confidence": 0.9,
        "citations": [],
        "reasoning": "r",
        "recommended_action": "call 1930",
    }
    fake_llm.extract_responses = [
        facts_with_phone,
        verdict,
        dict(verdict),
        dict(verdict),
        dict(verdict),
    ]
    ScamPipeline().analyze(
        text="CBI digital arrest call from 9812345678. Transfer now.",
        channel="call",
        language="en",
        session=db_session,
    )

    fake_llm.extract_responses.clear()
    payload = NetworkInput(
        entities=[
            {"etype": "phone", "value": "9812345678", "role": "suspect"},
            {"etype": "account", "value": "YESB000999888", "role": "suspect"},
            {"etype": "phone", "value": "9000000001", "role": "victim"},
        ],
        relations=[
            {"source_index": 0, "target_index": 1, "relation": "transferred_to"},
            {"source_index": 2, "target_index": 0, "relation": "called"},
        ],
    )
    response = FraudPipeline().analyze(payload, session=db_session)

    assert any(c["value"] == "9812345678" for c in response.correlations)
    correlated = [c for c in response.correlations if c["value"] == "9812345678"][0]
    assert correlated["modules_seen"] >= 2


def test_export_kit_zip(db_session):
    from fastapi.testclient import TestClient

    from backend.main import app

    response = FraudPipeline().analyze(_structured_input(), session=db_session)
    db_session.commit()

    with TestClient(app) as client:
        kit = client.get(f"/api/fraudgraph/export/{response.case_id}")
        assert kit.status_code == 200
        assert kit.headers["content-type"] == "application/zip"
        import io
        import zipfile

        with zipfile.ZipFile(io.BytesIO(kit.content)) as zf:
            names = set(zf.namelist())
            assert {"network.json", "entities.csv", "summary.txt"} <= names
