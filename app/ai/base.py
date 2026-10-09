from __future__ import annotations

from abc import ABC, abstractmethod
from app.models import Article, Classification, ClusterDecision, ExtractedEvent, GeneratedPackage, Event, PackageCheck, ClusterBatch


class AIProvider(ABC):
    @abstractmethod
    def classify(self, article: Article) -> Classification: ...

    @abstractmethod
    def same_event(self, left: Article, right: Article) -> ClusterDecision: ...

    @abstractmethod
    def extract_event(self, articles: list[Article], event_id: str) -> ExtractedEvent: ...

    @abstractmethod
    def generate_package(self, events: list[ExtractedEvent], control_time: str) -> GeneratedPackage: ...

    def classify_many(self, articles: list[Article]) -> list[Classification]:
        return [self.classify(a) for a in articles]

    def extract_events(self, clusters: list[tuple[str, list[Article]]]) -> dict[str, ExtractedEvent]:
        return {event_id: self.extract_event(articles, event_id) for event_id, articles in clusters}

    def cluster_all(self, articles: list[Article], buckets: dict[str, list[Article]]) -> ClusterBatch:
        raise AttributeError("AI adapter does not implement cluster_all")

    def regenerate_package(self, events: list[ExtractedEvent], control_time: str, previous: GeneratedPackage, errors: list[str]) -> GeneratedPackage:
        """Fallback regeneration for providers without feedback-aware generation."""
        return self.generate_package(events, control_time)

    def verify_package(self, package: GeneratedPackage, events: list[Event]) -> PackageCheck:
        # Deterministic fallback; OpenAI adapter overrides this with one batched LLM check.
        from app.validation.evidence import deterministic_package_check
        return deterministic_package_check(package, events)
