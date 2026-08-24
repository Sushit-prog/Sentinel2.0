"""ORM models: cases, events, entities, jobs, traces."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class Base(DeclarativeBase):
    pass


class Case(Base):
    """A single investigation/analysis unit across all modules."""

    __tablename__ = "cases"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    kind: Mapped[str] = mapped_column(String(20), index=True)
    status: Mapped[str] = mapped_column(String(20), default="open")
    source_channel: Mapped[str] = mapped_column(String(30), default="unknown")
    language: Mapped[str] = mapped_column(String(10), default="en")
    input_digest: Mapped[str] = mapped_column(String(64), index=True)
    redacted_input: Mapped[str] = mapped_column(Text, default="")
    risk_level: Mapped[str | None] = mapped_column(String(12), nullable=True)
    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    verdict: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    traces: Mapped[list["Trace"]] = relationship(
        back_populates="case", order_by="Trace.seq"
    )


class Trace(Base):
    """Append-only audit trail: one row per pipeline stage execution."""

    __tablename__ = "traces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[str] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), index=True
    )
    seq: Mapped[int] = mapped_column(Integer)
    stage: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20), default="ok")
    model: Mapped[str | None] = mapped_column(String(60), nullable=True)
    route: Mapped[str | None] = mapped_column(String(10), nullable=True)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    est_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    case: Mapped[Case] = relationship(back_populates="traces")


class Entity(Base):
    """Globally resolved entity (phone/account/device) - the correlation join key."""

    __tablename__ = "entities"
    __table_args__ = (
        UniqueConstraint("etype", "value_norm", name="uq_entity_type_value"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    etype: Mapped[str] = mapped_column(String(20))
    value_norm: Mapped[str] = mapped_column(String(120), index=True)
    value_display: Mapped[str] = mapped_column(String(140), default="")
    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    times_seen: Mapped[int] = mapped_column(Integer, default=1)


class CaseEntity(Base):
    __tablename__ = "case_entities"
    __table_args__ = (
        Index("ix_case_entities_entity", "entity_id"),
        UniqueConstraint("case_id", "entity_id", name="uq_case_entity"),
    )

    case_id: Mapped[str] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), primary_key=True
    )
    entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), primary_key=True)
    role: Mapped[str] = mapped_column(String(20), default="referenced")


class Event(Base):
    """Intelligence event emitted by a completed case."""

    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    case_id: Mapped[str] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), index=True
    )
    module: Mapped[str] = mapped_column(String(20), index=True)
    event_type: Mapped[str] = mapped_column(String(40))
    risk_level: Mapped[str] = mapped_column(String(12), default="UNKNOWN")
    summary: Mapped[str] = mapped_column(Text, default="")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )


class Job(Base):
    """Durable background job record for long-running analyses."""

    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    kind: Mapped[str] = mapped_column(String(30), index=True)
    status: Mapped[str] = mapped_column(String(15), default="queued", index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
