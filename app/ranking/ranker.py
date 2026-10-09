from __future__ import annotations

from app.models import Event


def score_event(event: Event) -> float:
    return round(
        0.30 * event.impact
        + 0.25 * event.scale
        + 0.20 * event.urgency
        + 0.15 * event.relevance
        + 0.10 * event.evidence_quality,
        3,
    )


def rank_events(events: list[Event], limit: int = 5) -> list[Event]:
    for e in events:
        e.score = score_event(e)
        e.selection_reason = (
            f"Приоритет: последствия {e.impact}/5 ({e.impact_evidence or 'нет отдельного пояснения'}); "
            f"масштаб {e.scale}/5 ({e.scale_evidence or 'нет данных о масштабе'}); "
            f"срочность {e.urgency}/5 ({e.urgency_evidence or 'нет отдельного пояснения'}); "
            f"релевантность {e.relevance}/5 ({e.relevance_evidence or 'связь с задачами читателей не раскрыта'}); "
            f"качество доказательств {e.evidence_quality}/5 ({e.evidence_quality_evidence or 'оценка по наличию источников и фактов'})."
        )
    return sorted(events, key=lambda x: (-x.score, x.title.lower()))[:limit]
