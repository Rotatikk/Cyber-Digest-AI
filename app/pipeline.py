from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from app.ai.factory import get_ai
from app.config import Settings, parse_control_time
from app.clustering.events import cluster_articles
from app.filtering.date_filter import filter_period
from app.filtering.relevance import lexical_candidate
from app.ingestion.loader import load_articles
from app.logging.audit import write_log
from app.models import Event, LogEntry, ExtractedEvent, RunManifest
from app.ranking.ranker import rank_events
from app.validation.checks import validate_report
from app.generation.repair import repair_generated_package

CLASSIFY_BATCH_SIZE = 30
PROMPT_VERSION = "2.1"


def _event_from_extracted(cluster, extracted: ExtractedEvent) -> Event:
    sources = [
        {
            "article_id": a.id,
            "source": a.source,
            "published_at": a.published_at,
            "url": a.url,
        }
        for a in cluster.articles
    ]
    return Event(
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
        impact_evidence=extracted.impact_evidence,
        scale_evidence=extracted.scale_evidence,
        urgency_evidence=extracted.urgency_evidence,
        relevance_evidence=extracted.relevance_evidence,
        evidence_quality_evidence=extracted.evidence_quality_evidence,
    )


def _cost(usage: dict, settings: Settings) -> float | None:
    if settings.input_price_per_1m is None or settings.output_price_per_1m is None:
        return None
    return round(
        usage.get("input_tokens", 0) / 1_000_000 * settings.input_price_per_1m
        + usage.get("output_tokens", 0) / 1_000_000 * settings.output_price_per_1m,
        8,
    )


def run(input_path: str, control_time: str, settings: Settings | None = None, output_dir: str = "output"):
    settings = settings or Settings()
    control = parse_control_time(control_time)
    start_time = datetime.now().astimezone()
    run_id = uuid.uuid4().hex[:12]
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    articles = load_articles(input_path)
    logs: list[LogEntry] = []

    in_period, date_reasons = filter_period(articles, control)
    for a in articles:
        if a.id in date_reasons:
            logs.append(LogEntry(article_id=a.id, status="excluded", reason=date_reasons[a.id]))

    candidates = []
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

    relevant = []
    for start in range(0, len(candidates), CLASSIFY_BATCH_SIZE):
        chunk = candidates[start:start + CLASSIFY_BATCH_SIZE]
        results = ai.classify_many(chunk)
        for a, result in zip(chunk, results):
            if result.relevant:
                relevant.append(a)
            else:
                logs.append(LogEntry(article_id=a.id, status="excluded", reason=result.reason))

    if not relevant:
        events: list[Event] = []
        selected = []
        package = ai.generate_package([], control.isoformat())
        report = validate_report(package, [])
    else:
        clusters = cluster_articles(relevant, ai)

        prelim = sorted(clusters, key=lambda c: (-c.preliminary_score, c.id))
        selected_clusters = prelim[:settings.max_preselect_clusters]
        selected_cluster_ids = {c.id for c in selected_clusters}

        extracted_map = ai.extract_events([(c.id, c.articles) for c in selected_clusters])
        events = []
        for cluster in selected_clusters:
            extracted = extracted_map[cluster.id]
            events.append(_event_from_extracted(cluster, extracted))

        selected = rank_events(events, 5)
        selected_ids = {e.id for e in selected}
        for event in events:
            if event.id in selected_ids:
                first = True
                for article_id in event.article_ids:
                    if first:
                        logs.append(LogEntry(article_id=article_id, status="included", event_group=event.id, reason="top_5_selected"))
                        first = False
                    else:
                        logs.append(LogEntry(article_id=article_id, status="merged", event_group=event.id, reason="same_event_multiple_sources"))
            else:
                for article_id in event.article_ids:
                    logs.append(LogEntry(article_id=article_id, status="excluded", event_group=event.id, reason="not_top_5"))

        for cluster in clusters:
            if cluster.id not in selected_cluster_ids:
                for a in cluster.articles:
                    logs.append(LogEntry(article_id=a.id, status="excluded", event_group=cluster.id, reason="outside_extraction_budget"))

        selected_payload = [
            ExtractedEvent(
                title=e.title, facts=e.facts, sources=e.sources, affected_entities=e.affected_entities,
                consequences=e.consequences, caveats=e.caveats, relevance=e.relevance, impact=e.impact,
                scale=e.scale, urgency=e.urgency, evidence_quality=e.evidence_quality,
                impact_evidence=e.impact_evidence, scale_evidence=e.scale_evidence,
                urgency_evidence=e.urgency_evidence, relevance_evidence=e.relevance_evidence,
                evidence_quality_evidence=e.evidence_quality_evidence,
            )
            for e in selected
        ]
        package = ai.generate_package(selected_payload, control.isoformat())
        package = repair_generated_package(package, selected, control.isoformat())
        report = validate_report(package, selected)

        if settings.verify_with_ai and settings.ai_mode == "openai":
            package_check = ai.verify_package(package, selected)
            report.package_check = package_check
            if not package_check.passed:
                report.errors.extend(f"ai_fact_check:{x}" for x in package_check.violations)
                report.passed = False

    finished_time = datetime.now().astimezone()
    usage = {
        "ai_calls": getattr(ai, "calls", None),
        "usage": getattr(ai, "usage", None),
    }
    if isinstance(usage.get("usage"), dict):
        usage["estimated_cost"] = _cost(usage["usage"], settings)
    usage["verify_with_ai"] = settings.verify_with_ai
    usage["max_ai_calls"] = settings.max_ai_calls

    write_log(logs, out / "processing_log.csv")
    (out / "digest.txt").write_text(package.digest, encoding="utf-8")
    (out / "post.txt").write_text(package.post, encoding="utf-8")
    (out / "email_subject.txt").write_text(package.email_subject, encoding="utf-8")
    (out / "ai_usage.json").write_text(json.dumps(usage, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "events.json").write_text(
        json.dumps([e.model_dump(mode="json") for e in selected], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out / "validation_report.json").write_text(
        json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    manifest = RunManifest(
        run_id=run_id,
        started_at=start_time.isoformat(),
        finished_at=finished_time.isoformat(),
        control_time=control.isoformat(),
        period_start=(control - timedelta(hours=24)).isoformat(),
        period_end=control.isoformat(),
        ai_mode=settings.ai_mode,
        model=settings.openai_model if settings.ai_mode == "openai" else "mock",
        base_url_set=bool(settings.openai_base_url),
        prompt_version=settings.prompt_version or PROMPT_VERSION,
        max_ai_calls=settings.max_ai_calls,
        max_preselect_clusters=settings.max_preselect_clusters,
        ai_calls=usage.get("ai_calls") or 0,
        usage=usage,
        articles_total=len(articles),
        articles_in_period=len(in_period),
        relevant_articles=len(relevant),
        clusters=len(clusters) if relevant else 0,
        events_extracted=len(events),
        events_selected=len(selected),
        validation_passed=report.passed,
        validation_errors=report.errors,
        validation_warnings=report.warnings,
    )
    (out / "run_manifest.json").write_text(
        json.dumps(manifest.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    if not report.passed:
        raise RuntimeError(f"Validation failed: {report.errors}")

    return {
        "run_id": run_id,
        "articles_total": len(articles),
        "articles_in_period": len(in_period),
        "relevant_articles": len(relevant),
        "clusters": len(clusters) if relevant else 0,
        "events": events,
        "selected": selected,
        "package": package,
        "validation_report": report,
        "validation_errors": report.errors,
        "validation_warnings": report.warnings,
        "ai_usage": usage,
    }
