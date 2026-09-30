"""Google Maps search: find the owner's hotel and nearby competitors.

Engine `google_maps`. Verified API details:
  * `type=search` + `q` are required for a list; `ll=@<lat>,<lng>,<zoom>z`
    optionally biases results and is only honoured with `type=search`.
  * Places appear under `local_results`, but Google sometimes resolves to a
    single place and returns `place_results` instead. Both are handled.
  * `data_id` is the identifier the reviews engine needs; `place_id` is the
    Google CID namespace equivalent.
"""

from __future__ import annotations

import logging
from typing import Any

from hotelpulse.models import HotelCandidate
from hotelpulse.serp.client import cached_search

logger = logging.getLogger(__name__)

ENGINE = "google_maps"


def _extract_places(response: dict[str, Any]) -> list[dict[str, Any]]:
    """Pull place entries from whichever key the response used.

    Prefers `local_results`, falls back to `place_results`, and tolerates a
    single dict rather than a list under either key.
    """
    for key in ("local_results", "place_results"):
        raw = response.get(key)
        if isinstance(raw, dict):
            raw = [raw]
        if isinstance(raw, list) and raw:
            return [r for r in raw if isinstance(r, dict)]
    return []


def _candidates(response: dict[str, Any]) -> list[HotelCandidate]:
    out: list[HotelCandidate] = []
    seen: set[str] = set()
    for raw in _extract_places(response):
        cand = HotelCandidate.from_maps_place(raw)
        if cand is None:
            continue
        # Google can repeat a place across pages; keep the first sighting.
        if cand.source_id in seen:
            continue
        seen.add(cand.source_id)
        out.append(cand)
    return out


def find_hotels(name: str, city: str, *, refresh: bool = False) -> list[HotelCandidate]:
    """Search for hotels matching `name` in `city`.

    Returns an empty list when nothing matched; the caller decides whether
    that is an error worth surfacing.
    """
    query = f"{name}, {city}".strip().strip(",")
    response = cached_search(ENGINE, {"type": "search", "q": query}, refresh=refresh)
    results = _candidates(response)
    logger.info("find_hotels(%r, %r) -> %d candidates", name, city, len(results))
    return results


def find_nearby(
    lat: float,
    lng: float,
    *,
    zoom: int = 14,
    query: str = "hotel",
    refresh: bool = False,
) -> list[HotelCandidate]:
    """Find hotels near a coordinate, for competitor selection (PRD 6.1)."""
    response = cached_search(
        ENGINE,
        {"type": "search", "q": query, "ll": f"@{lat},{lng},{zoom}z"},
        refresh=refresh,
    )
    results = _candidates(response)
    logger.info("find_nearby(%s,%s) -> %d candidates", lat, lng, len(results))
    return results


def find_by_data_id(data_id: str, *, refresh: bool = False) -> HotelCandidate | None:
    """Look up one place by `data_id`/`data_cid` without a text query."""
    response = cached_search(ENGINE, {"data_cid": data_id}, refresh=refresh)
    results = _candidates(response)
    return results[0] if results else None


def pick_own_hotel(
    candidates: list[HotelCandidate],
    name: str,
) -> HotelCandidate | None:
    """Best-effort match of the typed name against search candidates.

    Scored on how much of the typed name appears in the candidate name, with a
    nudge toward higher-rated places, so an exact-ish match wins over a
    similarly-named 2-star. Returns None for an empty candidate list.
    """
    if not candidates:
        return None

    needle = name.strip().lower()
    if not needle:
        return candidates[0]

    def score(cand: HotelCandidate) -> tuple[float, float]:
        hay = cand.name.lower()
        if hay == needle:
            exact = 2.0
        elif needle in hay:
            exact = 1.5
        elif hay in needle:
            exact = 1.0
        else:
            # Token overlap catches "Hotel Paradise" vs "Paradise Residency".
            tokens = [t for t in needle.split() if len(t) > 2]
            hits = sum(1 for t in tokens if t in hay)
            exact = hits / len(tokens) if tokens else 0.0
        return (exact, cand.rating or 0.0)

    ranked = sorted(candidates, key=score, reverse=True)
    best = ranked[0]
    if score(best)[0] <= 0.0:
        return None
    return best
