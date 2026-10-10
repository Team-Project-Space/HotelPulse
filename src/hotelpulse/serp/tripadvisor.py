"""Tripadvisor search + reviews via SerpApi.

API details verified against serpapi.com docs on 2026-10-10:

* `engine=tripadvisor` — hotel discovery. Required `q`; `ssrc=h` restricts to
  hotels. `places[]` entries carry `title`, `place_id` (Tripadvisor numeric)
  and `place_type`; hotels report `place_type=ACCOMMODATION`. Pagination is
  offset-based (`offset` steps by `limit`, default 30) but a first page with
  ~30 hotels is plenty for one request, so this module never pages the search.
* `engine=tripadvisor_reviews` — reviews for one Tripadvisor `place_id`.
  `limit` max is 20, so a cap of N costs about ceil(N / 20) credits. Pagination
  is offset-based too; `serpapi_pagination.next` carries a URL whose
  `offset` query param gives the next page (there is no next_page_token).
  `sort_by=most_recent` is the documented default and is what we want.
* `reviews[].response` is the *hotel's* reply — normalize strips it.
* Date fields: `reviews[].date` (YYYY-MM-DD), plus `trip_info.date` fallback,
  both handled by `normalize.tripadvisor_reviews_to_reviews`.
* The `translate` and `original_language` *parameters* were discontinued —
  we never send them.
"""

from __future__ import annotations

import logging
import math
from typing import Any
from urllib.parse import parse_qs, urlparse

from hotelpulse.config import get_settings
from hotelpulse.serp import normalize
from hotelpulse.serp.client import cached_search

logger = logging.getLogger(__name__)

SEARCH_ENGINE = "tripadvisor"
REVIEWS_ENGINE = "tripadvisor_reviews"

# Documented maximum per request for the reviews engine.
MAX_LIMIT_PER_REQUEST = 20


def find_tripadvisor_hotels(
    name: str,
    city: str,
    *,
    refresh: bool = False,
) -> list:
    """Search Tripadvisor for hotels matching `name` in `city`.

    Returns `HotelCandidate`s (source=tripadvisor) or an empty list when no
    listing matched. `ssrc=h` keeps the results to hotel accommodations; mixed
    place types (cities, attractions) are filtered out by name, not by
    assumption — the identity matcher in `identity.py` is the authority.
    """
    from hotelpulse.models import HotelCandidate

    query = f"{name} {city}".strip()
    response = cached_search(
        SEARCH_ENGINE,
        {"q": query, "ssrc": "h"},
        refresh=refresh,
    )
    results = normalize.tripadvisor_candidates(response)
    # Only genuine accommodations are usable — a `GEO` result (the *city*
    # itself) would drag in every review for the wrong entity. The Tripadvisor
    # search docs list `place_type=ACCOMMODATION` for hotels. Responses with
    # no place_type at all are kept; the identity matcher still applies.
    return [r for r in results if not r.place_type or r.place_type == "ACCOMMODATION"]


def _offset_from_next(response: dict[str, Any]) -> int | None:
    """Read the offset hidden in `serpapi_pagination.next`'s URL, if present."""
    pagination = response.get("serpapi_pagination") or {}
    next_url = pagination.get("next")
    if not next_url:
        return None
    try:
        parsed = urlparse(str(next_url))
        qs = parse_qs(parsed.query)
        offsets = qs.get("offset")
        if offsets:
            return int(offsets[0])
    except (ValueError, TypeError):
        return None
    return None


def fetch_tripadvisor_reviews(
    place_id: str,
    cap: int | None = None,
    *,
    max_pages: int | None = None,
    refresh: bool = False,
) -> list[dict[str, Any]]:
    """Fetch up to `cap` raw Tripadvisor review dicts for one `place_id`.

    Stops at whichever comes first: the cap, `max_pages`, an exhausted
    `serpapi_pagination.next`, or a page that adds nothing new. Each page costs
    one credit; `limit` is capped at 20 (the documented maximum).
    """
    settings = get_settings()
    limit = settings.max_reviews_own if cap is None else cap
    page_limit = settings.max_pages_own if max_pages is None else max_pages

    if limit <= 0:
        return []

    collected: list[dict[str, Any]] = []
    seen: set[str] = set()
    offset = 0
    pages = 0

    while pages < page_limit and len(collected) < limit:
        page_size = min(MAX_LIMIT_PER_REQUEST, limit - len(collected))
        params: dict[str, Any] = {
            "place_id": str(place_id),
            "sort_by": "most_recent",
            "limit": page_size,
            "offset": offset,
        }
        response = cached_search(REVIEWS_ENGINE, params, refresh=refresh)
        pages += 1

        batch = response.get("reviews")
        batch = batch if isinstance(batch, list) else []
        if not batch:
            break

        new_in_page = 0
        for raw in batch:
            if not isinstance(raw, dict):
                continue
            key = str(raw.get("review_id") or "")
            if not key:
                # Last resort: sha of recognizable fields. Never invents data.
                key = f"{raw.get('date', '')}:{str(raw.get('snippet', ''))[:80]}"
            if key in seen:
                continue
            seen.add(key)
            collected.append(raw)
            new_in_page += 1
            if len(collected) >= limit:
                break

        if new_in_page == 0:
            logger.info("tripadvisor page at offset %d added nothing new; stopping", offset)
            break

        next_offset = _offset_from_next(response)
        if next_offset is None or next_offset <= offset:
            break
        offset = next_offset

    logger.info(
        "fetch_tripadvisor_reviews(place_id=%s) -> %d reviews over %d page(s)",
        place_id,
        len(collected),
        pages,
    )
    return collected[:limit]


def estimate_credits(cap: int) -> int:
    """Rough credit cost of fetching `cap` Tripadvisor reviews (20/page)."""
    if cap <= 0:
        return 0
    return max(1, math.ceil(cap / MAX_LIMIT_PER_REQUEST))
