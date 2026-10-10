"""Offline regression tests for the Tripadvisor integration (PRD §6).

No live network — the SerpApi client fixture responds with inline payloads
shaped exactly like the documented API examples.
"""

from __future__ import annotations

from typing import Any

import pytest

from hotelpulse.models import Source
from hotelpulse.serp import normalize
from hotelpulse.serp.identity import match_tripadvisor_listing
from hotelpulse.serp import tripadvisor as ta


# ---------------------------------------------------------------------------
# Candidate parsing (engine=tripadvisor -> places[])
# ---------------------------------------------------------------------------


def _search_response(entries: list[dict[str, Any]]) -> dict[str, Any]:
    return {"search_metadata": {"id": "t1", "status": "Success"}, "places": entries}


def test_tripadvisor_hotel_listing_parsing():
    response = _search_response(
        [
            {
                "position": 1,
                "title": "Hotel Paradise",
                "place_id": 884213,
                "place_type": "ACCOMMODATION",
                "rating": 4.1,
                "reviews": 315,
                "location": "Mysuru, Karnataka, India",
            },
            {
                "position": 2,
                "title": "Mysuru",
                "place_id": 311111,
                "place_type": "GEO",
            },
        ]
    )
    cands = normalize.tripadvisor_candidates(response)
    usable = [c for c in cands if not c.place_type or c.place_type == "ACCOMMODATION"]
    assert len(usable) == 1
    assert usable[0].source is Source.tripadvisor
    assert usable[0].source_id == "884213"
    assert usable[0].name == "Hotel Paradise"
    assert usable[0].review_count == 315


def test_tripadvisor_candidates_reject_entries_without_place_id_or_title():
    response = _search_response(
        [
            {"title": "No id", "place_type": "ACCOMMODATION"},
            {"place_id": 999, "place_type": "ACCOMMODATION"},
            {"title": "ok", "place_id": 1000, "place_type": "ACCOMMODATION"},
        ]
    )
    cands = normalize.tripadvisor_candidates(response)
    assert [c.source_id for c in cands] == ["1000"]


def test_tripadvisor_candidates_dedupe_on_place_id():
    response = _search_response(
        [
            {"title": "Hotel A", "place_id": 42, "place_type": "ACCOMMODATION"},
            {"title": "Hotel A", "place_id": 42, "place_type": "ACCOMMODATION"},
        ]
    )
    cands = normalize.tripadvisor_candidates(response)
    assert len(cands) == 1


# ---------------------------------------------------------------------------
# Review normalization (engine=tripadvisor_reviews -> reviews[])
# ---------------------------------------------------------------------------


def _review(**over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "position": 1,
        "title": "Great stay",
        "snippet": "The staff were wonderful and the room was clean.",
        "rating": 5,
        "review_id": "1051450051",
        "date": "2026-02-28",
        "language": "en",
        "original_language": "en",
        "author": {"username": "carla", "display_name": "Carla Revill"},
    }
    base.update(over)
    return base


def test_tripadvisor_review_normalization_preserves_text_and_identity():
    raw = [_review()]
    reviews = normalize.tripadvisor_reviews_to_reviews(raw, "tripadvisor:884213")
    assert len(reviews) == 1
    r = reviews[0]
    assert r.source == "tripadvisor"
    assert r.hotel_id == "tripadvisor:884213"
    assert r.text.startswith("The staff were wonderful")
    # With assign_ids=True the id is the deterministic PRD §9 hash; a second
    # normalization of the same raw data must yield the same id so DB upserts
    # dedupe rather than duplicate.
    again = normalize.tripadvisor_reviews_to_reviews(raw, "tripadvisor:884213")
    assert again[0].review_id == r.review_id
    # With assign_ids=False the source's own review_id is preserved verbatim:
    raw_ids = normalize.tripadvisor_reviews_to_reviews(raw, "tripadvisor:884213", assign_ids=False)
    assert raw_ids[0].review_id == "1051450051"


def test_tripadvisor_owner_response_is_stripped():
    raw = [
        _review(
            response={
                "snippet": "Thank you for your feedback — we are sorry about the delay.",
                "date": "2026-03-01",
            }
        )
    ]
    reviews = normalize.tripadvisor_reviews_to_reviews(raw, "tripadvisor:884213")
    assert len(reviews) == 1
    assert "Thank you for your feedback" not in reviews[0].text


def test_tripadvisor_trip_info_date_fallback():
    raw = [_review(date=None, trip_info={"date": "2026-01-15", "type": "SOLO"})]
    reviews = normalize.tripadvisor_reviews_to_reviews(raw, "tripadvisor:1")
    assert reviews[0].review_date is not None
    assert reviews[0].review_date.isoformat() == "2026-01-15"


def test_tripadvisor_unparseable_date_is_none_not_guessed():
    raw = [_review(date="2 months ago", trip_info=None)]
    reviews = normalize.tripadvisor_reviews_to_reviews(raw, "tripadvisor:1")
    assert reviews[0].review_date is None


def test_tripadvisor_missing_optional_fields_do_not_raise():
    raw = [{"review_id": "1"}]  # no snippet, no author, no rating, no date
    reviews = normalize.tripadvisor_reviews_to_reviews(raw, "tripadvisor:1")
    assert reviews == []


def test_tripadvisor_malformed_entries_are_skipped():
    raw = [None, "not-a-dict", _review(), {"snippet": "", "review_id": "9"}]
    reviews = normalize.tripadvisor_reviews_to_reviews(raw, "tripadvisor:1")
    assert len(reviews) == 1


# ---------------------------------------------------------------------------
# Pagination and dedupe
# ---------------------------------------------------------------------------


def _reviews_response(reviews: list[dict[str, Any]], next_offset: int | None) -> dict[str, Any]:
    resp: dict[str, Any] = {"search_metadata": {"id": "r1"}, "reviews": reviews}
    if next_offset is not None:
        resp["serpapi_pagination"] = {
            "next": f"https://serpapi.com/search.json?engine=tripadvisor_reviews&offset={next_offset}&place_id=1"
        }
    return resp


def test_tripadvisor_pagination_and_termination():
    pages = {
        0: _reviews_response(
            [_review(review_id=str(100 + i)) for i in range(20)], next_offset=20
        ),
        20: _reviews_response(
            [_review(review_id=str(200 + i)) for i in range(20)], next_offset=None
        ),
    }

    def handler(params: dict[str, Any]) -> dict[str, Any]:
        return pages[params.get("offset", 0)]

    with _scripted_client(handler):
        raw = ta.fetch_tripadvisor_reviews("1", cap=40)
    assert len(raw) == 40


from contextlib import contextmanager


@contextmanager
def _scripted_client(handler):
    """Temporarily swap get_client for an offline scripted client."""
    from hotelpulse.serp import client as client_mod

    class _C:
        def __init__(self) -> None:
            self.calls: list[dict[str, Any]] = []

        def search(self, params: dict[str, Any]) -> dict[str, Any]:
            self.calls.append(dict(params))
            return handler(params)

    original = client_mod.get_client
    client_mod.get_client = lambda: _C()  # type: ignore[assignment]
    try:
        yield
    finally:
        client_mod.get_client = original


def test_tripadvisor_no_infinite_loop_when_next_repeats():
    """A server that keeps returning the same offset must not spin forever."""
    resp = _reviews_response([_review(review_id="1")], next_offset=0)  # repeats

    def handler(params: dict[str, Any]) -> dict[str, Any]:
        return resp

    with _scripted_client(handler):
        raw = ta.fetch_tripadvisor_reviews("1", cap=10)
    assert len(raw) == 1  # stops after the first page stops adding anything


def test_tripadvisor_duplicate_review_pages_dedupe():
    resp = _reviews_response([_review(review_id="dup") for _ in range(20)], next_offset=20)

    # Second page is identical to the first (server hiccup).
    pages = {0: resp, 20: resp}

    def handler(params: dict[str, Any]) -> dict[str, Any]:
        return pages[params.get("offset", 0)]

    with _scripted_client(handler):
        raw = ta.fetch_tripadvisor_reviews("1", cap=40)
    assert len(raw) == 1


def test_tripadvisor_empty_response_returns_nothing():
    def handler(params: dict[str, Any]) -> dict[str, Any]:
        return _reviews_response([], next_offset=None)

    with _scripted_client(handler):
        raw = ta.fetch_tripadvisor_reviews("1", cap=10)
    assert raw == []


def test_tripadvisor_malformed_response_kills_paging_gracefully():
    def handler(params: dict[str, Any]) -> dict[str, Any]:
        return {"search_metadata": {"id": "x"}}  # no "reviews" key at all

    with _scripted_client(handler):
        raw = ta.fetch_tripadvisor_reviews("1", cap=10)
    assert raw == []


# ---------------------------------------------------------------------------
# Identity matching
# ---------------------------------------------------------------------------


def _cand(name: str, source_id: str = "1"):
    from hotelpulse.models import HotelCandidate

    return HotelCandidate(
        source=Source.tripadvisor, source_id=source_id, name=name
    )


def test_identity_match_positive():
    result = match_tripadvisor_listing("OYO 123 Flagship Mysuru", [_cand("OYO 123 Flagship Mysuru")])
    assert result.candidate is not None
    assert result.confidence >= 0.55


def test_identity_numeric_suffix_protection():
    result = match_tripadvisor_listing(
        "OYO 123 Hotel Sunshine",
        [_cand("OYO 456 Hotel Sunshine")],
    )
    # The token "hotel"+"sunshine" would tie, but OYO-brand numbers differ — refuse.
    assert result.candidate is None


def test_identity_rejects_below_threshold():
    result = match_tripadvisor_listing(
        "Hotel Paradise Garden",
        [_cand("Paradise Beach Resort Mysuru")],
    )
    assert result.candidate is None


def test_identity_rejects_ambiguous_tie():
    result = match_tripadvisor_listing(
        "Hotel Paradise",
        [_cand("Hotel Paradise", "1"), _cand("Hotel Paradise", "2")],
    )
    assert result.candidate is None


def test_identity_empty_candidates():
    result = match_tripadvisor_listing("Hotel Paradise", [])
    assert result.candidate is None


# ---------------------------------------------------------------------------
# Source-aware cache keys and review id separation
# ---------------------------------------------------------------------------


def test_cache_key_distinguishes_engines():
    from hotelpulse.db import repo

    k1 = repo.cache_key("google_maps_reviews", {"data_id": "x"})
    k2 = repo.cache_key("tripadvisor_reviews", {"data_id": "x"})
    assert k1 != k2


def test_review_ids_differ_across_sources_for_same_text():
    from hotelpulse.models import make_review_id
    from datetime import date

    text = "The food was bad and the service was slow."
    google = normalize.maps_reviews_to_reviews(
        [{"review_id": "", "snippet": text, "rating": 2, "iso_date": "2026-01-01",
          "user": {"name": "Ravi"}}],
        "google_maps:1",
    )[0]
    trip = normalize.tripadvisor_reviews_to_reviews(
        [_review(snippet=text, review_id="", date="2026-01-01",
                 author={"display_name": "Ravi"})],
        "tripadvisor:1",
    )[0]
    assert google.review_id != trip.review_id
    assert google.source != trip.source
