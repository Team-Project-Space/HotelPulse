"""Raw SerpApi JSON -> Pydantic models (PRD section 6.2).

Every source collapses into one `Review` shape so the analysis layer never
branches on source.

Field maps verified against the SerpApi docs:

Google Maps reviews (`google_maps_reviews`)
    text     reviews[].snippet              (extracted_snippet.original is fuller)
    reviewer reviews[].user.name
    rating   reviews[].rating
    date     reviews[].iso_date             (NOT the human "2 months ago" string)
    dedupe   reviews[].review_id

Tripadvisor reviews (`tripadvisor_reviews`)
    text     reviews[].snippet
    reviewer reviews[].author.display_name
    rating   reviews[].rating
    date     reviews[].date                 (already YYYY-MM-DD)
    dedupe   reviews[].review_id
    reviews[].response holds the *hotel's* reply and is stripped, since it is
    not guest text and would poison topic detection.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime
from typing import Any

from hotelpulse.models import HotelCandidate, Review, make_review_id

logger = logging.getLogger(__name__)

_ISO_TRAILING_Z = re.compile(r"[Zz]$")


# ---------------------------------------------------------------------------
# dates
# ---------------------------------------------------------------------------


def parse_date(value: Any) -> date | None:
    """Parse a SerpApi date into a `date`, or None.

    Accepts ISO timestamps (`2026-09-12T13:48:47Z`) and plain ISO dates.
    Relative strings like "2 months ago" are deliberately not parsed: inventing
    a date would corrupt the recency weighting in scoring, so those stay None
    and scoring falls back to `w = 0.5` per PRD section 11.
    """
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    text = str(value).strip()
    if not text:
        return None

    cleaned = _ISO_TRAILING_Z.sub("+00:00", text)
    try:
        return datetime.fromisoformat(cleaned).date()
    except ValueError:
        pass
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        logger.debug("unparseable date %r -> None", text)
        return None


# ---------------------------------------------------------------------------
# Google Maps
# ---------------------------------------------------------------------------


def maps_place_to_candidate(raw: dict[str, Any]) -> HotelCandidate | None:
    """Normalize one `local_results` / `place_results` entry."""
    return HotelCandidate.from_maps_place(raw)


def maps_candidates(response: dict[str, Any]) -> list[HotelCandidate]:
    """All usable hotel candidates in a maps search response."""
    for key in ("local_results", "place_results"):
        raw = response.get(key)
        if isinstance(raw, dict):
            raw = [raw]
        if isinstance(raw, list) and raw:
            out: list[HotelCandidate] = []
            seen: set[str] = set()
            for entry in raw:
                if not isinstance(entry, dict):
                    continue
                cand = maps_place_to_candidate(entry)
                if cand is None or cand.source_id in seen:
                    continue
                seen.add(cand.source_id)
                out.append(cand)
            return out
    return []


def maps_reviews_to_reviews(
    raw_reviews: list[dict[str, Any]],
    hotel_id: str,
    *,
    source: str = "google_maps",
    assign_ids: bool = True,
) -> list[Review]:
    """Normalize `google_maps_reviews` entries into `Review` models.

    Reviews with no usable text are dropped: they cannot be quoted and would
    only add noise to the counts.
    """
    out: list[Review] = []
    for raw in raw_reviews:
        if not isinstance(raw, dict):
            continue

        text = (raw.get("snippet") or raw.get("text") or "").strip()
        if not text:
            # Fall back to the fuller extracted snippet when snippet is empty.
            extracted = raw.get("extracted_snippet")
            if isinstance(extracted, dict):
                text = (extracted.get("original") or "").strip()
        if not text:
            logger.debug("dropping review with no text (%s)", raw.get("review_id"))
            continue

        user = raw.get("user")
        reviewer = None
        if isinstance(user, dict):
            reviewer = (user.get("name") or user.get("username") or "").strip() or None
        reviewer = reviewer or (raw.get("reviewer") or None)

        review = Review(
            review_id=str(raw.get("review_id") or "") if not assign_ids else "",
            hotel_id=hotel_id,
            source=source,
            rating=raw.get("rating"),
            text=text,
            review_date=parse_date(raw.get("iso_date") or raw.get("date")),
            reviewer=reviewer,
            language=raw.get("language"),
        )
        if assign_ids:
            review = review.model_copy(
                update={
                    "review_id": make_review_id(
                        review.source,
                        review.hotel_id,
                        review.reviewer,
                        review.review_date,
                        review.text,
                    )
                }
            )
        out.append(review)
    return out


# ---------------------------------------------------------------------------
# Tripadvisor
# ---------------------------------------------------------------------------


def tripadvisor_candidates(response: dict[str, Any]) -> list[HotelCandidate]:
    """Normalize a `tripadvisor` search response (`places[]`, not local_results)."""
    from hotelpulse.models import Source

    raw = response.get("places")
    raw = [raw] if isinstance(raw, dict) else raw
    if not isinstance(raw, list):
        return []

    out: list[HotelCandidate] = []
    seen: set[str] = set()
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        place_id = entry.get("place_id")
        name = (entry.get("title") or entry.get("name") or "").strip()
        if not place_id or not name:
            continue
        key = str(place_id)
        if key in seen:
            continue
        seen.add(key)
        out.append(
            HotelCandidate(
                source=Source.tripadvisor,
                source_id=key,
                name=name,
                address=(entry.get("location") or None),
                review_count=entry.get("reviews"),
                rating=entry.get("rating"),
            )
        )
    return out


def tripadvisor_reviews_to_reviews(
    raw_reviews: list[dict[str, Any]],
    hotel_id: str,
    *,
    source: str = "tripadvisor",
    assign_ids: bool = True,
) -> list[Review]:
    """Normalize `tripadvisor_reviews` entries into `Review` models.

    Strips `reviews[].response` (the hotel's own reply) so owner-authored text
    is never treated as guest sentiment.
    """
    out: list[Review] = []
    for raw in raw_reviews:
        if not isinstance(raw, dict):
            continue

        text = (raw.get("snippet") or raw.get("text") or "").strip()
        if not text:
            logger.debug("dropping tripadvisor review with no text (%s)", raw.get("review_id"))
            continue

        author = raw.get("author")
        reviewer = None
        if isinstance(author, dict):
            reviewer = (
                author.get("display_name") or author.get("username") or ""
            ).strip() or None
        reviewer = reviewer or raw.get("reviewer") or None

        trip_info = raw.get("trip_info")
        raw_date = raw.get("date")
        if not raw_date and isinstance(trip_info, dict):
            raw_date = trip_info.get("date")

        review = Review(
            review_id=str(raw.get("review_id") or "") if not assign_ids else "",
            hotel_id=hotel_id,
            source=source,
            rating=raw.get("rating"),
            text=text,
            review_date=parse_date(raw_date),
            reviewer=reviewer,
            language=raw.get("original_language") or raw.get("language"),
        )
        if assign_ids:
            review = review.model_copy(
                update={
                    "review_id": make_review_id(
                        review.source,
                        review.hotel_id,
                        review.reviewer,
                        review.review_date,
                        review.text,
                    )
                }
            )
        out.append(review)
    return out
