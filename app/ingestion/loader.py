from __future__ import annotations

import json
from pathlib import Path
import pandas as pd
from app.models import Article

REQUIRED = ["id", "title", "text", "source", "url", "published_at"]

def _rows_from_file(path: Path) -> list[dict]:
    suffix = path.suffix.lower()
    if suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data = data.get("articles", [])
        return list(data)
    if suffix == ".csv":
        return pd.read_csv(path).fillna("").to_dict(orient="records")
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path).fillna("").to_dict(orient="records")
    raise ValueError(f"Неподдерживаемый формат: {suffix}")

def load_articles(path: str | Path) -> list[Article]:
    path = Path(path)
    rows = _rows_from_file(path)
    result: list[Article] = []
    for row in rows:
        payload = {key: row.get(key, "") for key in REQUIRED}
        result.append(Article.model_validate(payload))
    return result
