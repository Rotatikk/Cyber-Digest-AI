from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from app.models import Article
from app.config import MSK

def filter_period(articles: list[Article], control_time: datetime) -> tuple[list[Article], dict[str, str]]:
    end = control_time.astimezone(MSK)
    start = end - timedelta(hours=24)
    kept: list[Article] = []
    reasons: dict[str, str] = {}
    for article in articles:
        if article.published_at is None:
            reasons[article.id] = "date_unconfirmed"
            continue
        published = article.published_at.astimezone(MSK)
        if start < published <= end:
            kept.append(article)
        else:
            reasons[article.id] = "outside_24h_period"
    return kept, reasons
