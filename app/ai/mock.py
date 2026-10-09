from __future__ import annotations

import re
from app.ai.base import AIProvider
from app.models import (
    Article, Classification, ClusterDecision, ExtractedEvent, Fact, GeneratedPackage,
    ClassificationItem, ClassificationBatch, ClusterBatch, ClusterGroup, Event, PackageCheck,
)
from app.filtering.relevance import lexical_candidate


class MockAI(AIProvider):
    def classify(self, article: Article) -> Classification:
        ok = lexical_candidate(article)
        if any(x in article.text.lower() for x in ("реклама", "скидк", "купите", "акция") ):
            ok = False
        return Classification(relevant=ok, reason="Есть признаки тематики ИБ" if ok else "Нет признаков тематической ИБ-новости")

    def classify_many(self, articles: list[Article]) -> list[Classification]:
        return [self.classify(a) for a in articles]

    def _entity_key(self, article: Article) -> str:
        text = f"{article.title} {article.text}".lower()
        m = re.search(r"(?:компани[яи]|организаци[яи]|продукт[еа]?|портал[аеи]?)\s+([a-zа-яё][\w-]{2,})", text, flags=re.UNICODE)
        if m:
            return m.group(1)
        cve = re.search(r"cve-\d{4}-\d{4,}", text, flags=re.I)
        return cve.group(0).lower() if cve else "general"

    def _tokens(self, text: str) -> set[str]:
        return {t for t in re.findall(r"[\w-]+", text.lower(), flags=re.UNICODE) if len(t) >= 4}

    def same_event(self, left: Article, right: Article) -> ClusterDecision:
        a = self._tokens(left.title + " " + left.text)
        b = self._tokens(right.title + " " + right.text)
        overlap = len(a & b) / max(1, len(a | b))
        shared = {t for t in a & b if len(t) >= 6}
        same = self._entity_key(left) == self._entity_key(right) and (
            overlap >= 0.10 or len(shared) >= 2
        )
        return ClusterDecision(same_event=same, reason=f"entity={self._entity_key(left)}; overlap={overlap:.2f}")

    def cluster_all(self, articles: list[Article], buckets: dict[str, list[Article]]) -> ClusterBatch:
        groups: list[list[Article]] = []
        for article in articles:
            placed = False
            for group in groups:
                if self.same_event(article, group[0]).same_event:
                    group.append(article)
                    placed = True
                    break
            if not placed:
                groups.append([article])
        out = []
        for idx, group in enumerate(groups, 1):
            text = " ".join(a.title + " " + a.text for a in group).lower()
            impact = 4 if any(k in text for k in ["ransomware", "шифровальщик", "критическ", "утечк", "компрометац"]) else 2
            urgency = 4 if any(k in text for k in ["атака", "эксплуатац", "подтвердила", "восстановление"]) else 2
            scale = 3 if len(group) > 1 else 2
            out.append(ClusterGroup(
                cluster_id=f"event_{idx}", article_ids=[a.id for a in group],
                reason="Совпадают сущность и конкретные детали события",
                preliminary_relevance=4, preliminary_impact=impact, preliminary_scale=scale, preliminary_urgency=urgency,
            ))
        return ClusterBatch(groups=out)

    def cluster_group(self, articles: list[Article], group_id: str) -> ClusterBatch:
        groups: list[list[Article]] = []
        for article in articles:
            placed = False
            for group in groups:
                if self.same_event(article, group[0]).same_event:
                    group.append(article)
                    placed = True
                    break
            if not placed:
                groups.append([article])
        out = []
        for idx, group in enumerate(groups, 1):
            text = " ".join(a.title + " " + a.text for a in group).lower()
            impact = 4 if any(k in text for k in ["ransomware", "шифровальщик", "критическ", "утечк", "компрометац"]) else 2
            urgency = 4 if any(k in text for k in ["атака", "эксплуатац", "подтвердила", "восстановление"]) else 2
            scale = 3 if len(group) > 1 else 2
            out.append(ClusterGroup(
                cluster_id=f"{group_id}_{idx}",
                article_ids=[a.id for a in group],
                reason="Совпадают ключевая организация/продукт и детали события",
                preliminary_relevance=4,
                preliminary_impact=impact,
                preliminary_scale=scale,
                preliminary_urgency=urgency,
            ))
        return ClusterBatch(groups=out)

    def extract_event(self, articles: list[Article], event_id: str) -> ExtractedEvent:
        primary = max(articles, key=lambda x: len(x.text))
        fact_text = primary.text.strip().replace("\n", " ")[:500]
        fact = Fact(text=fact_text or primary.title, article_id=primary.id, evidence=fact_text or primary.title)
        text = " ".join(a.text.lower() for a in articles)
        high_impact = any(k in text for k in ["ransomware", "шифровальщик", "критическ", "утечк"])
        consequences = []
        if "недоступ" in text or "останов" in text:
            consequences.append("Часть сервисов была недоступна по данным источника.")
        elif "восстанов" in text:
            consequences.append("Источник сообщает о восстановлении после инцидента.")
        else:
            consequences.append("Подробные последствия в источнике не раскрыты.")
        return ExtractedEvent(
            title=primary.title or f"Событие {event_id}",
            facts=[fact],
            sources=[{"article_id": a.id, "source": a.source, "published_at": a.published_at, "url": a.url} for a in articles],
            affected_entities=[self._entity_key(primary)],
            consequences=consequences,
            caveats=["Источник не раскрывает дополнительный масштаб."] if "не раскры" in text else [],
            relevance=4,
            impact=4 if high_impact else 3,
            scale=3 if len(articles) > 1 else 2,
            urgency=4 if "ата" in text or "подтверд" in text else 3,
            evidence_quality=4 if len(articles) > 1 else 3,
            impact_evidence="В источнике описаны последствия инцидента или тип проблемы.",
            scale_evidence="Масштаб оценен по количеству источников; точное число затронутых объектов указано только при наличии.",
            urgency_evidence="В источнике есть признаки текущего реагирования или эксплуатации.",
            relevance_evidence="Материал непосредственно относится к задачам ИБ.",
            evidence_quality_evidence="Есть исходный текст и ссылка на материал.",
        )

    def extract_events(self, clusters: list[tuple[str, list[Article]]]) -> dict[str, ExtractedEvent]:
        return {event_id: self.extract_event(articles, event_id) for event_id, articles in clusters}

    def generate_package(self, events: list[ExtractedEvent], control_time: str) -> GeneratedPackage:
        if not events:
            msg = f"За период до {control_time} подходящих событий по информационной безопасности не найдено."
            return GeneratedPackage(digest=msg, post=msg, email_subject=f"Дайджест ИБ до {control_time}")

        def source_line(e: ExtractedEvent) -> str:
            return "; ".join(
                f"{src.source}, {src.published_at.strftime('%d.%m.%Y') if src.published_at else 'дата не указана'}, ID {src.article_id}, {src.url}"
                for src in e.sources
            )

        def digest_block(e: ExtractedEvent, idx: int) -> str:
            fact = (e.facts[0].text if e.facts else e.title).replace("\n", " ")[:360]
            consequence = (e.consequences[0] if e.consequences else "Сведения о последствиях отсутствуют.")[:110]
            return f"{idx}. {e.title}. {fact} Последствия: {consequence} Источники: {source_line(e)}"

        def post_block(e: ExtractedEvent, idx: int) -> str:
            fact = (e.facts[0].text if e.facts else e.title).replace("\n", " ")[:170]
            urls = ", ".join(src.url for src in e.sources)
            return f"{idx}. {e.title}. {fact} Источники: {urls}"

        digest = f"Дайджест за период последних 24 часов до {control_time}. Событий: {len(events)}.\n\n" + "\n\n".join(digest_block(e, i) for i, e in enumerate(events, 1))
        post = "\n\n".join(post_block(e, i) for i, e in enumerate(events, 1))
        return GeneratedPackage(digest=digest[:3990], post=post[:1990], email_subject=f"Дайджест ИБ до {control_time}")

    def verify_package(self, package: GeneratedPackage, events: list[Event]) -> PackageCheck:
        from app.validation.evidence import deterministic_package_check
        return deterministic_package_check(package, events)
