"""End-to-end analyze pipeline: search -> reviews -> LLM tags -> score -> rank.

Designed for Streamlit reruns: every expensive step is either cached (SerpApi)
or skipped (reviews already tagged at the current PROMPT_VERSION).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone

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
    Topic,
)
from hotelpulse.serp import maps, normalize, reviews_maps

logger = logging.getLogger(__name__)


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


def _score_hotel(hotel: Hotel) -> tuple[AnalysisResult, list[MentionEvent]]:
    events = load_mention_events(hotel.hotel_id)
    reviews = repo.get_reviews_for_hotel(hotel.hotel_id)
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
    """Full PRD §10 pipeline for one hotel, with optional competitor comparison."""
    settings = get_settings()
    if not settings.serpapi_api_key:
        raise PipelineError("SERPAPI_API_KEY is missing. Add it to .env and restart.")

    init_db()
    warnings: list[str] = []

    candidates = maps.find_hotels(hotel_name, city, refresh=refresh)
    own_cand = _pick_candidate(candidates, hotel_name, city)
    own_hotel = _ensure_hotel(own_cand, is_own=True)
    logger.info("own hotel: %s (%s)", own_hotel.name, own_hotel.hotel_id)

    _fetch_and_store_reviews(
        own_cand,
        own_hotel,
        refresh=refresh,
    )
    tagged_n, tag_warns = _tag_hotel(own_hotel.hotel_id, client=client)
    warnings.extend(tag_warns)

    analysis, own_events = _score_hotel(own_hotel)

    # --- competitors -------------------------------------------------------
    competitor_hotels: list[Hotel] = []
    competitor_score_lists = []
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
                _tag_hotel(hotel.hotel_id, client=client)
                scores = score_all_topics(load_mention_events(hotel.hotel_id))
                competitor_hotels.append(hotel)
                competitor_score_lists.append(scores)
            except Exception as exc:  # competitor failure must not sink the owner
                logger.warning("competitor %s failed: %s", cand.name, exc)
                warnings.append(f"Competitor “{getattr(cand, 'name', '?')}” skipped: {exc}")

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
