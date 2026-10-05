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
    args = p.parse_args()
    settings = Settings()
    if args.ai_mode:
        settings = replace(settings, ai_mode=args.ai_mode)
    if args.model:
        settings = replace(settings, openai_model=args.model)
    if args.base_url is not None:
        settings = replace(settings, openai_base_url=args.base_url.strip())
    result = run(args.input, args.control_time, settings, args.output_dir)
    print(f"Всего: {result['articles_total']}")
    print(f"В периоде: {result['articles_in_period']}")
    print(f"Релевантных: {result['relevant_articles']}")
    print(f"Событий: {len(result['events'])}")
    print(f"Выбрано: {len(result['selected'])}")
    print(f"AI calls: {result['ai_usage'].get('ai_calls')}")
    print(f"Tokens: {result['ai_usage'].get('usage')}")
    print("Проверка: OK")

if __name__ == "__main__":
    main()
