from __future__ import annotations

from dataclasses import dataclass
import re

from app.ai.base import AIProvider
from app.models import Article, ClusterBatch, ClusterGroup


@dataclass
class Cluster:
    id: str
    articles: list[Article]
    reason: str = ""
    preliminary_relevance: int = 0
    preliminary_impact: int = 0
    preliminary_scale: int = 0
    preliminary_urgency: int = 0

    @property
    def preliminary_score(self) -> float:
        return (
            0.35 * self.preliminary_impact
            + 0.25 * self.preliminary_scale
            + 0.20 * self.preliminary_urgency
            + 0.20 * self.preliminary_relevance
        )


def _entity_keys(article: Article) -> set[str]:
    text = f"{article.title} {article.text}"
    keys: set[str] = set()
    patterns = [
        r"(?:компани[яи]|организаци[яи]|производитель|vendor)\s+([A-ZА-ЯЁ][\w-]{2,})",
        r"(?:продукт[еа]?|product|сервис[аеи]?|portal|портал[аеи]?)\s+([A-ZА-ЯЁ][\w-]{2,})",
        r"\b(CVE-\d{4}-\d{4,})\b",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE | re.UNICODE):
            keys.add(match.group(1).lower())
    return keys


def cluster_articles(articles: list[Article], ai: AIProvider) -> list[Cluster]:
    if not articles:
        return []

    # Формируем candidate buckets детерминированно, но выполняем лишь один LLM-вызов
    # для окончательного разбиения всех неодиночных групп.
    buckets: dict[str, list[Article]] = {}
    for article in articles:
        keys = _entity_keys(article)
        key = sorted(keys)[0] if keys else "general"
        buckets.setdefault(f"entity:{key}", []).append(article)

    if hasattr(ai, "cluster_all"):
        batch = ai.cluster_all(articles, buckets)
        by_id = {a.id: a for a in articles}
        clusters: list[Cluster] = []
        seen: set[str] = set()
        for group in batch.groups:
            group_articles = [by_id[i] for i in group.article_ids if i in by_id and i not in seen]
            if not group_articles:
                continue
            seen.update(a.id for a in group_articles)
            clusters.append(
                Cluster(
                    id=group.cluster_id,
                    articles=group_articles,
                    reason=group.reason,
                    preliminary_relevance=group.preliminary_relevance,
                    preliminary_impact=group.preliminary_impact,
                    preliminary_scale=group.preliminary_scale,
                    preliminary_urgency=group.preliminary_urgency,
                )
            )
        for article in articles:
            if article.id not in seen:
                clusters.append(Cluster(id=f"event_{len(clusters)+1}", articles=[article], reason="Не распределено моделью"))
        return clusters

    # Fallback для очень простых/mock адаптеров.
    clusters: list[Cluster] = []
    for bucket_id, bucket in buckets.items():
        if len(bucket) == 1:
            clusters.append(Cluster(id=f"event_{len(clusters)+1}", articles=bucket, reason="Одиночная публикация"))
            continue
        if hasattr(ai, "cluster_group"):
            batch = ai.cluster_group(bucket, bucket_id.replace(":", "_"))
            seen: set[str] = set()
            for group in batch.groups:
                group_articles = [a for a in bucket if a.id in group.article_ids and a.id not in seen]
                if group_articles:
                    seen.update(a.id for a in group_articles)
                    clusters.append(Cluster(
                        id=group.cluster_id,
                        articles=group_articles,
                        reason=group.reason,
                        preliminary_relevance=group.preliminary_relevance,
                        preliminary_impact=group.preliminary_impact,
                        preliminary_scale=group.preliminary_scale,
                        preliminary_urgency=group.preliminary_urgency,
                    ))
            for article in bucket:
                if article.id not in seen:
                    clusters.append(Cluster(id=f"event_{len(clusters)+1}", articles=[article], reason="Fallback singleton"))
        else:
            current = Cluster(id=f"event_{len(clusters)+1}", articles=[bucket[0]], reason="Fallback")
            clusters.append(current)
            for article in bucket[1:]:
                if ai.same_event(article, bucket[0]).same_event:
                    current.articles.append(article)
                else:
                    clusters.append(Cluster(id=f"event_{len(clusters)+1}", articles=[article], reason="Fallback split"))
    return clusters
