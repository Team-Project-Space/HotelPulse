"""Normalization of raw SerpApi JSON into Pydantic models (PRD 17, rule 4).

Runs entirely offline. The `maps_*_sample` fixtures in tests/fixtures/ are
trimmed copies of real SerpApi response shapes; `inline_*` payloads cover the
edge cases those files do not contain.
"""

from __future__ import annotations

from datetime import date

import pytest

from hotelpulse.models import HotelCandidate, Source
from hotelpulse.serp import normalize


# ---------------------------------------------------------------------------
# dates
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("2026-09-12T13:48:47Z", date(2026, 9, 12)),
        ("2026-09-12T13:48:47+00:00", date(2026, 9, 12)),
        ("2026-09-12", date(2026, 9, 12)),
        ("2026-09-12 13:48:47", date(2026, 9, 12)),
        (date(2026, 9, 12), date(2026, 9, 12)),
        (None, None),
        ("", None),
        ("   ", None),
    ],
)
def test_parse_date_accepts_iso_forms(raw, expected):
    assert normalize.parse_date(raw) == expected


@pytest.mark.parametrize("raw", ["2 months ago", "last week", "yesterday", "a while back"])
def test_parse_date_refuses_to_invent_relative_dates(raw):
    """A guessed date would corrupt the recency weight in scoring (PRD 11)."""
    assert normalize.parse_date(raw) is None


# ---------------------------------------------------------------------------
# Google Maps places
# ---------------------------------------------------------------------------


def test_maps_candidate_from_realistic_place():
    raw = {
        "position": 1,
        "title": "Hotel Paradise",
        "data_id": "0x89c259a61c75684f:0x79d31adb123348d2",
        "place_id": "ChIJT2h1HKZZwokR0kgzEtsa03k",
        "rating": 4.2,
        "reviews": 1248,
        "address": "Hampankatta, Mangalore, Karnataka",
        "gps_coordinates": {"latitude": 12.9141, "longitude": 74.8560},
    }
    cand = HotelCandidate.from_maps_place(raw)
    assert cand is not None
    assert cand.source is Source.google_maps
    assert cand.source_id == "0x89c259a61c75684f:0x79d31adb123348d2"
    assert cand.name == "Hotel Paradise"
    assert cand.rating == 4.2
    assert cand.review_count == 1248  # SerpApi sends "1,248"
    assert (cand.lat, cand.lng) == (12.9141, 74.8560)
    assert cand.to_hotel(is_own=True).hotel_id == (
        "google_maps:0x89c259a61c75684f:0x79d31adb123348d2"
    )


def test_maps_candidates_read_local_results():
    response = {
        "local_results": [
            {"title": "A", "data_id": "0xA", "rating": 4.0, "reviews": 10},
            {"title": "B", "data_id": "0xB", "rating": 3.5, "reviews": 20},
        ]
    }
    assert [c.name for c in normalize.maps_candidates(response)] == ["A", "B"]


def test_maps_candidates_fall_back_to_place_results():
    """Google resolves some queries to one place and renames the key."""
    response = {"place_results": [{"title": "Solo", "data_id": "0xSOLO", "rating": 4.0}]}
    assert [c.name for c in normalize.maps_candidates(response)] == ["Solo"]


def test_place_results_may_be_a_single_dict_not_a_list():
    response = {"place_results": {"title": "Solo", "data_id": "0xSOLO"}}
    assert len(normalize.maps_candidates(response)) == 1


def test_local_results_takes_precedence_over_place_results():
    response = {
        "local_results": [{"title": "FromLocal", "data_id": "0x1"}],
        "place_results": [{"title": "FromPlace", "data_id": "0x2"}],
    }
    assert [c.name for c in normalize.maps_candidates(response)] == ["FromLocal"]


def test_maps_candidates_dedupe_repeated_places():
    response = {
        "local_results": [
            {"title": "Same", "data_id": "0xDUP"},
            {"title": "Same", "data_id": "0xDUP"},
        ]
    }
    assert len(normalize.maps_candidates(response)) == 1


@pytest.mark.parametrize(
    "entry",
    [
        {},                              # nothing
        {"title": "No data_id"},         # no identity
        {"data_id": "0x1"},              # no name
        {"title": "  ", "data_id": "0x1"},  # blank name
        "not a dict",
        None,
        42,
    ],
)
def test_unusable_place_entries_are_skipped_not_raised(entry):
    assert HotelCandidate.from_maps_place(entry) is None


def test_unusable_entries_are_filtered_out_of_a_list():
    response = {
        "local_results": [
            {"title": "Good", "data_id": "0x1"},
            {"title": "Bad"},          # no data_id
            "junk",
            {"title": "Also Good", "data_id": "0x2"},
        ]
    }
    assert [c.name for c in normalize.maps_candidates(response)] == ["Good", "Also Good"]


def test_maps_candidates_on_empty_response():
    assert normalize.maps_candidates({}) == []
    assert normalize.maps_candidates({"local_results": []}) == []


def test_junk_numeric_fields_become_none_rather_than_raising():
    cand = HotelCandidate.from_maps_place(
        {"title": "Junky", "data_id": "0x1", "rating": "N/A", "reviews": "many"}
    )
    assert cand is not None
    assert cand.rating is None
    assert cand.review_count is None


def test_missing_gps_coordinates_do_not_raise():
    cand = HotelCandidate.from_maps_place({"title": "No GPS", "data_id": "0x1"})
    assert cand is not None
    assert cand.lat is None and cand.lng is None


def test_malformed_gps_coordinates_do_not_raise():
    cand = HotelCandidate.from_maps_place(
        {"title": "Bad GPS", "data_id": "0x1", "gps_coordinates": "12.9,74.8"}
    )
    assert cand is not None
    assert cand.lat is None


# ---------------------------------------------------------------------------
# Google Maps reviews
# ---------------------------------------------------------------------------


def test_maps_review_field_mapping():
    raw = [
        {
            "review_id": "abc123",
            "snippet": "Rooms were not clean, especially the bathroom.",
            "rating": 1.0,
            "iso_date": "2026-09-12T13:48:47Z",
            "user": {"name": "Rahul Verma"},
        }
    ]
    reviews = normalize.maps_reviews_to_reviews(raw, "google_maps:0x1")
    assert len(reviews) == 1
    r = reviews[0]
    assert r.text == "Rooms were not clean, especially the bathroom."
    assert r.reviewer == "Rahul Verma"
    assert r.rating == 1.0
    assert r.review_date == date(2026, 9, 12)
    assert r.source == "google_maps"
    assert r.hotel_id == "google_maps:0x1"
    assert len(r.review_id) == 40  # sha1


def test_review_ids_are_deterministic_and_unique():
    raw = [
        {"snippet": "WiFi was slow.", "rating": 2, "user": {"name": "A"}},
        {"snippet": "Food was great.", "rating": 5, "user": {"name": "B"}},
    ]
    first = normalize.maps_reviews_to_reviews(raw, "google_maps:0x1")
    second = normalize.maps_reviews_to_reviews(raw, "google_maps:0x1")
    assert [r.review_id for r in first] == [r.review_id for r in second]
    assert len({r.review_id for r in first}) == 2


def test_identical_text_from_different_reviewers_gets_distinct_ids():
    raw = [
        {"snippet": "Same words.", "user": {"name": "Alice"}},
        {"snippet": "Same words.", "user": {"name": "Bob"}},
    ]
    reviews = normalize.maps_reviews_to_reviews(raw, "google_maps:0x1")
    assert len({r.review_id for r in reviews}) == 2


def test_review_without_iso_date_keeps_relative_date_unparsed():
    raw = [{"snippet": "No timestamp.", "date": "2 months ago", "user": {"name": "X"}}]
    assert normalize.maps_reviews_to_reviews(raw, "g:1")[0].review_date is None


def test_empty_snippet_falls_back_to_extracted_snippet():
    raw = [
        {
            "snippet": "",
            "extracted_snippet": {"original": "Full text recovered from extraction."},
            "user": {"name": "Z"},
        }
    ]
    assert normalize.maps_reviews_to_reviews(raw, "g:1")[0].text == (
        "Full text recovered from extraction."
    )


def test_reviews_without_text_are_dropped():
    """Unquotable text would only add noise to counts."""
    raw = [
        {"snippet": "   ", "user": {"name": "Empty"}},
        {"snippet": "", "user": {"name": "Also Empty"}},
        {"user": {"name": "No snippet key"}},
        "not a dict",
        None,
        {"snippet": "Real text.", "user": {"name": "Good"}},
    ]
    reviews = normalize.maps_reviews_to_reviews(raw, "g:1")
    assert len(reviews) == 1
    assert reviews[0].text == "Real text."


def test_missing_user_block_leaves_reviewer_none():
    raw = [{"snippet": "Anonymous feedback.", "rating": 3}]
    assert normalize.maps_reviews_to_reviews(raw, "g:1")[0].reviewer is None


def test_review_rating_string_is_coerced():
    raw = [{"snippet": "Fine.", "rating": "4", "user": {"name": "A"}}]
    assert normalize.maps_reviews_to_reviews(raw, "g:1")[0].rating == 4.0


def test_mixed_language_review_normalizes():
    raw = [
        {
            "snippet": "Wifi bahut slow tha, staff bahut accha tha.",
            "rating": 3,
            "iso_date": "2026-08-01T00:00:00Z",
            "user": {"name": "Rahul"},
            "language": "hi",
        }
    ]
    r = normalize.maps_reviews_to_reviews(raw, "g:1")[0]
    assert r.text.startswith("Wifi bahut slow")
    assert r.language == "hi"


# ---------------------------------------------------------------------------
# Tripadvisor
# ---------------------------------------------------------------------------


def test_tripadvisor_candidates_use_places_key():
    response = {
        "places": [
            {"title": "Hotel Paradise", "place_id": "187791", "location": "Mangalore"},
            {"title": "No Place Id"},
        ]
    }
    cands = normalize.tripadvisor_candidates(response)
    assert len(cands) == 1
    assert cands[0].source is Source.tripadvisor
    assert cands[0].source_id == "187791"
    assert cands[0].to_hotel().hotel_id == "tripadvisor:187791"


def test_tripadvisor_review_field_mapping():
    raw = [
        {
            "review_id": "ta-1",
            "snippet": "Great staff, but the AC was not working.",
            "rating": 3,
            "date": "2026-08-14",
            "original_language": "en",
            "author": {"display_name": "Priya S"},
        }
    ]
    r = normalize.tripadvisor_reviews_to_reviews(raw, "tripadvisor:187791")[0]
    assert r.text == "Great staff, but the AC was not working."
    assert r.reviewer == "Priya S"
    assert r.rating == 3.0
    assert r.review_date == date(2026, 8, 14)
    assert r.language == "en"
    assert r.source == "tripadvisor"


def test_tripadvisor_hotel_reply_is_not_treated_as_guest_text():
    """`reviews[].response` is the hotel's own reply."""
    raw = [
        {
            "review_id": "ta-2",
            "snippet": "The room was dirty.",
            "rating": 2,
            "date": "2026-08-14",
            "author": {"display_name": "Guest"},
            "response": {"snippet": "We apologise and have addressed this internally."},
        }
    ]
    r = normalize.tripadvisor_reviews_to_reviews(raw, "tripadvisor:1")[0]
    assert "apologise" not in r.text
    assert "addressed this internally" not in r.text
    assert r.text == "The room was dirty."


def test_tripadvisor_falls_back_to_trip_info_date():
    raw = [{"snippet": "Nice stay.", "rating": 5, "trip_info": {"date": "2026-07-01"}}]
    assert normalize.tripadvisor_reviews_to_reviews(raw, "tripadvisor:1")[0].review_date == (
        date(2026, 7, 1)
    )


def test_tripadvisor_empty_text_is_dropped():
    raw = [{"snippet": "", "author": {"display_name": "X"}}, {"snippet": "Real."}]
    assert len(normalize.tripadvisor_reviews_to_reviews(raw, "tripadvisor:1")) == 1


# ---------------------------------------------------------------------------
# both sources share one shape (PRD 6.2)
# ---------------------------------------------------------------------------


def test_both_sources_produce_the_same_review_shape():
    maps = normalize.maps_reviews_to_reviews(
        [{"snippet": "Clean room.", "rating": 5, "iso_date": "2026-09-01T00:00:00Z", "user": {"name": "A"}}],
        "x:1",
    )[0]
    trip = normalize.tripadvisor_reviews_to_reviews(
        [{"snippet": "Clean room.", "rating": 5, "date": "2026-09-01", "author": {"display_name": "A"}}],
        "x:2",
    )[0]
    assert set(maps.model_dump()) == set(trip.model_dump())
    assert maps.source != trip.source
    # Identical text and reviewer but different source -> different ids.
    assert maps.review_id != trip.review_id


# ---------------------------------------------------------------------------
# saved fixtures, when present
# ---------------------------------------------------------------------------


def test_maps_search_fixture_normalizes(load_fixture):
    from pathlib import Path

    if not (Path(__file__).parent / "fixtures" / "maps_search.json").exists():
        pytest.skip("maps_search.json not captured yet (see fixtures/README.md)")
    response = load_fixture("maps_search.json")
    cands = normalize.maps_candidates(response)
    assert cands, "a real response should yield at least one candidate"
    assert all(c.source_id for c in cands)


def test_maps_reviews_fixture_normalizes(load_fixture):
    from pathlib import Path

    if not (Path(__file__).parent / "fixtures" / "maps_reviews.json").exists():
        pytest.skip("maps_reviews.json not captured yet (see fixtures/README.md)")
    response = load_fixture("maps_reviews.json")
    raw = response.get("reviews", [])
    assert raw, "fixture should contain real reviews"
    reviews = normalize.maps_reviews_to_reviews(raw, "google_maps:fixture")
    assert reviews
    assert all(r.text.strip() for r in reviews)
    assert len({r.review_id for r in reviews}) == len(reviews)
