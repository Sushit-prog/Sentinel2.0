from sqlalchemy import select

from backend.db import repo
from backend.db.models import Entity


def test_create_case_and_digest_lookup(db_session):
    digest = repo.digest_input("SCAM", {"text": "hello"})
    case = repo.create_case(db_session, kind="SCAM", input_digest=digest)
    db_session.flush()
    found = repo.find_case_by_digest(db_session, digest)
    assert found is not None
    assert found.id == case.id


def test_entity_upsert_is_idempotent(db_session):
    first = repo.upsert_entities(db_session, [("phone", "+91 98765 43210")])
    second = repo.upsert_entities(db_session, [("phone", "9876543210")])
    rows = db_session.execute(select(Entity)).scalars().all()
    assert len(rows) == 1
    assert rows[0].times_seen == 2
    assert first["9876543210"].id == second["9876543210"].id


def test_invalid_entities_skipped(db_session):
    resolved = repo.upsert_entities(
        db_session, [("phone", "call-now"), ("account", "!!")]
    )
    assert resolved == {}


def test_correlation_requires_two_case_kinds(db_session):
    ent = repo.upsert_entities(db_session, [("phone", "9876543210")])["9876543210"]
    scam = repo.create_case(db_session, kind="SCAM", input_digest="d1")
    fraud = repo.create_case(db_session, kind="FRAUD", input_digest="d2")
    solo = repo.create_case(db_session, kind="SCAM", input_digest="d3")
    for case in (scam, fraud, solo):
        repo.link_case_entities(db_session, case.id, [ent])
        repo.record_event(
            db_session,
            case_id=case.id,
            module=case.kind,
            event_type="test",
            risk_level="HIGH",
            summary="s",
        )
    correlations = repo.correlated_entity_values(db_session)
    assert len(correlations) == 1
    assert correlations[0]["modules_seen"] == 2


def test_job_lifecycle(db_session):
    job = repo.create_job(db_session, kind="analysis", payload={"x": 1})
    claimed = repo.claim_job(db_session, job.id)
    assert claimed is not None and claimed.status == "running"
    assert repo.claim_job(db_session, job.id) is None
    repo.complete_job(db_session, claimed, {"ok": True})
    assert claimed.status == "done"
    failed = repo.create_job(db_session, kind="analysis", payload={})
    f_claimed = repo.claim_job(db_session, failed.id)
    repo.fail_job(db_session, f_claimed, "boom")
    assert f_claimed.status == "error"
    retriable = repo.claim_job(db_session, failed.id)
    assert retriable is not None


def test_module_stats_aggregation(db_session):
    case = repo.create_case(db_session, kind="SCAM", input_digest="s1")
    repo.record_event(
        db_session,
        case_id=case.id,
        module="SCAMWatch",
        event_type="scam",
        risk_level="CRITICAL",
        summary="x",
    )
    stats = repo.module_stats(db_session)
    assert stats["total_events"] == 1
    assert stats["events_by_module"]["SCAMWatch"] == 1
    assert stats["critical_risk_count"] == 1


def test_trace_append_ordered(db_session):
    case = repo.create_case(db_session, kind="FRAUD", input_digest="f1")
    for seq, stage in enumerate(["ingest", "extract", "verify"], start=1):
        repo.append_trace(db_session, case.id, seq, stage)
    traces = sorted(case.traces, key=lambda t: t.seq)
    assert [t.stage for t in traces] == ["ingest", "extract", "verify"]
