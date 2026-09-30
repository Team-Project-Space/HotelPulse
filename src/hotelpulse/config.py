"""Application configuration.

Environment values are read once at import time. `.env` is loaded if present so
that running from the project root works without exporting variables first.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

# Resolve the project root as <root>/src/hotelpulse/config.py -> <root>
PROJECT_ROOT = Path(__file__).resolve().parents[2]

load_dotenv(PROJECT_ROOT / ".env")


def _env_str(key: str, default: str = "") -> str:
    value = os.environ.get(key)
    return value.strip() if value and value.strip() else default


def _env_int(key: str, default: int) -> int:
    raw = _env_str(key)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(key: str, default: float) -> float:
    raw = _env_str(key)
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


class Settings:
    """Immutable-ish view of the runtime configuration.

    Read via the module-level `get_settings()` so tests can override env vars
    and then call `get_settings.cache_clear()`.
    """

    def __init__(self) -> None:
        # --- API keys -------------------------------------------------
        self.serpapi_api_key: str = _env_str("SERPAPI_API_KEY")
        # Free LLM providers. Gemini is preferred when both keys are present;
        # set LLM_PROVIDER=gemini|groq to force one.
        self.gemini_api_key: str = _env_str("GEMINI_API_KEY")
        self.groq_api_key: str = _env_str("GROQ_API_KEY")
        self.llm_provider_override: str = _env_str("LLM_PROVIDER").lower()

        # --- Models ---------------------------------------------------
        # Defaults track the free providers (Gemini Flash / Groq Llama).
        self.tag_model: str = _env_str("TAG_MODEL", "gemini-3.1-flash-lite")
        self.write_model: str = _env_str("WRITE_MODEL", "gemini-3.1-flash-lite")

        # --- Storage --------------------------------------------------
        db_path = _env_str("DB_PATH", "data/hotelpulse.db")
        db_file = Path(db_path)
        self.db_path: Path = db_file if db_file.is_absolute() else PROJECT_ROOT / db_file

        # --- Review caps ----------------------------------------------
        # Deliberately far below the PRD 100/40 defaults. At the SerpApi page
        # size of 8 reviews per request, 100 own + 4 competitors x 40 would
        # burn ~33 credits per run, i.e. ~7 runs per 250-credit month.
        self.max_reviews_own: int = _env_int("MAX_REVIEWS_OWN", 30)
        self.max_reviews_competitor: int = _env_int("MAX_REVIEWS_COMPETITOR", 10)

        # --- Credit budget guard rails --------------------------------
        self.serp_monthly_budget: int = _env_int("SERP_MONTHLY_BUDGET", 250)
        self.serp_hourly_budget: int = _env_int("SERP_HOURLY_BUDGET", 50)
        # Hard stop on pagination loops regardless of the review cap, so a
        # misconfigured cap can never drain the quota.
        self.max_pages_own: int = _env_int("MAX_PAGES_OWN", 8)
        self.max_pages_competitor: int = _env_int("MAX_PAGES_COMPETITOR", 3)

        # --- Ranking knobs (PRD 11) ------------------------------------
        self.recency_half_life_days: int = _env_int("RECENCY_HALF_LIFE_DAYS", 180)
        self.min_mentions: int = _env_int("MIN_MENTIONS", 3)

        # --- LLM batching (PRD 6.3) ------------------------------------
        self.llm_batch_size: int = _env_int("LLM_BATCH_SIZE", 12)

        # --- SerpApi behavioural defaults ------------------------------
        self.sort_by_newest: str = "newestFirst"
        self.nearby_zoom: int = _env_int("SERP_NEARBY_ZOOM", 14)
        self.serp_timeout: int = _env_int("SERP_TIMEOUT", 30)

    @property
    def serpapi_configured(self) -> bool:
        return bool(self.serpapi_api_key)

    @property
    def gemini_configured(self) -> bool:
        return bool(self.gemini_api_key)

    @property
    def groq_configured(self) -> bool:
        return bool(self.groq_api_key)

    @property
    def llm_configured(self) -> bool:
        """True when at least one free LLM key is present."""
        return bool(self.gemini_api_key or self.groq_api_key)

    @property
    def anthropic_configured(self) -> bool:
        """Deprecated alias — Anthropic is no longer used. Kept for old callers."""
        return False


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def reset_settings_cache() -> None:
    """Call after mutating os.environ in tests."""
    get_settings.cache_clear()
