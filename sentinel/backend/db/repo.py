"""Repository functions. Pipelines and API depend on these, not on ORM details."""

import hashlib
from datetime import datetime, timezone
from typing import Iterable, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.core.normalize import normalize_entity
from backend.db.models import Case, CaseEntity, Entity, Event, Job, Trace, new_id


def digest_input(kind: str, payload: dict) -> str:
    canonical = repr(sorted(payload.items(), key=lambda kv: kv[0]))
    return hashlib.sha256(f"{kind}|{canonical}".encode()).hexdigest()


def find_case_by_digest(session: Session, digest: str) -> Case | None:
    return (
        session.execute(
            select(Case)
            .where(Case.input_digest == digest)
            .order_by(Case.created_at.desc())
        )
        .scalars()
        .first()
    )


def create_case(
    session: Session,
    *,
    kind: str,
    input_digest: str,
    redacted_input: str = "",
    source_channel: str = "unknown",
    language: str = "en",
) -> Case:
    case = Case(
        id=new_id("case"),
        kind=kind,
        input_digest=input_digest,
        redacted_input=redacted_input,
        source_channel=source_channel,
        language=language,
    )
    session.add(case)
    session.flush()
    return case


def append_trace(
    session: Session, case_id: str, seq: int, stage: str, **kwargs
) -> None:
    session.add(Trace(case_id=case_id, seq=seq, stage=stage, **kwargs))


def upsert_entities(
    session: Session, candidates: Iterable[tuple[str, str]]
) -> dict[str, Entity]:
    """candidates: raw (type, value) pairs; returns map norm_value -> Entity."""
    resolved: dict[str, Entity] = {}
    for etype, raw in candidates:
        normalized = normalize_entity(etype, raw)
        if normalized is None:
            continue
        etype, value = normalized
        entity = session.execute(
            select(Entity).where(Entity.etype == etype, Entity.value_norm == value)
        ).scalar_one_or_none()
        if entity is None:
            entity = Entity(
                id=new_id("ent"), etype=etype, value_norm=value, value_display=raw[:140]
            )
            session.add(entity)
            session.flush()
        else:
            entity.times_seen += 1
            entity.last_seen = datetime.now(timezone.utc)
        resolved[value] = entity
    return resolved


def link_case_entities(
    session: Session, case_id: str, entities: Iterable[Entity], role: str = "referenced"
) -> None:
    for entity in entities:
        exists = session.get(CaseEntity, (case_id, entity.id))
        if exists is None:
            session.add(CaseEntity(case_id=case_id, entity_id=entity.id, role=role))


def record_event(
    session: Session,
    *,
    case_id: str,
    module: str,
    event_type: str,
    risk_level: str,
    summary: str,
    payload: dict | None = None,
) -> Event:
    event = Event(
        id=new_id("evt"),
        case_id=case_id,
        module=module,
        event_type=event_type,
        risk_level=risk_level,
        summary=summary,
        payload=payload or {},
    )
    session.add(event)
    return event


def finish_case(
    session: Session,
    case: Case,
    *,
    status: str,
    risk_level: str | None,
    risk_score: float | None,
    confidence: float | None,
    verdict: dict | None,
) -> None:
    case.status = status
    case.risk_level = risk_level
    case.risk_score = risk_score
    case.confidence = confidence
    case.verdict = verdict


def create_job(session: Session, *, kind: str, payload: dict) -> Job:
    job = Job(id=new_id("job"), kind=kind, payload=payload)
    session.add(job)
    session.flush()
    return job


def claim_job(session: Session, job_id: str) -> Job | None:
    job = session.get(Job, job_id)
    if job is None or job.status not in ("queued", "error"):
        return None
    job.status = "running"
    job.started_at = datetime.now(timezone.utc)
    job.attempts += 1
    return job


def complete_job(session: Session, job: Job, result: dict) -> None:
    job.status = "done"
    job.result = result
    job.finished_at = datetime.now(timezone.utc)


def fail_job(session: Session, job: Job, error: str) -> None:
    job.status = "error"
    job.error = error[:2000]
    job.finished_at = datetime.now(timezone.utc)


def recent_events(session: Session, limit: int = 20) -> Sequence[Event]:
    return (
        session.execute(select(Event).order_by(Event.occurred_at.desc()).limit(limit))
        .scalars()
        .all()
    )


def module_stats(session: Session) -> dict:
    rows = session.execute(
        select(Event.module, func.count(Event.id)).group_by(Event.module)
    ).all()
    stats = {module: count for module, count in rows}
    high_risk = session.execute(
        select(func.count(Event.id)).where(
            Event.risk_level.in_(["HIGH", "CRITICAL", "SUSPECT"])
        )
    ).scalar_one()
    critical = session.execute(
        select(func.count(Event.id)).where(
            Event.risk_level.in_(["CRITICAL", "COUNTERFEIT"])
        )
    ).scalar_one()
    return {
        "events_by_module": stats,
        "total_events": sum(stats.values()),
        "high_risk_count": high_risk,
        "critical_risk_count": critical,
    }


def correlated_entity_values(session: Session, limit: int = 10) -> list[dict]:
    """Entities referenced by cases from >=2 distinct case kinds (modules)."""
    module_count = func.count(func.distinct(Case.kind)).label("module_count")
    stmt = (
        select(Entity.value_norm, Entity.etype, Entity.value_display, module_count)
        .join(CaseEntity, CaseEntity.entity_id == Entity.id)
        .join(Case, Case.id == CaseEntity.case_id)
        .group_by(Entity.id, Entity.value_norm, Entity.etype, Entity.value_display)
        .having(module_count >= 2)
        .order_by(module_count.desc())
        .limit(limit)
    )
    rows = session.execute(stmt).all()
    return [
        {
            "value": r.value_display or r.value_norm,
            "type": r.etype,
            "modules_seen": r.module_count,
        }
        for r in rows
    ]
