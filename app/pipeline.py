from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from app.ai.factory import get_ai
from app.config import Settings, parse_control_time
from app.clustering.events import cluster_articles
from app.filtering.date_filter import filter_period
from app.filtering.relevance import lexical_candidate
from app.ingestion.loader import load_articles
from app.logging.audit import write_log
from app.models import Event, LogEntry, ExtractedEvent
from app.ranking.ranker import rank_events
from app.validation.checks import validate_package

CLASSIFY_BATCH_SIZE = 25
MAX_PRESELECT_CLUSTERS = 8

def run(input_path: str, control_time: str, settings: Settings | None = None, output_dir: str = "output"):
    settings = settings or Settings()
    control = parse_control_time(control_time)
    articles = load_articles(input_path)
    logs: list[LogEntry] = []

    in_period, date_reasons = filter_period(articles, control)
    for a in articles:
        if a.id in date_reasons:
            logs.append(LogEntry(article_id=a.id, status="excluded", reason=date_reasons[a.id]))

    candidates: list = []
    for a in in_period:
        if not a.title.strip() and not a.text.strip():
            logs.append(LogEntry(article_id=a.id, status="insufficient_data", reason="empty_title_and_text"))
            continue
        if not a.text.strip():
            logs.append(LogEntry(article_id=a.id, status="insufficient_data", reason="text_missing"))
            continue
        if lexical_candidate(a):
            candidates.append(a)
        else:
            logs.append(LogEntry(article_id=a.id, status="excluded", reason="lexical_pre_filter"))

    ai = get_ai(settings)

    # Одно обращение на пачку вместо отдельного вызова для каждой статьи.
    relevant: list = []
    for start in range(0, len(candidates), CLASSIFY_BATCH_SIZE):
        chunk = candidates[start:start + CLASSIFY_BATCH_SIZE]
        results = ai.classify_many(chunk)
        for a, result in zip(chunk, results):
            if result.relevant:
                relevant.append(a)
            else:
                logs.append(LogEntry(article_id=a.id, status="excluded", reason=result.reason))

    clusters = cluster_articles(relevant, ai)

    # Предварительно ограничиваем число групп, которые попадут в дорогое извлечение.
    prelim = []
    for cluster in clusters:
        text = " ".join((a.title + " " + a.text) for a in cluster.articles).lower()
        severity = sum(term in text for term in ["ransomware", "шифровальщик", "критическ", "zero-day", "0-day", "ddos", "утечк", "компрометац", "rce"])
        score = len(cluster.articles) * 2 + severity
        prelim.append((score, cluster))
    prelim.sort(key=lambda x: (-x[0], x[1].id))
    selected_clusters = [c for _, c in prelim[:MAX_PRESELECT_CLUSTERS]]

    extracted_map = ai.extract_events([(c.id, c.articles) for c in selected_clusters])
    events: list[Event] = []
    for cluster in selected_clusters:
        extracted = extracted_map[cluster.id]
        sources = [
            {
                "article_id": a.id,
                "source": a.source,
                "published_at": a.published_at,
                "url": a.url,
            }
            for a in cluster.articles
        ]
        event = Event(
            id=cluster.id,
            title=extracted.title,
            article_ids=[a.id for a in cluster.articles],
            facts=extracted.facts,
            affected_entities=extracted.affected_entities,
            consequences=extracted.consequences,
            caveats=extracted.caveats,
            sources=sources,
            relevance=extracted.relevance,
            impact=extracted.impact,
            scale=extracted.scale,
            urgency=extracted.urgency,
            evidence_quality=extracted.evidence_quality,
        )
        events.append(event)
        for a in cluster.articles:
            logs.append(LogEntry(article_id=a.id, status="included", event_group=cluster.id, reason="relevant_event"))

    # События, которые не попали в дорогую extraction-фазу, всё равно отражаем в журнале.
    selected_ids = {c.id for c in selected_clusters}
    for cluster in clusters:
        if cluster.id not in selected_ids:
            for a in cluster.articles:
                logs.append(LogEntry(article_id=a.id, status="excluded", event_group=cluster.id, reason="not_in_extraction_budget"))

    selected = rank_events(events, 5)
    selected_payload = [
        ExtractedEvent(
            title=e.title, facts=e.facts, sources=e.sources, affected_entities=e.affected_entities,
            consequences=e.consequences, caveats=e.caveats, relevance=e.relevance, impact=e.impact,
            scale=e.scale, urgency=e.urgency, evidence_quality=e.evidence_quality,
        )
        for e in selected
    ]
    package = ai.generate_package(selected_payload, control.isoformat())
    errors = validate_package(package, selected)
    if errors:
        raise RuntimeError(f"Validation failed: {errors}")

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "digest.txt").write_text(package.digest, encoding="utf-8")
    (out / "post.txt").write_text(package.post, encoding="utf-8")
    (out / "email_subject.txt").write_text(package.email_subject, encoding="utf-8")
    write_log(logs, out / "processing_log.csv")

    usage = {"ai_calls": getattr(ai, "calls", None), "usage": getattr(ai, "usage", None)}
    (out / "ai_usage.json").write_text(json.dumps(usage, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "articles_total": len(articles), "articles_in_period": len(in_period),
        "relevant_articles": len(relevant), "events": events, "selected": selected,
        "package": package, "validation_errors": errors, "ai_usage": usage,
    }
