"""LLM tagging engine (PRD section 6.3 / 12).

Batches reviews, calls a free LLM (Gemini Flash preferred, Groq fallback),
validates JSON with Pydantic, drops any mention whose quote is not a verbatim
substring of the review text, and stores results in SQLite via the repository.

Cost control: `repo.untagged_reviews()` filters out reviews already tagged at
the current PROMPT_VERSION, so they are never resent to the LLM.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterable, Sequence
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from hotelpulse.analysis.config import MAX_QUOTE_CHARS, PROMPT_VERSION, TAG_MODEL
from hotelpulse.analysis.llm_client import LLMClient, LLMClientError, get_llm_client
from hotelpulse.analysis.prompts import SYSTEM_PROMPT, user_message
from hotelpulse.config import get_settings
from hotelpulse.db import repo
from hotelpulse.models import Review, Sentiment, Topic, TopicMention

logger = logging.getLogger(__name__)


class LLMMention(BaseModel):
    """One topic mention as returned by the LLM (before quote validation)."""

    topic: str
    sentiment: str
    severity: int = Field(ge=1, le=3)
    quote: str
    quote_en: str | None = None


class LLMReviewResult(BaseModel):
    review_id: str
    mentions: list[LLMMention] = Field(default_factory=list)


class LLMTagResponse(BaseModel):
    results: list[LLMReviewResult] = Field(default_factory=list)


class TaggerError(RuntimeError):
    """Raised when the LLM cannot be reached or returns unusable output."""


# ---------------------------------------------------------------------------
# Quote validation (the critical rule)
# ---------------------------------------------------------------------------


def _normalize_ws(text: str) -> str:
    """Collapse all whitespace runs to single spaces and strip ends."""
    return re.sub(r"\s+", " ", text).strip()


def quote_matches(quote: str, review_text: str) -> bool:
    """True when `quote` appears in `review_text`.

    Exact substring first; then a whitespace-normalized match (LLMs often
    reflow line breaks). Never invents or repairs text — only verifies.
    """
    if not quote or not review_text:
        return False
    if len(quote) > MAX_QUOTE_CHARS:
        return False
    if quote in review_text:
        return True
    return _normalize_ws(quote) in _normalize_ws(review_text)


def validate_mentions(
    review: Review,
    raw_mentions: Sequence[LLMMention],
) -> tuple[list[TopicMention], int]:
    """Convert raw LLM mentions to TopicMention, dropping invalid ones.

    Returns (kept, dropped_count). Drops:
      - unknown topic or sentiment (Pydantic enum coercion fails)
      - quote not a verbatim substring of review.text
      - more than one mention for the same topic (keep the first)
    """
    kept: list[TopicMention] = []
    dropped = 0
    seen_topics: set[Topic] = set()

    for raw in raw_mentions:
        try:
            topic = Topic(raw.topic.lower().strip())
            sentiment = Sentiment(raw.sentiment.lower().strip())
        except ValueError:
            dropped += 1
            continue

        if topic in seen_topics:
            dropped += 1
            continue

        if not quote_matches(raw.quote, review.text):
            logger.warning(
                "dropping non-verbatim quote review_id=%s topic=%s quote=%r",
                review.review_id,
                topic.value,
                raw.quote[:80],
            )
            dropped += 1
            continue

        kept.append(
            TopicMention(
                review_id=review.review_id,
                topic=topic,
                sentiment=sentiment,
                severity=raw.severity,
                quote=raw.quote,
                quote_en=raw.quote_en,
            )
        )
        seen_topics.add(topic)

    return kept, dropped


# ---------------------------------------------------------------------------
# LLM client
# ---------------------------------------------------------------------------


def _default_client() -> LLMClient:
    """Build the active free LLM client (Gemini preferred, then Groq)."""
    try:
        return get_llm_client()
    except LLMClientError as exc:
        raise TaggerError(str(exc)) from exc


def _extract_text(response: Any) -> str:
    """Pull text out of a provider response object or plain string."""
    if isinstance(response, str):
        if not response:
            raise TaggerError("LLM returned an empty response.")
        return response
    # Defensive: tolerate SDK-shaped objects if a fake client returns them.
    text = getattr(response, "text", None)
    if text:
        return str(text)
    content = getattr(response, "content", None)
    if content is None and isinstance(response, dict):
        content = response.get("content") or response.get("text")
    if isinstance(content, str) and content:
        return content
    if content:
        parts: list[str] = []
        for block in content:
            t = getattr(block, "text", None)
            if t is None and isinstance(block, dict):
                t = block.get("text")
            if t:
                parts.append(str(t))
        if parts:
            return "\n".join(parts)
    raise TaggerError("LLM returned an empty response.")


def _strip_code_fences(text: str) -> str:
    """Remove markdown fences if the model added them despite instructions."""
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    return stripped


def parse_llm_json(text: str) -> LLMTagResponse:
    """Parse LLM output into LLMTagResponse. Raises TaggerError on bad JSON."""
    cleaned = _strip_code_fences(text)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise TaggerError(f"LLM returned invalid JSON: {exc}") from exc
    try:
        return LLMTagResponse.model_validate(data)
    except ValidationError as exc:
        raise TaggerError(f"LLM JSON failed schema validation: {exc}") from exc


def call_llm_batch(
    reviews: Sequence[Review],
    *,
    client: Any | None = None,
    model: str | None = None,
    max_tokens: int = 4096,
) -> LLMTagResponse:
    """One free-LLM call for a batch of reviews. Retry once on parse failure."""
    if not reviews:
        return LLMTagResponse(results=[])

    if client is None:
        try:
            client = get_llm_client(model=model or TAG_MODEL or None)
        except LLMClientError as exc:
            raise TaggerError(str(exc)) from exc
    elif model and hasattr(client, "model"):
        # Allow tests / callers to pin a model on an existing client.
        try:
            client.model = model
        except Exception:
            pass

    payload = [{"review_id": r.review_id, "text": r.text} for r in reviews]
    user_text = user_message(payload)

    last_error: TaggerError | None = None
    for attempt in range(2):
        try:
            if hasattr(client, "complete"):
                raw = client.complete(
                    system=SYSTEM_PROMPT,
                    user=user_text,
                    max_tokens=max_tokens,
                    temperature=0.0,
                )
            else:
                # Legacy/mock shape: client.messages.create(...)
                response = client.messages.create(
                    model=model or getattr(client, "model", TAG_MODEL),
                    max_tokens=max_tokens,
                    system=SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": user_text}],
                )
                raw = response
            text = _extract_text(raw)
            return parse_llm_json(text)
        except TaggerError as exc:
            last_error = exc
            logger.warning("tagger parse failure attempt=%d: %s", attempt + 1, exc)
        except Exception as exc:  # SDK errors — retry once, then bubble up
            last_error = TaggerError(f"LLM call failed: {exc}")
            logger.warning("tagger call failure attempt=%d: %s", attempt + 1, exc)

    raise last_error if last_error else TaggerError("LLM tagging failed.")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def batched(items: Sequence[Review], size: int) -> Iterable[list[Review]]:
    for i in range(0, len(items), size):
        yield list(items[i : i + size])


def tag_reviews(
    reviews: Sequence[Review],
    *,
    client: Any | None = None,
    prompt_version: str = PROMPT_VERSION,
    model: str | None = None,
    batch_size: int | None = None,
    persist: bool = True,
) -> list[TopicMention]:
    """Tag reviews that are not yet tagged at `prompt_version`.

    Already-tagged reviews are skipped (cost saving). Mentions with
    non-verbatim quotes are dropped. When `persist` is True, results are
    written via `repo.replace_mentions`.
    """
    size = batch_size or get_settings().llm_batch_size or 12
    pending = repo.untagged_reviews(list(reviews), prompt_version) if persist else list(reviews)
    if not pending:
        logger.info("tag_reviews: nothing untagged at %s", prompt_version)
        return []

    all_mentions: list[TopicMention] = []
    total_dropped = 0
    total_raw = 0

    for batch in batched(pending, size):
        try:
            parsed = call_llm_batch(batch, client=client, model=model)
        except TaggerError:
            logger.exception("batch failed; skipping %d reviews", len(batch))
            continue

        by_id = {r.review_id: r for r in batch}
        for result in parsed.results:
            review = by_id.get(result.review_id)
            if review is None:
                logger.warning("LLM returned unknown review_id=%s", result.review_id)
                continue
            total_raw += len(result.mentions)
            kept, dropped = validate_mentions(review, result.mentions)
            total_dropped += dropped
            all_mentions.extend(kept)
            if persist:
                repo.replace_mentions(review.review_id, kept, prompt_version)

        # Reviews the LLM omitted still get marked tagged (zero mentions).
        returned_ids = {r.review_id for r in parsed.results}
        if persist:
            for review in batch:
                if review.review_id not in returned_ids:
                    repo.replace_mentions(review.review_id, [], prompt_version)

    if total_raw:
        rate = total_dropped / total_raw
        logger.info(
            "tagged %d reviews: %d mentions kept, %d dropped (rate=%.1f%%)",
            len(pending),
            len(all_mentions),
            total_dropped,
            100 * rate,
        )
    return all_mentions


def tag_batch_offline(
    reviews: Sequence[Review],
    raw_payload: dict[str, Any],
    *,
    prompt_version: str = PROMPT_VERSION,
    persist: bool = False,
) -> list[TopicMention]:
    """Validate a pre-captured LLM payload without calling the API (tests/eval)."""
    parsed = LLMTagResponse.model_validate(raw_payload)
    by_id = {r.review_id: r for r in reviews}
    out: list[TopicMention] = []
    for result in parsed.results:
        review = by_id.get(result.review_id)
        if review is None:
            continue
        kept, _ = validate_mentions(review, result.mentions)
        out.extend(kept)
        if persist:
            repo.replace_mentions(review.review_id, kept, prompt_version)
    return out
