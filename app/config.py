from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

load_dotenv()
MSK = ZoneInfo("Europe/Moscow")

@dataclass(frozen=True)
class Settings:
    ai_mode: str = os.getenv("AI_MODE", "openai")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-6-luna")
    max_ai_calls: int = int(os.getenv("MAX_AI_CALLS", "12"))
    openai_timeout: float = float(os.getenv("OPENAI_TIMEOUT", "60"))

    @property
    def openai_api_key(self) -> str | None:
        return os.getenv("OPENAI_API_KEY")

def parse_control_time(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=MSK)
    return dt.astimezone(MSK)
