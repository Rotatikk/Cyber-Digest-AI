# Cyber Digest MVP

Прототип ИИ-сервиса подготовки дайджеста по кибербезопасности по ТЗ первого этапа хакатона.

## Что уже есть

- загрузка JSON/CSV/XLSX с публикациями;
- проверка периода последних 24 часов по московскому времени;
- базовый словарный pre-filter;
- AI-классификация релевантности;
- группировка повторов событий через AI adapter;
- ranking до 5 событий;
- генерация дайджеста, поста и email preview;
- проверки длины и обязательных полей;
- audit log по каждой публикации;
- mock-режим без API-ключа;
- тесты обязательных сценариев из ТЗ.

## Формат входных данных

JSON:

```json
[
  {
    "id": "n1",
    "title": "Заголовок",
    "text": "Полный текст публикации",
    "source": "Источник",
    "url": "https://example.com/news/1",
    "published_at": "2026-10-03T10:30:00+03:00"
  }
]
```

Пустые поля допустимы: система должна отдельно записать причину пропуска.

## Запуск

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
cp .env.example .env
python -m pytest -q
python -m app.cli --input data/sample.json --control-time 2026-10-03T12:00:00+03:00
streamlit run app/ui.py
```

Для реальной модели:

```text
AI_MODE=openai
OPENAI_API_KEY=...
OPENAI_MODEL=<доступная вам модель>
```

Прототип использует Responses API через официальный Python SDK. Не храните ключи в коде, prompt или журнале.

Примечание: `app/ui.py` сам добавляет корень проекта в `sys.path`, поэтому Streamlit можно запускать обычной командой `streamlit run app/ui.py`.
