"""Google Maps reviews with pagination and a hard cap (PRD section 6.1).

Verified API details that shaped this module:
  * engine `google_maps_reviews`, taking `data_id` or `place_id`.
  * Pagination is `serpapi_pagination.next_page_token`; the `start` offset is
    discontinued for this engine.
  * The first page returns 8 reviews and `num` is rejected on it, so a cap of
    N costs about ceil(N / 8) credits. Caps are enforced here rather than
    trusted from config, and a page-count guard backstops them.
"""

from __future__ import annotations

import logging
from typing import Any

from hotelpulse.config import get_settings
from hotelpulse.serp.client import cached_search

logger = logging.getLogger(__name__)

ENGINE = "google_maps_reviews"

# SerpApi returns 8 reviews on the first page and up to 20 on later pages.
FIRST_PAGE_SIZE = 8


def _next_page_token(response: dict[str, Any]) -> str | None:
    token = (response.get("serpapi_pagination") or {}).get("next_page_token")
    return str(token) if token else None


def fetch_maps_reviews(
    data_id: str,
    cap: int | None = None,
    *,
    max_pages: int | None = None,
    refresh: bool = False,
) -> list[dict[str, Any]]:
    """Fetch up to `cap` raw review dicts for one place.

    Each page costs a credit, so this stops at whichever comes first: the cap,
    `max_pages`, an exhausted `next_page_token`, or a page that adds nothing
    new.

    Args:
        data_id: the place's `data_id` from the maps search.
        cap: maximum reviews to return. Defaults to `MAX_REVIEWS_OWN`.
        max_pages: hard page limit. Defaults to `MAX_PAGES_OWN`.
        refresh: bypass the cache and force live calls (spends credits).
    """
    settings = get_settings()
    limit = settings.max_reviews_own if cap is None else cap
    page_limit = settings.max_pages_own if max_pages is None else max_pages

    if limit <= 0:
        return []

    collected: list[dict[str, Any]] = []
    seen: set[str] = set()
    token: str | None = None
    pages = 0

    while pages < page_limit and len(collected) < limit:
        params: dict[str, Any] = {
            "data_id": data_id,
            "sort_by": settings.sort_by_newest,
        }
        if token:
            params["next_page_token"] = token

        response = cached_search(ENGINE, params, refresh=refresh)
        pages += 1

        batch = response.get("reviews")
        batch = batch if isinstance(batch, list) else []
        if not batch:
            break

        new_in_page = 0
        for raw in batch:
            if not isinstance(raw, dict):
                continue
            # review_id is the documented dedupe key across pages.
            key = str(raw.get("review_id") or "")
            if not key:
                key = str(raw.get("user", {}).get("contributor_id", "")) + str(raw.get("snippet", ""))[:80]
            if key in seen:
                continue
            seen.add(key)
            collected.append(raw)
            new_in_page += 1
            if len(collected) >= limit:
                break

        if new_in_page == 0:
            logger.info("page %d added no new reviews; stopping", pages)
            break

        token = _next_page_token(response)
        if not token:
            break

    logger.info(
        "fetch_maps_reviews(data_id=%s) -> %d reviews over %d page(s)",
        data_id,
        len(collected),
        pages,
    )
    return collected[:limit]


def estimate_credits(cap: int, *, first_page_size: int = FIRST_PAGE_SIZE) -> int:
    """Rough credit cost of fetching `cap` reviews. Used by the sidebar hint."""
    if cap <= 0:
        return 0
    return max(1, -(-cap // first_page_size))
