"""Runtime configuration loaded from environment variables.

Values are read once at startup so they are not hardcoded across modules.
"""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_path: str = os.environ.get("AQUAGUARD_DB", "aquaguard.db")
    token_secret: str = os.environ.get("AQUAGUARD_SECRET", "dev-only-change-me")
    token_ttl_seconds: int = int(os.environ.get("AQUAGUARD_TOKEN_TTL", "1800"))
    ai_deadline_seconds: float = float(os.environ.get("AQUAGUARD_AI_DEADLINE", "8"))
    ai_provider: str = os.environ.get("AQUAGUARD_AI_PROVIDER", "local")
    chat_limit_per_minute: int = int(os.environ.get("AQUAGUARD_CHAT_LIMIT", "6"))


def load_settings() -> Settings:
    return Settings()
