from __future__ import annotations

import sys
from pathlib import Path
import tempfile

# Streamlit запускает app/ui.py как отдельный скрипт и не всегда
# добавляет корень проекта в sys.path. Явно добавляем его, чтобы
# импорты вида `from app...` работали независимо от способа запуска.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

from app.pipeline import run
from app.config import Settings

st.set_page_config(page_title="Cyber Digest AI", layout="wide")
st.title("Cyber Digest AI")
st.caption("MVP по ТЗ: отбор, объединение событий, ranking, дайджест и audit log")

uploaded = st.file_uploader("Набор публикаций", type=["json", "csv", "xlsx"])
control_time = st.text_input("Контрольное время MSK", "2026-10-03T12:00:00+03:00")
mode = st.selectbox("AI mode", ["openai", "mock"], index=0)
st.caption("OpenAI-режим ограничен MAX_AI_CALLS. Текущее значение: " + __import__("os").getenv("MAX_AI_CALLS", "12"))

if uploaded and st.button("Запустить"):
    suffix = Path(uploaded.name).suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
        f.write(uploaded.getbuffer())
        path = f.name
    settings = Settings(ai_mode=mode)
    with st.spinner("Обработка..."):
        result = run(path, control_time, settings)
    st.metric("Публикаций", result["articles_total"])
    st.metric("Событий", len(result["events"]))
    st.metric("Выбрано", len(result["selected"]))
    st.metric("LLM вызовов", result["ai_usage"].get("ai_calls"))
    st.subheader("Дайджест")
    st.text_area("Email preview", result["package"].digest, height=450)
    st.subheader("Пост")
    st.text_area("Post", result["package"].post, height=300)
    st.subheader("Выбранные события")
    for e in result["selected"]:
        with st.expander(e.title):
            st.write(f"Score: {e.score}")
            st.write(e.selection_reason)
            st.json(e.model_dump(mode="json"))
    st.subheader("Audit log")
    log_path = Path("output/processing_log.csv")
    if log_path.exists():
        st.dataframe(log_path.read_text(encoding="utf-8-sig"))
