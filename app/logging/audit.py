from __future__ import annotations

import csv
from pathlib import Path
from app.models import LogEntry

def write_log(entries: list[LogEntry], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["article_id", "status", "event_group", "reason", "errors"])
        writer.writeheader()
        for e in entries:
            writer.writerow({
                "article_id": e.article_id,
                "status": e.status,
                "event_group": e.event_group or "",
                "reason": e.reason,
                "errors": ";".join(e.errors),
            })
