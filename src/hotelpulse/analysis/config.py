"""Phase 2 analysis config (PRD section 11/12).

Single source of truth for tagging and ranking constants. Ranking knobs are
re-exported from `hotelpulse.config` so env overrides keep working.
"""

from __future__ import annotations

from hotelpulse.config import get_settings

# Bump whenever prompts.py changes — tagged_reviews is keyed on this.
PROMPT_VERSION = "v1"

# Re-export ranking constants (PRD section 11) from app config.
RECENCY_HALF_LIFE_DAYS = get_settings().recency_half_life_days
MIN_MENTIONS = get_settings().min_mentions
LLM_BATCH_SIZE = get_settings().llm_batch_size

# Tagging model — free provider (Gemini Flash by default; Groq Llama fallback).
# Overridden by TAG_MODEL in .env. Old Claude ids are remapped in llm_client.
TAG_MODEL = get_settings().tag_model

# Quote length cap enforced in code as well as in the prompt.
MAX_QUOTE_CHARS = 200
