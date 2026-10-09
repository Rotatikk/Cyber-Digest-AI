# Cyber Digest AI v2

Прототип ИИ-сервиса подготовки новостного дайджеста по кибербезопасности по ТЗ первого этапа.

## Что улучшено в v2

- строгая проверка 24-часового окна по Москве;
- словарный pre-filter до обращения к модели;
- пакетная классификация публикаций;
- единый LLM-вызов для кластеризации вместо N²-парных сравнений;
- объединение повторов и сохранение всех источников;
- извлечение фактов с `article_id` + `evidence`;
- отдельные доказательства для оценок impact / scale / urgency / relevance / evidence quality;
- TOP-5 с объяснением порядка событий;
- генерация email preview и поста из одного набора структурированных событий;
- детерминированный evidence-check чисел и URL;
- отдельный AI fact-check финального текста, максимум один дополнительный вызов;
- обнаружение конфликтов и сохранение caveats;
- проверка согласованности выбранных событий между digest и post;
- `processing_log.csv`;
- `events.json`;
- `validation_report.json`;
- `run_manifest.json`;
- `ai_usage.json` с количеством запросов и токенами;
- hard limit `MAX_AI_CALLS` и `max_retries=0`;
- `OPENAI_BASE_URL` остаётся опциональным;
- обновленный Streamlit UI с вкладками «Почему выбрано», «Источники и факты», «Проверки», «Audit / AI usage`;
- mock-режим для воспроизводимых тестов без API-ключа.

## Формат входных данных

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

## Запуск

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m pytest -q
python -m app.cli --ai-mode mock --input data/test_publications_full.json --control-time 2026-10-04T12:00:00+03:00
streamlit run app/ui.py
```

Для OpenAI:

```env
AI_MODE=openai
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-6-luna
OPENAI_BASE_URL=
MAX_AI_CALLS=12
MAX_PRESELECT_CLUSTERS=6
VERIFY_WITH_AI=1
PROMPT_VERSION=2.1
```

`OPENAI_BASE_URL=` оставляйте пустым, если нужен стандартный OpenAI endpoint. Свой OpenAI-compatible endpoint можно указать явно.

## Контроль стоимости

Ключевой принцип v2: не делать один API-вызов на одну статью. Классификация и кластеризация работают пакетно. В типичном прогоне структура такая:

1. пакетная классификация;
2. одна кластеризация;
3. одно пакетное извлечение событий;
4. генерация дайджеста;
5. один AI fact-check.

`MAX_AI_CALLS` является жестким верхним пределом. Автоматические retries OpenAI SDK отключены.

`OPENAI_INPUT_PRICE_PER_1M` и `OPENAI_OUTPUT_PRICE_PER_1M` можно заполнить, чтобы `ai_usage.json` рассчитывал ориентировочную стоимость. Если цены не указаны, стоимость записывается как `null`.

## Выходные артефакты

- `digest.txt` — полный дайджест;
- `post.txt` — сокращенный пост;
- `email_subject.txt` — тема письма;
- `events.json` — выбранные события, факты и источники;
- `processing_log.csv` — статус каждой публикации;
- `validation_report.json` — обязательные проверки;
- `run_manifest.json` — параметры и воспроизводимость запуска;
- `ai_usage.json` — AI-вызовы, токены и стоимость.

## Тестовый набор

`data/test_publications_full.json` — синтетический набор, включающий повторы, материалы вне периода, обновление старого события, неполный текст, противоречивые сообщения, prompt injection и рекламный текст.

## Безопасность

Текст публикации всегда передается модели как данные. Инструкции внутри новости не должны изменять правила отбора, настройки или адресатов. Ключи не должны попадать в код, prompts или audit log.


### Контроль размера extraction-запроса
По умолчанию извлекаются только 6 лучших предварительно ранжированных кластеров. Это предотвращает слишком большой третий LLM-запрос. Лимит можно изменить через `MAX_PRESELECT_CLUSTERS` или `--max-preselect-clusters`.
