# Prompt registry

Версия: `2.1`

Системная инструкция и промпты находятся в `app/ai/openai_provider.py` и версионируются полем `PROMPT_VERSION` / `.env`.

Основные контракты:

- `classify_many`: релевантность каждой публикации;
- `cluster_all`: одно событие на группу публикаций, каждый `article_id` ровно один раз;
- `extract_events`: факты, evidence, источники, caveats и оценки;
- `generate_package`: digest/post/email preview без новых фактов;
- `verify_package`: независимая проверка claims, чисел, ссылок, дат, событий и расхождений.
