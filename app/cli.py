from __future__ import annotations

import argparse
from dataclasses import replace
from app.pipeline import run
from app.config import Settings


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--control-time", required=True)
    p.add_argument("--output-dir", default="output")
    p.add_argument("--ai-mode", choices=["mock", "openai"], default=None)
    p.add_argument("--model", default=None)
    p.add_argument("--base-url", default=None, help="OpenAI-compatible base URL; empty = official OpenAI endpoint")
    p.add_argument("--max-ai-calls", type=int, default=None, help="0 = без лимита (по умолчанию без лимита)")
    p.add_argument("--max-preselect-clusters", type=int, default=None, help="0 = извлекать все кластеры (по умолчанию без лимита)")
    p.add_argument("--extraction-batch-size", type=int, default=None)
    p.add_argument("--json-mode", choices=["on", "off"], default=None)
    p.add_argument("--skip-ai-fact-check", action="store_true")
    args = p.parse_args()

    settings = Settings()
    if args.ai_mode:
        settings = replace(settings, ai_mode=args.ai_mode)
    if args.model:
        settings = replace(settings, openai_model=args.model)
    if args.base_url is not None:
        settings = replace(settings, openai_base_url=args.base_url.strip())
    if args.max_ai_calls is not None:
        settings = replace(settings, max_ai_calls=args.max_ai_calls if args.max_ai_calls > 0 else None)
    if args.max_preselect_clusters is not None:
        settings = replace(settings, max_preselect_clusters=args.max_preselect_clusters if args.max_preselect_clusters > 0 else None)
    if args.extraction_batch_size is not None:
        settings = replace(settings, extraction_batch_size=max(1, args.extraction_batch_size))
    if args.json_mode is not None:
        settings = replace(settings, openai_json_mode=(args.json_mode == "on"))
    if args.skip_ai_fact_check:
        settings = replace(settings, verify_with_ai=False)

    result = run(args.input, args.control_time, settings, args.output_dir)
    print(f"Run ID: {result['run_id']}")
    print(f"Всего: {result['articles_total']}")
    print(f"В периоде: {result['articles_in_period']}")
    print(f"Релевантных: {result['relevant_articles']}")
    print(f"Кластеров: {result['clusters']}")
    print(f"Извлечено событий: {len(result['events'])}")
    print(f"Выбрано: {len(result['selected'])}")
    print(f"AI calls: {result['ai_usage'].get('ai_calls')}")
    print(f"Tokens: {result['ai_usage'].get('usage')}")
    print(f"Estimated cost: {result['ai_usage'].get('estimated_cost')}")
    print(f"Валидация: {'OK' if not result['validation_errors'] and result['validation_report'].passed else 'NEEDS_REVIEW'}")
    if result["validation_errors"]:
        print("Ошибки проверки:")
        for error in result["validation_errors"]:
            print(f"  - {error}")
    if result["validation_warnings"]:
        print("Предупреждения:")
        for warning in result["validation_warnings"]:
            print(f"  - {warning}")
    print(f"Артефакты сохранены в: {args.output_dir}/")


if __name__ == "__main__":
    main()
