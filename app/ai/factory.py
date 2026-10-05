from app.ai.base import AIProvider
from app.ai.mock import MockAI
from app.config import Settings

def get_ai(settings: Settings) -> AIProvider:
    if settings.ai_mode == "openai":
        if not settings.openai_api_key:
            raise RuntimeError("AI_MODE=openai, но OPENAI_API_KEY не задан")
        from app.ai.openai_provider import OpenAIProvider
        return OpenAIProvider(settings.openai_model, settings.openai_api_key)
    return MockAI()
