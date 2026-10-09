from datetime import datetime

from app.ai.mock import MockAI
from app.models import Article, Event, Fact, GeneratedPackage, SourceRef
from app.validation.evidence import deterministic_package_check
from app.validation.checks import validate_report


def article(i, title, text, dt="2026-10-04T09:00:00+03:00"):
    return Article(
        id=i,
        title=title,
        text=text,
        source="Test Source",
        url=f"https://example.test/{i}",
        published_at=datetime.fromisoformat(dt),
    )


def event():
    return Event(
        id="event_1",
        title="Атака на Альфу",
        article_ids=["a1"],
        facts=[Fact(text="Компания Альфа сообщила об атаке 3 октября", article_id="a1", evidence="Компания Альфа сообщила об атаке 3 октября")],
        affected_entities=["Альфа"],
        consequences=["Часть сервиса была недоступна"],
        sources=[SourceRef(article_id="a1", source="Test Source", published_at=datetime.fromisoformat("2026-10-04T09:00:00+03:00"), url="https://example.test/a1")],
        relevance=5,
        impact=4,
        scale=2,
        urgency=4,
        evidence_quality=4,
    )


def test_empty_events_is_valid_no_events_state():
    package = GeneratedPackage(
        digest="За период до 2026-10-04T12:00:00+03:00 подходящих событий нет.",
        post="Подходящих событий нет.",
        email_subject="Дайджест ИБ",
    )
    report = validate_report(package, [])
    assert report.passed is True
    assert any(w.startswith("less_than_5_events") for w in report.warnings)


def test_evidence_checker_rejects_new_number():
    e = event()
    package = GeneratedPackage(
        digest="Атака на Альфу затронула 500 организаций. Источник: https://example.test/a1",
        post="500 организаций затронуто. https://example.test/a1",
        email_subject="Дайджест",
    )
    check = deterministic_package_check(package, [e])
    assert check.passed is False
    assert "unsupported_numbers" in check.violations


def test_evidence_checker_allows_supported_number():
    e = event()
    e.facts[0].text = "Компания Альфа сообщила об атаке 3 октября, затронуты 500 организаций"
    package = GeneratedPackage(
        digest="Компания Альфа сообщила об атаке 3 октября, затронуты 500 организаций. https://example.test/a1",
        post="Атака на Альфу: затронуты 500 организаций. https://example.test/a1",
        email_subject="Дайджест",
    )
    check = deterministic_package_check(package, [e])
    assert check.passed is True


def test_mock_fact_check_pipeline():
    ai = MockAI()
    articles = [
        article("a1", "Атака ransomware против Альфы", "Компания Альфа подверглась ransomware-атаке"),
        article("a2", "Повтор: атака ransomware против Альфы", "Компания Альфа сообщает о ransomware атаке"),
    ]
    clusters = ai.cluster_all(articles, {})
    assert len(clusters.groups) == 1


def test_full_mock_run_preserves_conflict_and_ignores_injection(tmp_path):
    import json
    from app.pipeline import run
    from app.config import Settings
    from pathlib import Path

    data_path = Path(__file__).resolve().parents[1] / "data" / "test_publications_full.json"
    out = tmp_path / "out"
    result = run(
        str(data_path),
        "2026-10-04T12:00:00+03:00",
        Settings(ai_mode="mock"),
        str(out),
    )
    assert len(result["selected"]) == 5
    assert "attacker@example.com" not in result["package"].digest
    assert "attacker@example.com" not in result["package"].post
    conflict = [e for e in result["events"] if "Иота" in e.title]
    assert conflict and conflict[0].caveats
    manifest = json.loads((out / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["validation_passed"] is True


def test_preselect_cluster_budget_is_finite():
    from app.config import Settings
    assert Settings().max_preselect_clusters <= 6



def test_repair_package_restores_missing_events_and_caveats():
    from app.generation.repair import repair_generated_package
    e1 = event()
    e1.id = "event_1"
    e1.caveats = ["Число затронутых пользователей неизвестно."]
    e2 = event()
    e2.id = "event_2"
    e2.title = "Утечка в Бете"
    e2.article_ids = ["b2"]
    e2.sources = [SourceRef(article_id="b2", source="Other", published_at=e2.sources[0].published_at, url="https://example.test/b2")]
    package = GeneratedPackage(
        digest="Только событие Альфа. https://example.test/a1",
        post="Только событие Альфа. https://example.test/a1",
        email_subject="Дайджест",
    )
    repaired = repair_generated_package(package, [e1, e2], "2026-10-04T12:00:00+03:00")
    check = deterministic_package_check(repaired, [e1, e2])
    assert check.passed is True, check.violations
    assert "https://example.test/b2" in repaired.digest
    assert "https://example.test/b2" in repaired.post
    assert "Число затронутых пользователей неизвестно." in repaired.post
