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


def test_extraction_and_ai_call_limits_are_unlimited_by_default():
    from app.config import Settings
    settings = Settings()
    assert settings.max_preselect_clusters is None
    assert settings.max_ai_calls is None
    assert settings.openai_timeout == 60
    assert settings.retry_requests is False
    explicit_unlimited = Settings(max_ai_calls=0, max_preselect_clusters=0)
    assert explicit_unlimited.max_ai_calls is None
    assert explicit_unlimited.max_preselect_clusters is None



def test_caveats_are_moved_into_the_related_event_not_left_in_email_footer():
    from app.generation.repair import repair_generated_package

    e = event()
    caveat = "Число затронутых пользователей неизвестно."
    e.caveats = [caveat]
    package = GeneratedPackage(
        digest=(
            "Дайджест за период.\n\n1. Атака на Альфу. Компания сообщила об атаке. "
            "Источник: https://example.test/a1\n\nОговорки: " + caveat
        ),
        post=(
            "1. Атака на Альфу. Краткое описание. https://example.test/a1"
            "\n\nОговорки: " + caveat
        ),
        email_subject="Дайджест",
    )

    repaired = repair_generated_package(package, [e], "2026-10-04T12:00:00+03:00")
    digest_event_paragraph = next(p for p in repaired.digest.split("\n\n") if "Атака на Альфу" in p)
    post_event_paragraph = next(p for p in repaired.post.split("\n\n") if "Атака на Альфу" in p)
    assert caveat in digest_event_paragraph
    assert caveat in post_event_paragraph
    assert not any(p.strip().lower().startswith("оговорки:") for p in repaired.digest.split("\n\n"))
    assert not any(p.strip().lower().startswith("оговорки:") for p in repaired.post.split("\n\n"))


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


def test_extraction_config_limits_batch_size():
    from app.config import Settings
    assert Settings().extraction_batch_size == 2

def test_openai_provider_can_enable_or_disable_transient_request_retries(monkeypatch):
    import importlib
    import sys
    import types
    constructed = []

    class DummyClient:
        def __init__(self, **kwargs):
            constructed.append(kwargs)
            self.responses = type("Responses", (), {"create": lambda self, **kwargs: None})()

    fake_openai = types.ModuleType("openai")
    fake_openai.OpenAI = DummyClient
    monkeypatch.setitem(sys.modules, "openai", fake_openai)
    sys.modules.pop("app.ai.openai_provider", None)
    provider_module = importlib.import_module("app.ai.openai_provider")
    provider_module.OpenAIProvider("test-model", "key", retry_requests=False)
    provider_module.OpenAIProvider("test-model", "key", retry_requests=True)
    assert constructed[0]["max_retries"] == 0
    assert constructed[1]["max_retries"] == 2

    from app.models import Article
    long_article = Article(
        id="long", title="Тест", text=("Основной текст. " * 200) + "ВАЖНОЕ УТОЧНЕНИЕ В КОНЦЕ",
        source="Test", url="https://example.test/long",
    )
    article_block = provider_module.OpenAIProvider._article_block(long_article, 1000)
    assert "ВАЖНОЕ УТОЧНЕНИЕ В КОНЦЕ" in article_block
    monkeypatch.delitem(sys.modules, "app.ai.openai_provider", raising=False)


def test_models_support_extracted_event_batch():
    from app.models import ExtractedEventBatch, ExtractedEventBatchItem, ExtractedEvent
    e = ExtractedEvent(
        title="Атака на Альфу", facts=[], affected_entities=[], consequences=[], caveats=[],
        relevance=1, impact=1, scale=1, urgency=1, evidence_quality=1
    )
    batch = ExtractedEventBatch(events=[ExtractedEventBatchItem(event_id="event_1", event=e)])
    assert batch.events[0].event_id == "event_1"



def test_pipeline_keeps_outputs_when_ai_fact_check_fails(tmp_path, monkeypatch):
    import json
    from pathlib import Path
    from app import pipeline
    from app.config import Settings

    class FailingVerifier:
        calls = 0
        usage = {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2}
        def __getattr__(self, name):
            return getattr(MockAI(), name)
        def verify_package(self, package, events):
            raise TimeoutError("fact-check timed out")

    monkeypatch.setattr(pipeline, "get_ai", lambda settings: FailingVerifier())
    data_path = Path(__file__).resolve().parents[1] / "data" / "test_publications_full.json"
    out = tmp_path / "out"
    result = pipeline.run(str(data_path), "2026-10-04T12:00:00+03:00", Settings(ai_mode="openai"), str(out))
    assert result["validation_report"].passed is False
    assert any("ai_fact_check_unavailable" in w for w in result["validation_warnings"])
    assert (out / "digest.txt").exists()
    assert (out / "post.txt").exists()
    manifest = json.loads((out / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["validation_passed"] is False


def test_pipeline_returns_validation_failure_without_raising(tmp_path):
    from pathlib import Path
    from app.pipeline import run
    from app.config import Settings
    data_path = Path(__file__).resolve().parents[1] / "data" / "test_publications_full.json"
    result = run(str(data_path), "2026-10-04T12:00:00+03:00", Settings(ai_mode="mock"), str(tmp_path / "out"))
    assert "validation_report" in result
    assert "validation_errors" in result
