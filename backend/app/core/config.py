import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    app_name: str = "Utilities Platform"
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://utilities:change-me@localhost:5432/utilities_platform",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
