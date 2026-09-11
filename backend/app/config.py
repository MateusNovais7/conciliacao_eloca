from __future__ import annotations

import os
from functools import lru_cache


class Settings:
    def __init__(self) -> None:
        self.app_env: str = os.environ.get("APP_ENV", "development")
        self.database_url: str = os.environ.get("DATABASE_URL", "")
        self.secret_key: str = os.environ.get("SECRET_KEY", "")
        self.cors_origins: list[str] = [
            o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()
        ]
        self.api_key: str = os.environ.get("API_KEY", "")  # ver app/api/auth.py

        if self.app_env == "production":
            missing = [
                name for name, value in [
                    ("DATABASE_URL", self.database_url),
                    ("SECRET_KEY", self.secret_key),
                    ("API_KEY", self.api_key),
                ] if not value
            ]
            if missing:
                raise RuntimeError(
                    f"Variáveis de ambiente obrigatórias faltando em produção: {', '.join(missing)}"
                )


@lru_cache
def get_settings() -> Settings:
    return Settings()
