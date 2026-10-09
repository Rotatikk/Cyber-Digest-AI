from __future__ import annotations

from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field

Status = Literal["included", "excluded", "merged", "error", "insufficient_data"]


class Article(BaseModel):
    id: str
    title: str = ""
    text: str = ""
    source: str = ""
    url: str = ""
    published_at: datetime | None = None


class Fact(BaseModel):
    text: str
    article_id: str
    evidence: str
    confidence: Literal["high", "medium", "low"] = "high"


class SourceRef(BaseModel):
    article_id: str
    source: str
    published_at: datetime | None
    url: str


class ScoreEvidence(BaseModel):
    score: int = Field(default=0, ge=0, le=5)
    evidence: str = ""


class Event(BaseModel):
    id: str
    title: str
    article_ids: list[str] = Field(default_factory=list)
    facts: list[Fact] = Field(default_factory=list)
    affected_entities: list[str] = Field(default_factory=list)
    consequences: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    sources: list[SourceRef] = Field(default_factory=list)
    relevance: int = Field(default=0, ge=0, le=5)
    impact: int = Field(default=0, ge=0, le=5)
    scale: int = Field(default=0, ge=0, le=5)
    urgency: int = Field(default=0, ge=0, le=5)
    evidence_quality: int = Field(default=0, ge=0, le=5)
    impact_evidence: str = ""
    scale_evidence: str = ""
    urgency_evidence: str = ""
    relevance_evidence: str = ""
    evidence_quality_evidence: str = ""
    score: float = 0.0
    selection_reason: str = ""


class Classification(BaseModel):
    relevant: bool
    reason: str


class ClusterDecision(BaseModel):
    same_event: bool
    reason: str


class ExtractedEvent(BaseModel):
    title: str
    facts: list[Fact]
    sources: list[SourceRef] = Field(default_factory=list)
    affected_entities: list[str]
    consequences: list[str]
    caveats: list[str]
    relevance: int = Field(ge=0, le=5)
    impact: int = Field(ge=0, le=5)
    scale: int = Field(ge=0, le=5)
    urgency: int = Field(ge=0, le=5)
    evidence_quality: int = Field(ge=0, le=5)
    impact_evidence: str = ""
    scale_evidence: str = ""
    urgency_evidence: str = ""
    relevance_evidence: str = ""
    evidence_quality_evidence: str = ""


class GeneratedPackage(BaseModel):
    digest: str
    post: str
    email_subject: str


class PackageCheck(BaseModel):
    passed: bool
    violations: list[str] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    conflicting_claims: list[str] = Field(default_factory=list)
    event_ids_in_digest: list[str] = Field(default_factory=list)
    event_ids_in_post: list[str] = Field(default_factory=list)
    numbers_checked: int = 0
    urls_checked: int = 0


class ValidationReport(BaseModel):
    passed: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    package_check: PackageCheck | None = None
    events_selected: int = 0


class RunManifest(BaseModel):
    run_id: str
    started_at: str
    finished_at: str
    control_time: str
    period_start: str
    period_end: str
    ai_mode: str
    model: str
    base_url_set: bool = False
    prompt_version: str = "2.0"
    max_ai_calls: int = 0
    max_preselect_clusters: int = 6
    ai_calls: int = 0
    usage: dict = Field(default_factory=dict)
    articles_total: int = 0
    articles_in_period: int = 0
    relevant_articles: int = 0
    clusters: int = 0
    events_extracted: int = 0
    events_selected: int = 0
    validation_passed: bool = False
    validation_errors: list[str] = Field(default_factory=list)
    validation_warnings: list[str] = Field(default_factory=list)


class LogEntry(BaseModel):
    article_id: str
    status: Status
    event_group: str | None = None
    reason: str = ""
    errors: list[str] = Field(default_factory=list)


class ClassificationItem(BaseModel):
    article_id: str
    relevant: bool
    reason: str


class ClassificationBatch(BaseModel):
    items: list[ClassificationItem]


class ClusterGroup(BaseModel):
    cluster_id: str
    article_ids: list[str]
    reason: str = ""
    preliminary_relevance: int = Field(default=0, ge=0, le=5)
    preliminary_impact: int = Field(default=0, ge=0, le=5)
    preliminary_scale: int = Field(default=0, ge=0, le=5)
    preliminary_urgency: int = Field(default=0, ge=0, le=5)


class ClusterBatch(BaseModel):
    groups: list[ClusterGroup]
