from __future__ import annotations

from app.models import Event, GeneratedPackage
from app.validation.evidence import strip_urls


def _source_urls(event: Event) -> list[str]:
    return [s.url for s in event.sources if s.url]


def _source_line(event: Event) -> str:
    items = []
    for s in event.sources:
        date = s.published_at.strftime('%d.%m.%Y') if s.published_at else 'дата не указана'
        items.append(f"{s.source}, {date}, ID {s.article_id}, {s.url}")
    return "; ".join(items)


def _fact(event: Event, limit: int) -> str:
    if event.facts:
        text = event.facts[0].text.strip().replace('\n', ' ')
    else:
        text = event.title
    return text[:limit]


def _caveat_line(event: Event) -> str:
    if not event.caveats:
        return ''
    return ' Оговорки: ' + ' '.join(c.strip() for c in event.caveats if c.strip())


def _digest_block(event: Event, index: int) -> str:
    consequences = ' '.join(c.strip() for c in event.consequences if c.strip()) or 'Сведения о последствиях отсутствуют.'
    return (
        f"{index}. {event.title}. {_fact(event, 360)} "
        f"Последствия: {consequences[:260]}."
        f"{_caveat_line(event)} Источники: {_source_line(event)}"
    )


def _post_block(event: Event, index: int) -> str:
    text = f"{index}. {event.title}. {_fact(event, 190)}"
    if event.caveats:
        text += _caveat_line(event)
    text += ' Источники: ' + ', '.join(_source_urls(event))
    return text


def _event_present(text: str, event: Event) -> bool:
    text_l = (text or '').lower()
    urls = _source_urls(event)
    if urls and any(url.lower() in text_l for url in urls):
        return True
    title = ' '.join((event.title or '').lower().split())
    return bool(title and title in ' '.join((text or '').lower().split()))


def repair_generated_package(package: GeneratedPackage, selected: list[Event], control_time: str) -> GeneratedPackage:
    """Repair omissions deterministically without another LLM call.

    The LLM remains responsible for wording, but coverage of selected events,
    source URLs and caveats is enforced by code so a concise model response
    cannot silently drop a selected event or an important caveat.
    """
    digest = package.digest or ''
    post = package.post or ''

    missing_digest = [e for e in selected if not _event_present(digest, e)]
    missing_post = [e for e in selected if not _event_present(post, e)]

    if missing_digest:
        start = len(digest)
        addition = '\n\n' + '\n\n'.join(_digest_block(e, selected.index(e) + 1) for e in missing_digest)
        digest = (digest.rstrip() + addition) if start else addition.lstrip()

    if missing_post:
        addition = '\n\n' + '\n\n'.join(_post_block(e, selected.index(e) + 1) for e in missing_post)
        post = (post.rstrip() + addition) if post.strip() else addition.lstrip()

    # Ensure every source ID is visible in the digest and every source URL is
    # present in both digest and post. These are deterministic metadata anchors.
    digest_l = digest.lower()
    post_l = post.lower()
    missing_source_lines = []
    for event in selected:
        missing_ids = [s.article_id for s in event.sources if s.article_id and s.article_id.lower() not in digest_l]
        missing_urls = [s.url for s in event.sources if s.url and s.url.lower() not in digest_l]
        if missing_ids or missing_urls:
            missing_source_lines.append('Источники: ' + _source_line(event))
    if missing_source_lines:
        digest += '\n\n' + '\n'.join(missing_source_lines)

    digest_l = digest.lower()
    missing_post_urls = []
    for event in selected:
        for source in event.sources:
            if source.url and source.url.lower() not in post_l:
                missing_post_urls.append(source.url)
    if missing_post_urls:
        post += '\n\nИсточники: ' + ', '.join(dict.fromkeys(missing_post_urls))

    # Ensure caveats are not silently dropped from either representation.
    for event in selected:
        if not event.caveats:
            continue
        caveats = ' '.join(c.strip() for c in event.caveats if c.strip())
        if not caveats:
            continue
        marker = caveats.lower()
        if marker not in digest.lower():
            digest += f"\n\nОговорка по событию «{event.title}»: {caveats}"
        if marker not in post.lower():
            post += f"\n\nОговорка по событию «{event.title}»: {caveats}"

    # If the model response is over a limit after repair, build a deterministic
    # compact package from the selected events rather than truncating facts.
    if len(strip_urls(digest)) > 4000:
        blocks = [_digest_block(e, i) for i, e in enumerate(selected, 1)]
        digest = (
            f"Дайджест за последние 24 часа до {control_time} по Москве. "
            f"Событий: {len(selected)}.\n\n" + '\n\n'.join(blocks)
        )
    if len(strip_urls(post)) > 2000:
        post = '\n\n'.join(_post_block(e, i) for i, e in enumerate(selected, 1))

    subject = package.email_subject.strip() or f"Дайджест ИБ до {control_time}"
    return GeneratedPackage(digest=digest, post=post, email_subject=subject)
