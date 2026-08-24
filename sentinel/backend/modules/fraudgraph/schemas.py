"""Typed contracts for the FRAUDGraph network pipeline."""

from enum import Enum

from pydantic import BaseModel, Field


class EntityType(str, Enum):
    PHONE = "phone"
    ACCOUNT = "account"
    DEVICE = "device"


class EntityRole(str, Enum):
    SUSPECT = "suspect"
    VICTIM = "victim"
    REFERENCED = "referenced"


class StructuredEntity(BaseModel):
    etype: EntityType
    value: str = Field(min_length=4, max_length=60)
    role: EntityRole = EntityRole.REFERENCED
    label: str | None = Field(default=None, max_length=80)


class RelationInput(BaseModel):
    source_index: int = Field(ge=0, le=200)
    target_index: int = Field(ge=0, le=200)
    relation: str = Field(default="linked_to", max_length=40)


class NetworkInput(BaseModel):
    """Either a free-text victim statement, structured records, or both."""

    text: str | None = Field(default=None, max_length=6000)
    entities: list[StructuredEntity] = Field(default_factory=list, max_length=100)
    relations: list[RelationInput] = Field(default_factory=list, max_length=200)


class ExtractedEntities(BaseModel):
    """Quarantined-stage output from free-text statements."""

    phones: list[str] = Field(default_factory=list, max_length=20)
    accounts: list[str] = Field(default_factory=list, max_length=20)
    devices: list[str] = Field(default_factory=list, max_length=20)
    victims: list[str] = Field(default_factory=list, max_length=30)
    relations: list[RelationInput] = Field(default_factory=list, max_length=60)


class NodeOut(BaseModel):
    key: str
    etype: str
    display: str = ""
    role: str = "referenced"
    prior_sightings: int = 0
    cross_module: bool = False
    degree: int = 0


class EdgeOut(BaseModel):
    source: str
    target: str
    relation: str


class ClusterOut(BaseModel):
    cluster_id: int
    size: int
    entity_types: dict[str, int]
    hub_key: str | None = None
    hub_centrality: float = 0.0
    cross_module_hits: int = 0
    risk_contribution: float = 0.0


class FraudAnalysisResponse(BaseModel):
    case_id: str
    status: str
    node_count: int
    edge_count: int
    cluster_count: int
    risk_level: str
    risk_score: float
    confidence: float
    clusters: list[ClusterOut]
    nodes: list[NodeOut]
    edges: list[EdgeOut]
    correlations: list[dict]
    reasoning: str
    degraded: bool = False
    total_cost_usd: float = 0.0
    latency_ms: int = 0
