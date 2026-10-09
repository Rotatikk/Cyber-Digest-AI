from __future__ import annotations

import re
from urllib.parse import urlparse

from app.models import Event, GeneratedPackage, PackageCheck

URL_RE = re.compile(r"https?://[^\s)\]>]+", re.IGNORECASE)
DATE_RE = re.compile(r"\b(?:\d{4}-\d{2}-\d{2}|\d{2}\.\d{2}\.\d{4})\b")
NUMBER_RE = re.compile(r"\b\d+(?:[.,]\d+)?\b")


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def _all_event_text(events: list[Event]) -> str:
    parts: list[str] = []
    for event in events:
        parts.append(event.title)
        parts.extend(f.text for f in event.facts)
        parts.extend(f.evidence for f in event.facts)
        parts.extend(event.affected_entities)
        parts.extend(event.consequences)
        parts.extend(event.caveats)
        parts.extend(str(s.published_at.date()) for s in event.sources if s.published_at)
    return _norm(" ".join(parts))


def _important_numbers(text: str) -> set[str]:
    # Не считаем форматирование, даты и служебное "24 часа" доказательствами фактов.
    cleaned = DATE_RE.sub(" ", text or "")
    cleaned = re.sub(r"\b24\s*(?:часа|часов|ч)\b", " ", cleaned, flags=re.I)
    cleaned = re.sub(r"\b\d+\.\s", " ", cleaned)  # нумерация пунктов
    result: set[str] = set()
    for match in NUMBER_RE.findall(cleaned):
        try:
            value = float(match.replace(",", "."))
        except ValueError:
            continue
        # Малые целые обычно являются днями/пунктами; десятичные версии оставляем.
        if value.is_integer() and (value <= 31 or value >= 1900):
            continue
        result.add(match)
    return result


def _event_tokens(event: Event) -> set[str]:
    text = " ".join([event.title] + [f.text for f in event.facts] + event.affected_entities)
    return {x for x in re.findall(r"[\w-]{4,}", text.lower(), flags=re.UNICODE)}


def deterministic_package_check(package: GeneratedPackage, events: list[Event]) -> PackageCheck:
    if not events:
        return PackageCheck(passed=True)

    digest_raw = package.digest or ""
    post_raw = package.post or ""
    digest = strip_urls(digest_raw)
    post = strip_urls(post_raw)
    source_urls = {s.url for e in events for s in e.sources if s.url}
    source_url_hosts = {urlparse(u).netloc for u in source_urls if urlparse(u).netloc}
    corpus = _all_event_text(events)
    violations: list[str] = []
    unsupported: list[str] = []
    conflicting: list[str] = []

    all_numbers = _important_numbers(package.digest + " " + package.post)
    evidence_numbers = _important_numbers(corpus)
    for number in all_numbers:
        if number not in evidence_numbers:
            unsupported.append(f"number_not_found_in_evidence:{number}")

    urls_digest = {u.rstrip(".,;:)") for u in URL_RE.findall(package.digest)}
    urls_post = {u.rstrip(".,;:)") for u in URL_RE.findall(package.post)}
    for url in urls_digest | urls_post:
        if url not in source_urls:
            host = urlparse(url).netloc
            if host not in source_url_hosts:
                violations.append(f"unknown_url:{url}")

    if urls_digest != urls_post:
        violations.append("digest_post_urls_mismatch")

    digest_norm = _norm(digest)
    post_norm = _norm(post)

    def event_present(text_norm: str, event: Event) -> bool:
        # Source URLs are canonical anchors. Fall back to an exact normalized title
        # only when the source URL is unavailable. This avoids false negatives when
        # the model paraphrases the event title.
        urls = [s.url.lower() for s in event.sources if s.url]
        if urls and any(u in text_norm for u in urls):
            return True
        title = _norm(event.title)
        return bool(title and title in text_norm)

    missing_digest = [e.id for e in events if not event_present(_norm(digest_raw), e)]
    missing_post = [e.id for e in events if not event_present(_norm(post_raw), e)]
    if missing_digest:
        violations.append("selected_event_missing_from_digest:" + ",".join(missing_digest))
    if missing_post:
        violations.append("selected_event_missing_from_post:" + ",".join(missing_post))

    # Каждый выбранный источник обязан присутствовать в digest. ID служит простой anchor-check.
    for event in events:
        for source in event.sources:
            if source.article_id not in package.digest:
                violations.append(f"source_id_missing_from_digest:{source.article_id}")
            if source.url and source.url not in package.digest:
                violations.append(f"source_url_missing_from_digest:{source.article_id}")

    for event in events:
        nums = set()
        for fact in event.facts:
            nums.update(_important_numbers(fact.text))
        if len(nums) > 1 and not event.caveats:
            conflicting.append(f"numeric_conflict_without_caveat:{event.id}")

    if unsupported:
        violations.append("unsupported_numbers")
    if conflicting:
        violations.append("conflicts_not_preserved")

    return PackageCheck(
        passed=not violations,
        violations=violations,
        unsupported_claims=unsupported,
        conflicting_claims=conflicting,
        event_ids_in_digest=[e.id for e in events if event_present(_norm(digest_raw), e)],
        event_ids_in_post=[e.id for e in events if event_present(_norm(post_raw), e)],
        numbers_checked=len(all_numbers),
        urls_checked=len(urls_digest | urls_post),
    )


def strip_urls(text: str) -> str:
    return URL_RE.sub("", text or "")
