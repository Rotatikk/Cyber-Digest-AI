from __future__ import annotations

from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, HttpUrl

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

class GeneratedPackage(BaseModel):
    digest: str
    post: str
    email_subject: str

class LogEntry(BaseModel):
    article_id: str
    status: Status
    event_group: str | None = None
    reason: str = ""
    errors: list[str] = Field(default_factory=list)
