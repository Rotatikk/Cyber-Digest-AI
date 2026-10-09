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


def _optional_limit(value: str | None, default: str = "0") -> int | None:
    """Parse a positive limit; 0/blank/unlimited means no limit."""
    raw = default if value is None else value
    if raw is None or raw.strip().lower() in {"", "0", "none", "null", "unlimited", "без лимита", "-1"}:
        return None
    try:
        limit = int(raw)
    except ValueError:
        return None
    return limit if limit > 0 else None


def _env_bool(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() not in {"0", "false", "no", "off", ""}


@dataclass(frozen=True)
class Settings:
    ai_mode: str = os.getenv("AI_MODE", "openai")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-6-luna")
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", "").strip()
    max_ai_calls: int | None = _optional_limit(os.getenv("MAX_AI_CALLS"))
    max_preselect_clusters: int | None = _optional_limit(os.getenv("MAX_PRESELECT_CLUSTERS"))
    extraction_batch_size: int = int(os.getenv("EXTRACTION_BATCH_SIZE", "2"))
    openai_json_mode: bool = _env_bool("OPENAI_JSON_MODE", "1")
    openai_timeout: float = float(os.getenv("OPENAI_TIMEOUT", "60"))
    retry_requests: bool = _env_bool("OPENAI_RETRY_REQUESTS", "0")
    verify_with_ai: bool = os.getenv("VERIFY_WITH_AI", "1").lower() not in {"0", "false", "no"}
    retry_on_validation_error: bool = os.getenv("RETRY_ON_VALIDATION_ERROR", "1").lower() not in {"0", "false", "no"}
    validation_retry_count: int = max(0, min(2, int(os.getenv("VALIDATION_RETRY_COUNT", "1"))))
    prompt_version: str = os.getenv("PROMPT_VERSION", "2.2")
    input_price_per_1m: float | None = _optional_float(os.getenv("OPENAI_INPUT_PRICE_PER_1M"))
    output_price_per_1m: float | None = _optional_float(os.getenv("OPENAI_OUTPUT_PRICE_PER_1M"))

    def __post_init__(self) -> None:
        # Keep the same sentinel semantics for UI, CLI, .env and direct Settings usage.
        if self.max_ai_calls is not None and self.max_ai_calls <= 0:
            object.__setattr__(self, "max_ai_calls", None)
        if self.max_preselect_clusters is not None and self.max_preselect_clusters <= 0:
            object.__setattr__(self, "max_preselect_clusters", None)

    @property
    def openai_api_key(self) -> str | None:
        return os.getenv("OPENAI_API_KEY")


def parse_control_time(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=MSK)
    return dt.astimezone(MSK)
