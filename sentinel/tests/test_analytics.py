"""Analytics API v2 tests - honest, timestamp-derived numbers only."""

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.modules.scamwatch.pipeline import ScamPipeline
from tests.test_scamwatch_pipeline import SCAM_TEXT, _script_agreeing


@pytest.fixture()
def client(fake_llm):
    with TestClient(app) as c:
        yield c


def test_stats_counts_real_events(client, fake_llm):
    _script_agreeing(fake_llm)
    with TestClient(app) as _:
        from backend.db.base import session_scope

        with session_scope() as session:
            ScamPipeline().analyze(
                text=SCAM_TEXT, channel="sms", language="en", session=session
            )

    stats = client.get("/api/analytics/stats").json()
    assert stats["total_events"] == 1
    assert stats["events_last_24h"] == 1
    assert stats["events_by_module"]["SCAMWatch"] == 1


def test_recent_returns_stored_events(client, fake_llm):
    from backend.db.base import session_scope

    _script_agreeing(fake_llm)
    with session_scope() as session:
        ScamPipeline().analyze(
            text=SCAM_TEXT, channel="sms", language="en", session=session
        )
    recent = client.get("/api/analytics/recent?limit=5").json()
    assert recent["count"] >= 1
    assert "occurred_at" in recent["events"][0]
    assert "T" in recent["events"][0]["occurred_at"]


def test_timeline_has_no_fabricated_buckets_when_empty(client):
    body = client.get("/api/analytics/timeline?hours=2").json()
    assert body["window_hours"] == 2
    assert isinstance(body["buckets"], list)


def test_timeline_bucket_matches_event_hour(client, fake_llm):
    from backend.db.base import session_scope

    _script_agreeing(fake_llm)
    with session_scope() as session:
        ScamPipeline().analyze(
            text=SCAM_TEXT, channel="sms", language="en", session=session
        )
    body = client.get("/api/analytics/timeline?hours=24").json()
    assert len(body["buckets"]) >= 1
    assert all(b["total"] >= 1 for b in body["buckets"])
