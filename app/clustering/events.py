from __future__ import annotations

from dataclasses import dataclass
from app.ai.base import AIProvider
from app.models import Article, LogEntry

@dataclass
class Cluster:
    id: str
    articles: list[Article]

def cluster_articles(articles: list[Article], ai: AIProvider) -> list[Cluster]:
    clusters: list[Cluster] = []
    for article in articles:
        placed = False
        for cluster in clusters:
            decision = ai.same_event(article, cluster.articles[0])
            if decision.same_event:
                cluster.articles.append(article)
                placed = True
                break
        if not placed:
            clusters.append(Cluster(id=f"event_{len(clusters)+1}", articles=[article]))
    return clusters
