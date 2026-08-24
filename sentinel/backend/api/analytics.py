"""Analytics API v2.

Every number here is computed from persisted events with real timestamps.
The legacy fabricated timeline (pseudo-random bucket spreading) is gone.
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from backend.db import repo
from backend.db.base import session_scope
from backend.db.models import Case, Event

router = APIRouter()


@router.get("/stats")
def stats():
    with session_scope() as session:
        base = repo.module_stats(session)
        day_ago = datetime.now(timezone.utc) - timedelta(hours=24)
        today_count = session.execute(
            select(func.count(Event.id)).where(Event.occurred_at >= day_ago)
        ).scalar_one()
        case_count = session.execute(select(func.count(Case.id))).scalar_one()
        return {**base, "events_last_24h": today_count, "total_cases": case_count}


@router.get("/recent")
def recent(limit: int = Query(default=20, ge=1, le=100)):
    with session_scope() as session:
        events = repo.recent_events(session, limit=limit)
        return {
            "count": len(events),
            "events": [
                {
                    "id": e.id,
                    "case_id": e.case_id,
                    "module": e.module,
                    "event_type": e.event_type,
                    "risk_level": e.risk_level,
                    "summary": e.summary[:200],
                    "occurred_at": e.occurred_at.isoformat(),
                }
                for e in events
            ],
        }


@router.get("/timeline")
def timeline(hours: int = Query(default=24, ge=1, le=720)):
    """Real hourly event buckets from stored timestamps."""
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    with session_scope() as session:
        rows = session.execute(
            select(Event.occurred_at, Event.risk_level).where(
                Event.occurred_at >= since
            )
        ).all()

    buckets: dict[str, dict[str, int]] = {}
    for occurred_at, risk in rows:
        hour_key = occurred_at.strftime("%Y-%m-%dT%H:00")
        bucket = buckets.setdefault(hour_key, {"total": 0})
        bucket["total"] += 1
        bucket[risk.lower()] = bucket.get(risk.lower(), 0) + 1

    return {
        "window_hours": hours,
        "buckets": [{"hour": k, **v} for k, v in sorted(buckets.items())],
    }


@router.get("/correlations")
def correlations(limit: int = Query(default=10, ge=1, le=50)):
    with session_scope() as session:
        return {"correlations": repo.correlated_entity_values(session, limit=limit)}
