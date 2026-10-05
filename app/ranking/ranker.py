from __future__ import annotations
from app.models import Event


def score_event(event: Event) -> float:
    return (
        0.30 * event.impact
        + 0.25 * event.scale
        + 0.20 * event.urgency
        + 0.15 * event.relevance
        + 0.10 * event.evidence_quality
    )

def rank_events(events: list[Event], limit: int = 5) -> list[Event]:
    for e in events:
        e.score = round(score_event(e), 3)
        e.selection_reason = (
            f"Приоритет связан с последствиями={e.impact}/5, масштабом={e.scale}/5, "
            f"срочностью={e.urgency}/5 и релевантностью={e.relevance}/5."
        )
    return sorted(events, key=lambda x: (-x.score, x.title))[:limit]
