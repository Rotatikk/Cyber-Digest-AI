from __future__ import annotations

import re

from app.ai.base import AIProvider
from app.models import Article, Classification, ClusterDecision, ExtractedEvent, Fact, GeneratedPackage
from app.filtering.relevance import lexical_candidate

class MockAI(AIProvider):
    def classify(self, article: Article) -> Classification:
        ok = lexical_candidate(article)
        return Classification(relevant=ok, reason="Есть признаки тематики ИБ" if ok else "Нет признаков тематики ИБ")

    def same_event(self, left: Article, right: Article) -> ClusterDecision:
        tokenize = lambda text: set(re.findall(r"[\w-]+", text.lower(), flags=re.UNICODE))
        a = tokenize(left.title + " " + left.text)
        b = tokenize(right.title + " " + right.text)
        overlap = len(a & b) / max(1, len(a | b))
        long_shared = {t for t in (a & b) if len(t) >= 5}
        same = (
            overlap >= 0.08
            or len(long_shared) >= 2
            or (left.source and left.source == right.source and left.title[:30].lower() == right.title[:30].lower())
        )
        return ClusterDecision(same_event=same, reason=f"token_overlap={overlap:.2f}; shared_terms={sorted(long_shared)[:5]}")

    def extract_event(self, articles: list[Article], event_id: str) -> ExtractedEvent:
        primary = max(articles, key=lambda x: len(x.text))
        fact_text = primary.text.strip().replace("\n", " ")[:500]
        fact = Fact(text=fact_text or primary.title, article_id=primary.id, evidence=fact_text or primary.title)
        sources = [
            {
                "article_id": a.id,
                "source": a.source,
                "published_at": a.published_at,
                "url": a.url,
            }
            for a in articles
        ]
        return ExtractedEvent(
            title=primary.title or f"Событие {event_id}",
            facts=[fact],
            sources=sources,
            affected_entities=[primary.source] if primary.source else [],
            consequences=["Подробные последствия требуют дополнительной проверки источника."],
            caveats=[],
            relevance=3,
            impact=3,
            scale=2,
            urgency=3,
            evidence_quality=3,
        )

    def generate_package(self, events: list[ExtractedEvent], control_time: str) -> GeneratedPackage:
        if not events:
            msg = f"За период до {control_time} подходящих событий по информационной безопасности не найдено."
            return GeneratedPackage(digest=msg, post=msg, email_subject=f"Дайджест ИБ до {control_time}")

        def block(e: ExtractedEvent, concise: bool = False) -> str:
            fact = (e.facts[0].text if e.facts else e.title).replace("\n", " ")
            fact = fact[:260] if concise else fact[:700]
            consequence = (e.consequences[0] if e.consequences else "Сведения о последствиях отсутствуют в тестовых данных.")[:180]
            source_lines = "; ".join(
                f"{src.source}, {src.published_at.isoformat() if src.published_at else 'дата не указана'}, ID {src.article_id}, {src.url}"
                for src in e.sources
            )
            return f"{e.title}. {fact} Последствия: {consequence} Источники: {source_lines}"

        digest_blocks = [f"{idx}. {block(e)}" for idx, e in enumerate(events, 1)]
        digest = f"Дайджест за период до {control_time}.\nНайдено событий: {len(events)}.\n\n" + "\n\n".join(digest_blocks)

        # Тестовый генератор гарантирует лимит поста. В реальном режиме лимит проверяет validator.
        post_parts = []
        for idx, e in enumerate(events, 1):
            post_parts.append(f"{idx}. {block(e, concise=True)}")
        post = "\n\n".join(post_parts)
        if len(post) > 2000:
            post = post[:1960].rstrip() + "\n[Пост сокращен тестовым генератором до лимита 2000 знаков.]"

        return GeneratedPackage(digest=digest, post=post, email_subject=f"Дайджест ИБ до {control_time}")
