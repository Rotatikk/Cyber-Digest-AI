from __future__ import annotations

import json
import os
import sys
from pathlib import Path
import tempfile

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import streamlit as st

from app.pipeline import run
from app.config import Settings

st.set_page_config(page_title="Cyber Digest AI", layout="wide")
st.title("Cyber Digest AI")
st.caption("Прототип по ТЗ: период 24 часа, релевантность, события, TOP-5, evidence, fact-check и audit")

with st.sidebar:
    st.header("Запуск")
    mode = st.selectbox("AI mode", ["openai", "mock"], index=0)
    model = st.text_input("OpenAI model", os.getenv("OPENAI_MODEL", "gpt-6-luna"))
    base_url = st.text_input("OPENAI_BASE_URL", os.getenv("OPENAI_BASE_URL", ""), help="Пусто = официальный endpoint OpenAI")
    max_calls = st.number_input("Максимум AI-вызовов", min_value=1, max_value=50, value=int(os.getenv("MAX_AI_CALLS", "12")))
    max_preselect = st.number_input("Максимум кандидатов на извлечение", min_value=5, max_value=10, value=int(os.getenv("MAX_PRESELECT_CLUSTERS", "6")))
    verify_ai = st.checkbox("AI fact-check финального текста", value=os.getenv("VERIFY_WITH_AI", "1") not in {"0", "false", "no"})
    st.caption("При достижении лимита новые платные запросы не выполняются.")

uploaded = st.file_uploader("Набор публикаций", type=["json", "csv", "xlsx"])
control_time = st.text_input("Контрольное время MSK", "2026-10-04T12:00:00+03:00")

if uploaded is None:
    st.info("Загрузите JSON/CSV/XLSX с публикациями. Реальный API-источник можно подключить отдельно после стабилизации контрольного набора.")
else:
    if st.button("Запустить обработку", type="primary", use_container_width=True):
        suffix = Path(uploaded.name).suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
            f.write(uploaded.getbuffer())
            path = f.name

        settings = Settings(
            ai_mode=mode,
            openai_model=model,
            openai_base_url=base_url.strip(),
            max_ai_calls=int(max_calls),
            max_preselect_clusters=int(max_preselect),
            verify_with_ai=verify_ai,
        )

        try:
            with st.spinner("Обработка публикаций..."):
                result = run(path, control_time, settings)
        except Exception as exc:
            st.error(str(exc))
            st.stop()

        cols = st.columns(6)
        metrics = [
            ("Публикаций", result["articles_total"]),
            ("В периоде", result["articles_in_period"]),
            ("Релевантных", result["relevant_articles"]),
            ("Кластеров", result["clusters"]),
            ("Выбрано", len(result["selected"])),
            ("AI-вызовов", result["ai_usage"].get("ai_calls")),
        ]
        for col, (label, value) in zip(cols, metrics):
            col.metric(label, value)

        warnings = result.get("validation_warnings", [])
        if warnings:
            for warning in warnings:
                st.warning(warning)

        tabs = st.tabs(["Дайджест", "Пост", "Почему выбрано", "Источники и факты", "Проверки", "Audit / AI usage"])

        with tabs[0]:
            st.subheader("Предпросмотр письма")
            st.text_area("Email preview", result["package"].digest, height=500)
            st.caption(f"Тема: {result['package'].email_subject}")

        with tabs[1]:
            st.subheader("Сокращенный пост")
            st.text_area("Post", result["package"].post, height=400)

        with tabs[2]:
            if not result["selected"]:
                st.info("Подходящих событий за период нет.")
            for idx, event in enumerate(result["selected"], 1):
                with st.expander(f"#{idx} {event.title} — score {event.score}", expanded=idx <= 2):
                    st.markdown(event.selection_reason)
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Последствия", f"{event.impact}/5")
                    c2.metric("Масштаб", f"{event.scale}/5")
                    c3.metric("Срочность", f"{event.urgency}/5")
                    c4.metric("Релевантность", f"{event.relevance}/5")
                    st.write("**Почему такие оценки**")
                    st.write(f"Последствия: {event.impact_evidence}")
                    st.write(f"Масштаб: {event.scale_evidence}")
                    st.write(f"Срочность: {event.urgency_evidence}")
                    st.write(f"Релевантность: {event.relevance_evidence}")
                    st.write(f"Доказательства: {event.evidence_quality_evidence}")

        with tabs[3]:
            for idx, event in enumerate(result["selected"], 1):
                st.markdown(f"### {idx}. {event.title}")
                st.write("**Факты**")
                for fact in event.facts:
                    st.write(f"- {fact.text}")
                    st.caption(f"Источник {fact.article_id}: {fact.evidence}")
                st.write("**Последствия**")
                for consequence in event.consequences:
                    st.write(f"- {consequence}")
                if event.caveats:
                    st.write("**Оговорки / расхождения**")
                    for caveat in event.caveats:
                        st.warning(caveat)
                st.write("**Источники**")
                st.dataframe(pd.DataFrame([s.model_dump(mode="json") for s in event.sources]), use_container_width=True, hide_index=True)

        with tabs[4]:
            report = result["validation_report"]
            if report.passed:
                st.success("Все обязательные проверки пройдены.")
            else:
                st.error("Есть ошибки валидации")
                for error in report.errors:
                    st.write(f"- {error}")
            if report.package_check:
                st.write("### Fact-check")
                st.json(report.package_check.model_dump(mode="json"))

        with tabs[5]:
            usage = result["ai_usage"]
            st.write("### AI usage")
            st.json(usage)
            out = Path("output")
            if (out / "run_manifest.json").exists():
                st.write("### Run manifest")
                st.json(json.loads((out / "run_manifest.json").read_text(encoding="utf-8")))
            if (out / "processing_log.csv").exists():
                st.write("### Processing log")
                st.dataframe(pd.read_csv(out / "processing_log.csv"), use_container_width=True, hide_index=True)
