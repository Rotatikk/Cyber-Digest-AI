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
