from __future__ import annotations

from abc import ABC, abstractmethod
from app.models import Article, Classification, ClusterDecision, ExtractedEvent, GeneratedPackage

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
