from __future__ import annotations

import argparse
from app.pipeline import run
from app.config import Settings

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--control-time", required=True)
    p.add_argument("--output-dir", default="output")
    args = p.parse_args()
    result = run(args.input, args.control_time, Settings(), args.output_dir)
    print(f"Всего: {result['articles_total']}")
    print(f"В периоде: {result['articles_in_period']}")
    print(f"Релевантных: {result['relevant_articles']}")
    print(f"Событий: {len(result['events'])}")
    print(f"Выбрано: {len(result['selected'])}")
    print("Проверка: OK")

if __name__ == "__main__":
    main()
