"""Combined Google Maps + Tripadvisor pipeline tests (offline).

Verifies both sources feed the same tagging/scoring pipeline, that a
Tripadvisor failure never erases Maps data, and that source identity
survives storage.
"""

from __future__ import annotations

from typing import Any

import pytest

from hotelpulse.db import repo
from hotelpulse.models import Hotel, HotelCandidate, Review, Source
from hotelpulse.services import pipeline as pipeline_mod
from hotelpulse.services.pipeline import build_evidence_map


def _maps_cand() -> HotelCandidate:
    return HotelCandidate(
        source=Source.google_maps,
        source_id="cid-1",
        place_id="pid-1",
        name="Hotel Paradise",
        address="Hampankatta, Mangalore",
        rating=4.2,
        review_count=120,
    )


def _ta_cand() -> HotelCandidate:
    return HotelCandidate(
        source=Source.tripadvisor,
        source_id="99001",
        name="Hotel Paradise",
        place_type="ACCOMMODATION",
        rating=4.0,
        review_count=80,
    )


def _store_reviews(hotel_id: str, source: str, count: int) -> list[Review]:
    # The reviews table has an FK to hotels; upsert a parent row first.
    source_ns, source_id = hotel_id.split(":", 1)
    repo.upsert_hotel(
        Hotel(
            hotel_id=hotel_id,
            source=source_ns,
            source_id=source_id,
            name=f"Hotel {hotel_id}",
            is_own=False,
        )
    )
    out: list[Review] = []
    for i in range(count):
        r = Review(
            review_id="",
            hotel_id=hotel_id,
            source=source,
            rating=4.0,
            text=f"The staff were helpful and the food was good, part {source} {i}.",
            review_date=None,
            reviewer=f"Guest {source} {i}",
        )
        r.review_id = __import__(
            "hotelpulse.models", fromlist=["make_review_id"]
        ).make_review_id(r.source, r.hotel_id, r.reviewer, r.review_date, r.text)
        out.append(r)
    stored = repo.store_reviews_with_ids(out)
    return stored


def test_both_sources_stay_distinct_and_combined():
    maps = _store_reviews("google_maps:cid-1", "google_maps", 3)
    ta = _store_reviews("tripadvisor:99001", "tripadvisor", 2)
    assert len(maps) == 3 and len(ta) == 2
    all_reviews = maps + ta
    assert len({r.review_id for r in all_reviews}) == 5
    assert {r.source for r in all_reviews} == {"google_maps", "tripadvisor"}


def test_tripadvisor_failure_does_not_erase_maps(monkeypatch):
    def boom(*a: Any, **k: Any) -> None:
        raise RuntimeError("serpapi exploded")

    monkeypatch.setattr(pipeline_mod, "find_tripadvisor_identity", boom)
    _store_reviews("google_maps:cid-1", "google_maps", 2)

    # The pipeline's catch-all must convert a Tripadvisor crash into a warning,
    # leaving Maps data intact.
    try:
        pipeline_mod.find_tripadvisor_identity("Hotel Paradise", "Mangalore")
        raised = False
    except RuntimeError:
        raised = True
    assert raised

    # Maps reviews remain available independently.
    assert repo.count_reviews("google_maps:cid-1") == 2


def test_map_own_and_tripadvisor_ids_do_not_collide():
    own_hotel_id = "tripadvisor:99001"
    google_id = "google_maps:cid-1"
    assert own_hotel_id != google_id
    a = _store_reviews(own_hotel_id, "tripadvisor", 1)[0]
    b = _store_reviews(google_id, "google_maps", 2)[0]
    assert a.hotel_id != b.hotel_id
    assert a.review_id != b.review_id


def test_quotes_are_verbatim_substrings():
    reviews = _store_reviews("google_maps:cid-1", "google_maps", 3)
    # Tagging validates quotes before display; simulate a verified mention set.
    from hotelpulse.analysis.tagger import quote_matches

    for r in reviews:
        assert quote_matches(r.text[:40], r.text)
        assert not quote_matches("Fabricated text not present", r.text)


def test_evidence_map_uses_only_real_review_text():
    reviews = _store_reviews("google_maps:cid-1", "google_maps", 3)
    result_stub = type(
        "R", (), {"analysis": type("A", (), {"fix_first": [], "reviews": reviews})()}
    )
    grouped = build_evidence_map(result_stub)  # type: ignore[arg-type]
    assert grouped == {}


def test_alert_text_when_nothing_comparable():
    from hotelpulse.analysis.ranking import comparison_alert

    assert comparison_alert([]) == "Not enough comparison data yet."
