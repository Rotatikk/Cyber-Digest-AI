from __future__ import annotations

from dataclasses import dataclass
import re
from app.ai.base import AIProvider
from app.models import Article

@dataclass
class Cluster:
    id: str
    articles: list[Article]


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

    buckets: dict[str, list[Article]] = {}
    unkeyed: list[Article] = []
    for article in articles:
        keys = _entity_keys(article)
        if keys:
            # Основной ключ = первый стабильный entity key в отсортированном наборе.
            key = sorted(keys)[0]
            buckets.setdefault(f"entity:{key}", []).append(article)
        else:
            unkeyed.append(article)

    if unkeyed:
        buckets["general"] = unkeyed

    clusters: list[Cluster] = []
    for bucket_id, bucket in buckets.items():
        if len(bucket) == 1:
            clusters.append(Cluster(id=f"event_{len(clusters)+1}", articles=bucket))
            continue
        if hasattr(ai, "cluster_group"):
            batch = ai.cluster_group(bucket, bucket_id.replace(":", "_"))
            seen: set[str] = set()
            for group in batch.groups:
                group_articles = [a for a in bucket if a.id in group.article_ids and a.id not in seen]
                if group_articles:
                    seen.update(a.id for a in group_articles)
                    clusters.append(Cluster(id=group.cluster_id, articles=group_articles))
            # Если модель пропустила материал, не теряем его.
            for article in bucket:
                if article.id not in seen:
                    clusters.append(Cluster(id=f"event_{len(clusters)+1}", articles=[article]))
        else:
            # Без batch API сохраняем совместимость, но не сравниваем каждый со всеми.
            first = bucket[0]
            current = Cluster(id=f"event_{len(clusters)+1}", articles=[first])
            clusters.append(current)
            for article in bucket[1:]:
                decision = ai.same_event(article, first)
                if decision.same_event:
                    current.articles.append(article)
                else:
                    clusters.append(Cluster(id=f"event_{len(clusters)+1}", articles=[article]))
    return clusters
