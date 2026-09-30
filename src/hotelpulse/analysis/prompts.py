"""LLM tagging prompts (PRD section 12).

The system prompt must stay **verbatim** — eval numbers in the README are only
comparable while PROMPT_VERSION / this text stay fixed. Bump PROMPT_VERSION in
`analysis/config.py` whenever this changes.
"""

from __future__ import annotations

import json
from typing import Any

from hotelpulse.analysis.config import PROMPT_VERSION

# PRD section 12 — copy exactly, do not paraphrase.
SYSTEM_PROMPT = """You analyze hotel guest reviews. Reviews may be English, Hinglish (Hindi in Latin script), or regional languages.
For each review, extract mentions of these topics only: cleanliness, staff, food, wifi, ac, noise, location, value.
For each mention return: topic, sentiment (positive|negative|mixed), severity (1 minor, 2 clear, 3 severe; use 1 for positive), quote, quote_en.
Rules:
- quote MUST be copied exactly from the review text, under 200 characters. Do not edit it.
- quote_en is an English translation of quote. If quote is already English, repeat it.
- Only include a topic if the review clearly talks about it. Do not infer.
- One mention per topic per review. If mixed feelings on one topic, use "mixed".
- Return ONLY valid JSON, no prose, no markdown fences.
Output schema:
{"results":[{"review_id":"...","mentions":[{"topic":"...","sentiment":"...","severity":1,"quote":"...","quote_en":"..."}]}]}"""


def user_message(reviews: list[dict[str, Any]]) -> str:
    """Build the user message: JSON list of {review_id, text}."""
    payload = [{"review_id": r["review_id"], "text": r["text"]} for r in reviews]
    return json.dumps(payload, ensure_ascii=False)


def build_messages(reviews: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Chat-style messages list for one batch (system + user JSON payload)."""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message(reviews)},
    ]


__all__ = ["PROMPT_VERSION", "SYSTEM_PROMPT", "user_message", "build_messages"]
