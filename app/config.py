"""
Central configuration. Loads env vars once, validates required ones are
present, and exposes typed constants for the rest of the app to import.
"""
import os
from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Missing required environment variable: {name}. "
            f"Copy .env.example to .env and fill it in."
        )
    return value


class Settings:
    # Supabase
    SUPABASE_URL: str = _require("SUPABASE_URL")
    SUPABASE_SERVICE_KEY: str = _require("SUPABASE_SERVICE_KEY")

    # Groq (LLM calls for decomposition/ranking-explanation/workflow/architecture)
    GROQ_API_KEY: str = _require("GROQ_API_KEY")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    # GitHub (optional but strongly recommended — unauthenticated rate
    # limit is 60 req/hr and ingestion will blow through that instantly)
    GITHUB_TOKEN: str | None = os.getenv("GITHUB_TOKEN")

    APP_ENV: str = os.getenv("APP_ENV", "development")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "info")

    # Ranking weights — kept here (not buried in rank.py) so they're easy
    # to tune and easy to point judges to as "the deterministic formula"
    RANK_WEIGHT_STARS: float = 0.4
    RANK_WEIGHT_RECENCY: float = 0.3
    RANK_WEIGHT_ISSUE_HEALTH: float = 0.3

    # How many candidate MCPs to fetch per capability before ranking
    MATCH_CANDIDATES_PER_CAPABILITY: int = 8

    # How many top-ranked MCPs to return per capability after ranking
    TOP_N_PER_CAPABILITY: int = 3


settings = Settings()