"""End-to-end analyze pipeline: search -> reviews -> LLM tags -> score -> rank.

Designed for Streamlit reruns: every expensive step is either cached (SerpApi)
or skipped (reviews already tagged at the current PROMPT_VERSION).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

from hotelpulse.analysis.config import PROMPT_VERSION
from hotelpulse.analysis.ranking import (
    comparison_alert,
    competitor_gap,
    fix_first,
    strengths,
    topic_label,
)
from hotelpulse.analysis.scoring import (
    MentionEvent,
    load_mention_events,
    overall_stats,
    score_all_topics,
)
from hotelpulse.analysis.tagger import TaggerError, tag_reviews
from hotelpulse.config import get_settings
from hotelpulse.db import repo
from hotelpulse.db.connection import init_db
from hotelpulse.models import (
    AnalysisResult,
    ApiBudget,
    ComparisonResult,
    Hotel,
    HotelCandidate,
    Source,
    Topic,
)
from hotelpulse.serp import maps, normalize, reviews_maps
from hotelpulse.serp.client import cache_hit_miss_counts
from hotelpulse.serp.identity import match_tripadvisor_listing
from hotelpulse.serp import tripadvisor as ta

logger = logging.getLogger(__name__)


def _log_stage(stage: str, started: float, **fields: Any) -> None:
    """One structured timing line per pipeline stage.

    Only counts, elapsed time, and cache/provider metadata are logged —
    never API keys, secrets, or review text.
    """
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    detail = " ".join(f"{k}={v}" for k, v in fields.items())
    logger.info("stage=%s elapsed_ms=%.1f %s", stage, elapsed_ms, detail)


def _cache_delta() -> tuple[int, int]:
    """Current (hits, misses) snapshot for before/after comparisons."""
    try:
        return cache_hit_miss_counts()
    except Exception:  # noqa: BLE001 — stats must never break the pipeline
        return (0, 0)


class PipelineError(RuntimeError):
    """User-facing failure (no hotel found, missing key, tagging failed hard)."""


@dataclass
class PipelineResult:
    analysis: AnalysisResult
    comparison: ComparisonResult
    budget: ApiBudget
    hotel_name: str
    city: str
    tagged_this_run: int = 0
    warnings: list[str] = field(default_factory=list)

    @property
    def hotel(self) -> Hotel:
        return self.analysis.hotel


def _budget() -> ApiBudget:
    settings = get_settings()
    used = repo.api_calls_this_month()
    budget = settings.serp_monthly_budget
    hits, misses = repo.cache_stats()
    return ApiBudget(
        calls_this_month=used,
        monthly_budget=budget,
        remaining=max(0, budget - used),
        cache_hits=hits,
        cache_misses=misses,
    )


def _pick_candidate(
    candidates: list[HotelCandidate],
    hotel_name: str,
    city: str,
) -> HotelCandidate:
    """Choose the best match for the owner's hotel name."""
    if not candidates:
        raise PipelineError(
            f"No Google Maps results for “{hotel_name}, {city}”. "
            "Try a different spelling or city."
        )
    needle = hotel_name.strip().lower()
    city_l = city.strip().lower()
    for cand in candidates:
        name_l = (cand.name or "").lower()
        if needle and needle in name_l:
            return cand
        if city_l and city_l in (cand.address or "").lower():
            return cand
    return candidates[0]


def _ensure_hotel(cand: HotelCandidate, *, is_own: bool) -> Hotel:
    hotel = cand.to_hotel(is_own=is_own)
    repo.upsert_hotel(hotel)
    return hotel


def _fetch_and_store_reviews(
    cand: HotelCandidate,
    hotel: Hotel,
    *,
    cap: int | None = None,
    max_pages: int | None = None,
    refresh: bool = False,
) -> int:
    settings = get_settings()
    if cand.source is Source.tripadvisor:
        raw = ta.fetch_tripadvisor_reviews(
            cand.source_id,
            cap=cap if cap is not None else settings.max_reviews_own,
            max_pages=max_pages if max_pages is not None else settings.max_pages_own,
            refresh=refresh,
        )
        reviews = normalize.tripadvisor_reviews_to_reviews(raw, hotel.hotel_id)
    else:
        raw = reviews_maps.fetch_maps_reviews(
            cand.source_id,
            cap=cap if cap is not None else settings.max_reviews_own,
            max_pages=max_pages if max_pages is not None else settings.max_pages_own,
            refresh=refresh,
        )
        reviews = normalize.maps_reviews_to_reviews(raw, hotel.hotel_id)
    stored = repo.store_reviews_with_ids(reviews)
    return len(stored)


def _tag_hotel(hotel_id: str, *, client=None) -> tuple[int, list[str]]:
    """Tag untagged reviews for one hotel. Returns (mentions_kept, warnings)."""
    warnings: list[str] = []
    reviews = repo.get_reviews_for_hotel(hotel_id)
    if not reviews:
        return 0, warnings
    try:
        mentions = tag_reviews(reviews, client=client, persist=True, prompt_version=PROMPT_VERSION)
        return len(mentions), warnings
    except TaggerError as exc:
        warnings.append(f"LLM tagging skipped for {hotel_id}: {exc}")
        return 0, warnings


def _score_hotel(
    hotel: Hotel,
    *,
    extra_events: list[MentionEvent] | None = None,
    extra_reviews: list | None = None,
) -> tuple[AnalysisResult, list[MentionEvent]]:
    # Tripadvisor reviews are stored under their own hotel_id (source identity
    # is preserved), but they describe the owner's hotel — so their tagged
    # mentions must contribute to the owner's topic scores, not just inflate
    # the review count. Callers pass them in via extra_events/extra_reviews.
    events = load_mention_events(hotel.hotel_id) + list(extra_events or [])
    reviews = repo.get_reviews_for_hotel(hotel.hotel_id) + list(extra_reviews or [])
    scores = score_all_topics(events)
    overall = overall_stats(reviews, events, average_rating=hotel.rating)
    analysis = AnalysisResult(
        hotel=hotel,
        reviews_analyzed=len(reviews),
        overall=overall,
        topic_scores=scores,
        fix_first=fix_first(scores, events),
        strengths=strengths(scores, events),
        reviews=reviews,
        data_updated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    return analysis, events


# ---------------------------------------------------------------------------
# Cross-source discovery: find the same hotel on Tripadvisor
# ---------------------------------------------------------------------------


def find_tripadvisor_identity(
    hotel_name: str,
    city: str,
    *,
    refresh: bool = False,
) -> HotelCandidate | None:
    """Locate our own hotel on Tripadvisor using conservative identity match.

    `find_tripadvisor_hotels` may return several listings; only one is accepted
    and only when it confidently belongs to the same hotel. A lookup failure
    never invalidates Google Maps data — callers simply get None.
    """
    settings = get_settings()
    if not settings.serpapi_api_key:
        return None
    try:
        candidates = ta.find_tripadvisor_hotels(hotel_name, city, refresh=refresh)
    except Exception as exc:  # noqa: BLE001 — search failure just means None
        logger.info("tripadvisor search failed for %s %s: %s", hotel_name, city, exc)
        return None
    result = match_tripadvisor_listing(hotel_name, [c for c in candidates if c.name])
    return result.candidate


def fetch_tripadvisor_reviews_for(
    hotel_name: str,
    city: str,
    *,
    cap: int | None = None,
    refresh: bool = False,
    identity: HotelCandidate | None = None,
) -> list:
    """Fetch Tripadvisor reviews for our own hotel and return stored Reviews.

    Pass a pre-identified `identity` candidate to skip the search. Reviews are
    stored under the Tripadvisor hotel_id ("tripadvisor:<place_id>"), never
    mixing with Google Maps hotel ids, and are tagged + scored together with
    Maps reviews by the dashboard via `get_all_own_reviews`. Raises nothing —
    an empty/failed Tripadvisor source just yields an empty list.
    """
    try:
        cand = identity or find_tripadvisor_identity(hotel_name, city, refresh=refresh)
        if cand is None:
            return []
        if not get_settings().serpapi_api_key:
            return []
        hotel = _ensure_hotel(cand, is_own=False)
        _fetch_and_store_reviews(
            cand,
            hotel,
            cap=cap if cap is not None else get_settings().max_reviews_own,
            max_pages=get_settings().max_pages_own,
            refresh=refresh,
        )
        _tag_hotel(hotel.hotel_id, client=None)
        return repo.get_reviews_for_hotel(hotel.hotel_id)
    except Exception as exc:  # noqa: BLE001 — Tripadvisor failure degrades, not breaks
        logger.warning("tripadvisor fetch skipped: %s", exc)
        return []


def analyze_hotel(
    hotel_name: str,
    city: str,
    *,
    refresh: bool = False,
    max_competitors: int = 2,
    competitor_reviews: int = 10,
    analyze_competitors: bool = True,
    client=None,
) -> PipelineResult:
    """Full PRD §10 pipeline for one hotel, with optional competitor comparison.

    Google Maps is the primary source. Tripadvisor is attempted next and is
    purely additive: when the listing identity is ambiguous or the request
    fails, a warning is recorded and Maps-only analysis continues.
    """
    settings = get_settings()
    if not settings.serpapi_api_key:
        raise PipelineError("SERPAPI_API_KEY is missing. Add it to .env and restart.")

    init_db()
    warnings: list[str] = []

    # One shared LLM client for the whole analysis. Previously every tagging
    # batch built its own provider client (SDK construction per batch); reuse
    # removes that overhead. When no provider is configured this stays None
    # and each batch is skipped exactly as before — no behaviour change.
    shared_client = client
    if shared_client is None:
        try:
            from hotelpulse.analysis.llm_client import LLMClientError, get_llm_client

            shared_client = get_llm_client()
        except Exception as exc:  # noqa: BLE001 — missing keys just mean untagged
            logger.info("no LLM provider configured; tagging will be skipped: %s", exc)
            shared_client = None

    t0 = time.perf_counter()
    candidates = maps.find_hotels(hotel_name, city, refresh=refresh)
    own_cand = _pick_candidate(candidates, hotel_name, city)
    own_hotel = _ensure_hotel(own_cand, is_own=True)
    logger.info("own hotel: %s (%s)", own_hotel.name, own_hotel.hotel_id)
    _log_stage("discovery", t0, candidates=len(candidates))

    t0 = time.perf_counter()
    hits0, misses0 = _cache_delta()
    _fetch_and_store_reviews(
        own_cand,
        own_hotel,
        refresh=refresh,
    )
    own_review_count = repo.count_reviews(own_hotel.hotel_id)
    hits1, misses1 = _cache_delta()
    _log_stage(
        "own_fetch",
        t0,
        reviews=own_review_count,
        cache_hits=hits1 - hits0,
        cache_misses=misses1 - misses0,
    )
    t0 = time.perf_counter()
    tagged_n, tag_warns = _tag_hotel(own_hotel.hotel_id, client=shared_client)
    warnings.extend(tag_warns)
    _log_stage(
        "own_tag",
        t0,
        mentions=tagged_n,
        provider=getattr(shared_client, "provider", None) or getattr(shared_client, "model", "test-double"),
    )

    # --- Tripadvisor (secondary source, never breaks the primary) -----------
    ta_identity: HotelCandidate | None = None
    ta_reviews: list = []
    ta_events: list[MentionEvent] = []
    t0 = time.perf_counter()
    hits0, misses0 = _cache_delta()
    try:
        ta_identity = find_tripadvisor_identity(hotel_name, city, refresh=refresh)
        if ta_identity is None:
            warnings.append(
                "Tripadvisor: no confident listing match found for this hotel — continuing with Google Maps reviews only."
            )
        else:
            ta_hotel = _ensure_hotel(ta_identity, is_own=False)
            ta_count = _fetch_and_store_reviews(
                ta_identity,
                ta_hotel,
                refresh=refresh,
            )
            _tag_hotel(ta_hotel.hotel_id, client=shared_client)
            ta_reviews = repo.get_reviews_for_hotel(ta_hotel.hotel_id)
            ta_events = load_mention_events(ta_hotel.hotel_id)
            logger.info("tripadvisor: %d reviews for %s", len(ta_reviews), ta_hotel.name)
    except Exception as exc:  # noqa: BLE001 — one source failing must not erase the other
        logger.warning("tripadvisor fetch failed: %s", exc)
        warnings.append(f"Tripadvisor fetch failed: {exc}")
    finally:
        hits1, misses1 = _cache_delta()
        _log_stage(
            "tripadvisor",
            t0,
            matched=ta_identity is not None,
            reviews=len(ta_reviews),
            mentions=len(ta_events),
            cache_hits=hits1 - hits0,
            cache_misses=misses1 - misses0,
        )

    t0 = time.perf_counter()
    analysis, own_events = _score_hotel(own_hotel, extra_events=ta_events, extra_reviews=ta_reviews)
    _log_stage("scoring", t0, mentions=len(own_events), topics=len(analysis.topic_scores))

    # --- competitors -------------------------------------------------------
    competitor_hotels: list[Hotel] = []
    competitor_score_lists = []
    t0 = time.perf_counter()
    comp_tagged = 0
    if analyze_competitors and max_competitors > 0:
        others = [c for c in candidates if c.source_id != own_cand.source_id][:max_competitors]
        for cand in others:
            try:
                hotel = _ensure_hotel(cand, is_own=False)
                _fetch_and_store_reviews(
                    cand,
                    hotel,
                    cap=competitor_reviews,
                    max_pages=1,
                    refresh=False,
                )
                n, _ = _tag_hotel(hotel.hotel_id, client=shared_client)
                comp_tagged += n
                scores = score_all_topics(load_mention_events(hotel.hotel_id))
                competitor_hotels.append(hotel)
                competitor_score_lists.append(scores)
            except Exception as exc:  # competitor failure must not sink the owner
                logger.warning("competitor %s failed: %s", cand.name, exc)
                warnings.append(f"Competitor “{getattr(cand, 'name', '?')}” skipped: {exc}")
    _log_stage(
        "competitors",
        t0,
        competitors=len(competitor_hotels),
        mentions=comp_tagged,
    )

    # Show topics the owner talks about, plus any competitor topic we scored.
    own_topics = [ts.topic for ts in analysis.topic_scores if ts.mention_count > 0]
    comp_topics = [
        ts.topic
        for scores in competitor_score_lists
        for ts in scores
        if ts.mention_count > 0
    ]
    focus: list[Topic] = list(dict.fromkeys(own_topics + comp_topics))
    rows = competitor_gap(analysis.topic_scores, competitor_score_lists, top_topics=focus or None)

    comparison = ComparisonResult(
        hotel_id=own_hotel.hotel_id,
        competitors=competitor_hotels,
        rows=rows,
        alert_text=comparison_alert(rows),
    )

    return PipelineResult(
        analysis=analysis,
        comparison=comparison,
        budget=_budget(),
        hotel_name=own_hotel.name,
        city=city,
        tagged_this_run=tagged_n,
        warnings=warnings,
    )


def build_evidence_map(result: PipelineResult) -> dict[str, list[dict]]:
    """Topic label -> evidence cards for the Streamlit modal."""
    grouped: dict[str, list[dict]] = {}
    for issue in result.analysis.fix_first:
        label = topic_label(issue.topic)
        cards = []
        for q in issue.quotes:
            review = next(
                (r for r in result.analysis.reviews if r.review_id == q.review_id),
                None,
            )
            cards.append(
                {
                    "quote": q.quote,
                    "source": (review.source if review else "google_maps").replace("_", " "),
                    "date": (
                        review.review_date.strftime("%d %b %Y")
                        if review and review.review_date
                        else "—"
                    ),
                    "reviewer": (review.reviewer if review and review.reviewer else "Guest"),
                    "sentiment": q.sentiment.value,
                    "severity": q.severity,
                }
            )
        if cards:
            grouped[label] = cards
    return grouped
