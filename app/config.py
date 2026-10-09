from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

load_dotenv()
MSK = ZoneInfo("Europe/Moscow")


def _optional_float(value: str | None) -> float | None:
    if value is None or value.strip() == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


@dataclass(frozen=True)
class Settings:
    ai_mode: str = os.getenv("AI_MODE", "openai")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-6-luna")
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", "").strip()
    max_ai_calls: int = int(os.getenv("MAX_AI_CALLS", "12"))
    max_preselect_clusters: int = int(os.getenv("MAX_PRESELECT_CLUSTERS", "6"))
    openai_timeout: float = float(os.getenv("OPENAI_TIMEOUT", "60"))
    verify_with_ai: bool = os.getenv("VERIFY_WITH_AI", "1").lower() not in {"0", "false", "no"}
    prompt_version: str = os.getenv("PROMPT_VERSION", "2.1")
    input_price_per_1m: float | None = _optional_float(os.getenv("OPENAI_INPUT_PRICE_PER_1M"))
    output_price_per_1m: float | None = _optional_float(os.getenv("OPENAI_OUTPUT_PRICE_PER_1M"))

    @property
    def openai_api_key(self) -> str | None:
        return os.getenv("OPENAI_API_KEY")


def parse_control_time(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=MSK)
    return dt.astimezone(MSK)
