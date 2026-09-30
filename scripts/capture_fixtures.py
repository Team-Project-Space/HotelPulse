"""Capture real SerpApi fixtures for Phase 1 box 6 (run once, ~2-3 credits).

Usage (from project root, after pasting SERPAPI_API_KEY into .env):

    py scripts/capture_fixtures.py "Hotel Name" "City"

Writes:
    tests/fixtures/maps_search.json
    tests/fixtures/maps_reviews.json

Then prove the cache by re-running without --refresh and checking
repo.api_calls_this_month() does not increase.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hotelpulse.config import get_settings  # noqa: E402
from hotelpulse.db import repo  # noqa: E402
from hotelpulse.db.connection import init_db  # noqa: E402
from hotelpulse.serp import maps, reviews_maps  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures"


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    name, city = sys.argv[1], sys.argv[2]
    settings = get_settings()
    if not settings.serpapi_api_key:
        print("SERPAPI_API_KEY is empty in .env — paste it first.")
        return 1

    init_db()
    before = repo.api_calls_this_month()
    print(f"api_calls_this_month before: {before}")

    candidates = maps.find_hotels(name, city, refresh=True)
    if not candidates:
        print(f"No hotels found for {name!r} in {city!r}.")
        return 1
    cand = candidates[0]
    print(f"Picked: {cand.name} data_id={cand.source_id} rating={cand.rating}")

    FIXTURES.mkdir(parents=True, exist_ok=True)
    # Re-fetch search response raw for the fixture (cached now, free).
    search_payload = repo.cache_get(
        repo.cache_key(
            "google_maps",
            {"engine": "google_maps", "type": "search", "q": f"{name}, {city}".strip().strip(",")},
        )
    )
    if search_payload is None:
        # Fall back to a second live call only if cache key mismatched.
        from hotelpulse.serp.client import cached_search

        search_payload = cached_search(
            "google_maps",
            {"type": "search", "q": f"{name}, {city}".strip().strip(",")},
            refresh=True,
        )
    (FIXTURES / "maps_search.json").write_text(
        json.dumps(search_payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Wrote {FIXTURES / 'maps_search.json'}")

    reviews_raw = reviews_maps.fetch_maps_reviews(cand.source_id, cap=8, max_pages=1, refresh=True)
    # Fixture is the raw one-page response shape the normalizer expects.
    # Reconstruct a minimal google_maps_reviews payload from the collected reviews
    # plus pagination metadata if available; prefer dumping via cache when present.
    review_key = repo.cache_key(
        "google_maps_reviews",
        {"engine": "google_maps_reviews", "data_id": cand.source_id, "sort_by": settings.sort_by_newest},
    )
    review_payload = repo.cache_get(review_key)
    if review_payload is None:
        review_payload = {
            "reviews": reviews_raw,
            "serpapi_pagination": {},
            "search_metadata": {"id": "manual-capture", "status": "Success"},
        }
    (FIXTURES / "maps_reviews.json").write_text(
        json.dumps(review_payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Wrote {FIXTURES / 'maps_reviews.json'} ({len(reviews_raw)} reviews)")

    after = repo.api_calls_this_month()
    print(f"api_calls_this_month after: {after} (spent {after - before})")
    print("Done. Next: re-run the same script WITHOUT refresh and confirm spend does not rise.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
