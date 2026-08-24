import pytest
from fastapi.testclient import TestClient

from backend.api.scamwatch import set_pipeline
from backend.main import app
from backend.modules.scamwatch.pipeline import ScamPipeline
from tests.test_scamwatch_pipeline import (
    BENIGN_TEXT,
    SCAM_TEXT,
    _script_agreeing,
)


@pytest.fixture()
def client(fake_llm):
    set_pipeline(ScamPipeline())
    with TestClient(app) as c:
        yield c
    set_pipeline(None)


def test_health_open_and_versioned(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["version"] == "2.0"
    assert "X-Request-ID" in r.headers


def test_analyze_endpoint_full_shape(client, fake_llm):
    _script_agreeing(fake_llm)
    r = client.post(
        "/api/scamwatch/analyze", json={"text": SCAM_TEXT, "channel": "sms"}
    )
    assert r.status_code == 200
    body = r.json()
    for key in (
        "case_id",
        "status",
        "risk_level",
        "risk_score",
        "confidence",
        "verification",
        "prescreen",
        "usage",
        "evidence",
    ):
        assert key in body
    assert body["scam_type"] == "digital_arrest"
    assert body["usage"][0]["stage"] == "extraction"


def test_analyze_validation_rejects_short_text(client):
    r = client.post("/api/scamwatch/analyze", json={"text": "hi"})
    assert r.status_code == 422


def test_analyze_rejects_unsupported_language(client):
    r = client.post(
        "/api/scamwatch/analyze", json={"text": SCAM_TEXT, "language": "fr"}
    )
    assert r.status_code == 422


def test_patterns_endpoint(client):
    r = client.get("/api/scamwatch/patterns")
    assert r.status_code == 200
    assert r.json()["total_patterns"] >= 7


def test_case_lookup_unknown_returns_404(client):
    assert client.get("/api/scamwatch/cases/case_doesnotexist").status_code == 404


def test_alert_flow_after_analysis(client, fake_llm):
    _script_agreeing(fake_llm)
    created = client.post("/api/scamwatch/analyze", json={"text": SCAM_TEXT}).json()

    alert = client.post(f"/api/scamwatch/alert/{created['case_id']}")
    assert alert.status_code == 200
    payload = alert.json()
    assert "1930" in [c["contact"] for c in payload["emergency_contacts"]]
    assert payload["recommended_actions"]


def test_benign_alert_is_low_key(client, fake_llm):
    created = client.post("/api/scamwatch/analyze", json={"text": BENIGN_TEXT}).json()
    assert created["risk_level"] == "LOW"
    alert = client.post(f"/api/scamwatch/alert/{created['case_id']}").json()
    assert "No immediate action" in alert["recommended_actions"][0]
