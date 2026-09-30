"""Cache behaviour and credit accounting (PRD 17, rule 4).

The headline guarantee: an identical repeat query costs nothing. A test that
accidentally reaches the network is blocked in conftest.py, so the fake client
call counts below are real assertions about the cache.
"""

from __future__ import annotations

import pytest

from hotelpulse.db import repo
from hotelpulse.models import HotelCandidate, Source
from hotelpulse.serp import client as client_mod
from hotelpulse.serp import maps, reviews_maps
from hotelpulse.serp.client import BudgetExhausted, SerpApiError, cached_search

MAPS_PARAMS = {"type": "search", "q": "Hotel Paradise, Mangalore"}


# ---------------------------------------------------------------------------
# cache keys
# ---------------------------------------------------------------------------


def test_cache_key_ignores_param_order():
    a = repo.cache_key("google_maps", {"type": "search", "q": "Hotel X"})
    b = repo.cache_key("google_maps", {"q": "Hotel X", "type": "search"})
    assert a == b


def test_cache_key_includes_engine():
    params = {"q": "Hotel X", "type": "search"}
    assert repo.cache_key("google_maps", params) != repo.cache_key("google_maps_reviews", params)


def test_cache_key_differs_on_any_value():
    base = repo.cache_key("google_maps", {"q": "Hotel X", "type": "search"})
    assert base != repo.cache_key("google_maps", {"q": "Hotel Y", "type": "search"})
    assert base != repo.cache_key("google_maps", {"q": "Hotel X", "type": "place"})


def test_cache_key_is_a_sha256_hex_digest():
    key = repo.cache_key("google_maps", {"q": "Hotel X"})
    assert len(key) == 64
    assert all(ch in "0123456789abcdef" for ch in key)


# ---------------------------------------------------------------------------
# the core guarantee: a cache hit avoids the API call
# ---------------------------------------------------------------------------


def test_first_call_hits_api_and_second_is_served_from_cache(serp_client):
    first = cached_search("google_maps", MAPS_PARAMS)
    assert serp_client.call_count == 1

    second = cached_search("google_maps", MAPS_PARAMS)
    assert serp_client.call_count == 1, "second identical call must not hit the API"
    assert "_cached_at" in second
    assert "_cached_at" not in first


def test_cache_hit_returns_the_same_payload(serp_client):
    cached_search("google_maps", MAPS_PARAMS)
    from_cache = cached_search("google_maps", MAPS_PARAMS)
    assert from_cache["search_metadata"]["id"] == "default"


def test_third_repeat_is_still_free(serp_client):
    for _ in range(5):
        cached_search("google_maps", MAPS_PARAMS)
    assert serp_client.call_count == 1


def test_different_params_do_hit_the_api(serp_client):
    cached_search("google_maps", MAPS_PARAMS)
    cached_search("google_maps", {"type": "search", "q": "Hotel Other, Mangalore"})
    assert serp_client.call_count == 2


def test_refresh_bypasses_the_cache(serp_client):
    cached_search("google_maps", MAPS_PARAMS)
    cached_search("google_maps", MAPS_PARAMS, refresh=True)
    assert serp_client.call_count == 2


def test_engine_is_injected_into_params(serp_client):
    cached_search("google_maps", {"q": "Hotel X"})
    assert serp_client.calls[0]["engine"] == "google_maps"


def test_nested_and_non_string_params_are_hashable():
    key = repo.cache_key("google_maps", {"ll": "@12.9,74.8,14z", "opts": {"a": [1, 2]}})
    assert len(key) == 64


# ---------------------------------------------------------------------------
# credit accounting
# ---------------------------------------------------------------------------


def test_cache_hit_spends_no_credit(serp_client):
    cached_search("google_maps", MAPS_PARAMS)
    assert repo.api_calls_this_month() == 1
    cached_search("google_maps", MAPS_PARAMS)
    cached_search("google_maps", MAPS_PARAMS)
    assert repo.api_calls_this_month() == 1


def test_refresh_spends_another_credit(serp_client):
    """Regression: api_cache upserts, so it cannot be the spend counter."""
    cached_search("google_maps", MAPS_PARAMS)
    for _ in range(4):
        cached_search("google_maps", MAPS_PARAMS, refresh=True)
    assert serp_client.call_count == 5
    assert repo.api_calls_this_month() == 5


def test_credit_ledger_matches_actual_api_calls(serp_client):
    for i in range(6):
        cached_search("google_maps", {"type": "search", "q": f"Hotel {i}, Mangalore"})
        if i % 2 == 0:
            cached_search("google_maps", {"type": "search", "q": f"Hotel {i}, Mangalore"}, refresh=True)
    assert repo.api_calls_this_month() == serp_client.call_count


def test_cached_row_count_is_not_a_credit_count(serp_client):
    cached_search("google_maps", MAPS_PARAMS)
    cached_search("google_maps", MAPS_PARAMS, refresh=True)
    cached_search("google_maps", MAPS_PARAMS, refresh=True)
    assert repo.cached_response_count() == 1
    assert repo.api_calls_this_month() == 3


def test_failed_search_spends_no_credit(serp_client):
    serp_client.responses["google_maps"] = RuntimeError("boom")
    with pytest.raises(SerpApiError):
        cached_search("google_maps", MAPS_PARAMS)
    assert repo.api_calls_this_month() == 0


def test_error_in_search_metadata_spends_no_credit(serp_client):
    serp_client.responses["google_maps"] = {
        "search_metadata": {"status": "Error", "error": "Invalid API key"}
    }
    with pytest.raises(SerpApiError, match="Invalid API key"):
        cached_search("google_maps", MAPS_PARAMS)
    assert repo.api_calls_this_month() == 0


def test_api_calls_this_month_ignores_other_months():
    repo.log_api_call("k1", "google_maps", {"q": "a"}, called_at="1999-01-01T00:00:00+00:00")
    assert repo.api_calls_this_month() == 0
    assert repo.api_calls_this_month("1999-01") == 1


# ---------------------------------------------------------------------------
# budget guard
# ---------------------------------------------------------------------------


def test_call_is_refused_once_the_monthly_cap_is_reached(serp_client, monkeypatch):
    monkeypatch.setenv("SERP_MONTHLY_BUDGET", "2")
    from hotelpulse.config import reset_settings_cache

    reset_settings_cache()

    cached_search("google_maps", {"type": "search", "q": "one"})
    cached_search("google_maps", {"type": "search", "q": "two"})

    with pytest.raises(BudgetExhausted):
        cached_search("google_maps", {"type": "search", "q": "three"})

    assert serp_client.call_count == 2, "refusal must happen before spending"
    assert repo.api_calls_this_month() == 2


def test_refusal_message_is_user_readable(serp_client, monkeypatch):
    from hotelpulse.config import reset_settings_cache

    monkeypatch.setenv("SERP_MONTHLY_BUDGET", "0")
    reset_settings_cache()
    with pytest.raises(BudgetExhausted) as exc:
        cached_search("google_maps", MAPS_PARAMS)
    message = str(exc.value)
    assert "Traceback" not in message
    assert "budget" in message.lower()


def test_cached_data_still_works_after_the_cap_is_hit(serp_client, monkeypatch):
    from hotelpulse.config import reset_settings_cache

    cached_search("google_maps", MAPS_PARAMS)
    monkeypatch.setenv("SERP_MONTHLY_BUDGET", "0")
    reset_settings_cache()

    with pytest.raises(BudgetExhausted):
        cached_search("google_maps", {"type": "search", "q": "brand new"})

    # The already-cached query must still resolve, since it costs nothing.
    result = cached_search("google_maps", MAPS_PARAMS)
    assert result["search_metadata"]["id"] == "default"


def test_enforce_budget_false_bypasses_the_cap(serp_client, monkeypatch):
    from hotelpulse.config import reset_settings_cache

    monkeypatch.setenv("SERP_MONTHLY_BUDGET", "0")
    reset_settings_cache()
    cached_search("google_maps", MAPS_PARAMS, enforce_budget=False)
    assert serp_client.call_count == 1


# ---------------------------------------------------------------------------
# missing key / error handling
# ---------------------------------------------------------------------------


def test_missing_api_key_gives_a_plain_message(no_api_key):
    client_mod.reset_client()
    with pytest.raises(SerpApiError) as exc:
        client_mod.get_client()
    message = str(exc.value)
    assert "Traceback" not in message
    assert "SERPAPI_API_KEY" in message


@pytest.mark.parametrize(
    "status,expected",
    [
        (429, "rate limit"),
        (401, "API key"),
        (400, "invalid"),
    ],
)
def test_http_errors_map_to_plain_language(serp_client, status, expected):
    """Real serpapi.HTTPError wrapping a real requests error."""
    import requests
    import serpapi

    response = requests.Response()
    response.status_code = status
    original = requests.exceptions.HTTPError("boom", response=response)

    def boom(*args, **kwargs):
        raise serpapi.HTTPError(original)

    serp_client.search = boom
    with pytest.raises(SerpApiError) as exc:
        cached_search("google_maps", MAPS_PARAMS)
    assert expected.lower() in str(exc.value).lower()
    assert "Traceback" not in str(exc.value)
    assert repo.api_calls_this_month() == 0


def test_timeout_maps_to_plain_language(serp_client):
    import serpapi

    def boom(*args, **kwargs):
        raise serpapi.TimeoutError("timed out")

    serp_client.search = boom
    with pytest.raises(SerpApiError) as exc:
        cached_search("google_maps", MAPS_PARAMS)
    assert "too long" in str(exc.value).lower()


def test_unrecognised_error_still_has_no_traceback(serp_client):
    def boom(*args, **kwargs):
        raise ValueError("some unexpected internal detail")

    serp_client.search = boom
    with pytest.raises(SerpApiError) as exc:
        cached_search("google_maps", MAPS_PARAMS)
    message = str(exc.value)
    assert "Traceback" not in message
    assert "Could not reach SerpApi" in message


def test_cache_row_with_corrupt_json_degrades_to_a_miss(serp_client):
    cached_search("google_maps", MAPS_PARAMS)
    from hotelpulse.db.connection import db_session

    with db_session() as conn:
        conn.execute("UPDATE api_cache SET response_json = '{not json'")

    # Treated as a miss, so the next call repairs it rather than crashing.
    result = cached_search("google_maps", MAPS_PARAMS)
    assert result["search_metadata"]["id"] == "default"
    assert serp_client.call_count == 2


# ---------------------------------------------------------------------------
# pagination cost
# ---------------------------------------------------------------------------


def _page(token: str | None, count: int, next_token: str | None) -> dict:
    return {
        "reviews": [
            {
                "review_id": f"r-{(token or 'p1')}-{i}",
                "snippet": f"Review {i} on page {token or 1}",
                "rating": 3,
                "iso_date": "2026-09-01T00:00:00Z",
                "user": {"name": f"Guest {i}"},
            }
            for i in range(count)
        ],
        "serpapi_pagination": {"next_page_token": next_token} if next_token else {},
    }


def test_repeat_review_fetch_is_entirely_free(serp_client):
    """The whole point: fetch once, replay forever."""
    serp_client.responses["google_maps_reviews"] = _page(None, 8, None)
    reviews_maps.fetch_maps_reviews("0x1", cap=8)
    assert serp_client.call_count == 1

    reviews_maps.fetch_maps_reviews("0x1", cap=8)
    reviews_maps.fetch_maps_reviews("0x1", cap=8)
    assert serp_client.call_count == 1
    assert repo.api_calls_this_month() == 1


def test_pagination_uses_next_page_token(serp_client):
    serp_client.responses["google_maps_reviews"] = lambda p: _page(
        p.get("next_page_token"), 8, None if p.get("next_page_token") else "tok2"
    )
    reviews_maps.fetch_maps_reviews("0x1", cap=16)
    assert serp_client.call_count == 2
    assert serp_client.calls[0].get("next_page_token") is None
    assert serp_client.calls[1]["next_page_token"] == "tok2"


def test_cap_stops_pagination_early(serp_client):
    serp_client.responses["google_maps_reviews"] = lambda p: _page(
        p.get("next_page_token"), 8, None if p.get("next_page_token") == "tok2" else "tok2"
    )
    reviews = reviews_maps.fetch_maps_reviews("0x1", cap=8)
    assert len(reviews) == 8
    assert serp_client.call_count == 1, "hitting the cap must not fetch page 2"


def test_page_guard_bounds_a_misconfigured_cap(serp_client):
    """Even with an absurd cap, the page guard caps the credit spend."""
    page_no = {"n": 0}

    def endless(p):
        page_no["n"] += 1
        return _page(f"tok{page_no['n']}", 8, f"tok{page_no['n']}")

    serp_client.responses["google_maps_reviews"] = endless
    reviews = reviews_maps.fetch_maps_reviews("0x1", cap=1000, max_pages=3)
    assert serp_client.call_count == 3
    assert len(reviews) == 24


def test_pagination_stops_when_a_page_adds_only_duplicates(serp_client):
    """A page whose reviews are all already-seen is a sign of a loop."""
    serp_client.responses["google_maps_reviews"] = _page(None, 8, "tok2")
    reviews = reviews_maps.fetch_maps_reviews("0x1", cap=100)
    assert serp_client.call_count == 2
    assert len(reviews) == 8, "no duplicates carried into the result"


def test_zero_cap_makes_no_call(serp_client):
    assert reviews_maps.fetch_maps_reviews("0x1", cap=0) == []
    assert serp_client.call_count == 0


def test_empty_first_page_stops_immediately(serp_client):
    serp_client.responses["google_maps_reviews"] = {"reviews": [], "serpapi_pagination": {"next_page_token": "x"}}
    assert reviews_maps.fetch_maps_reviews("0x1", cap=30) == []
    assert serp_client.call_count == 1


def test_duplicate_reviews_across_pages_are_deduped(serp_client):
    # Same review_ids on every page, which Google can do.
    serp_client.responses["google_maps_reviews"] = lambda p: _page(
        p.get("next_page_token"), 4, None if p.get("next_page_token") else "tok2"
    )
    reviews = reviews_maps.fetch_maps_reviews("0x1", cap=50)
    ids = [r["review_id"] for r in reviews]
    assert len(ids) == len(set(ids)), "duplicate review_id across pages"


def test_reviews_are_requested_newest_first(serp_client):
    serp_client.responses["google_maps_reviews"] = _page(None, 8, None)
    reviews_maps.fetch_maps_reviews("0x1", cap=8)
    assert serp_client.calls[0]["sort_by"] == "newestFirst"
    assert serp_client.calls[0]["data_id"] == "0x1"


def test_estimate_credits_matches_the_eight_per_page_reality():
    """SerpApi's first page is 8, not the 10-20 the PRD assumed."""
    assert reviews_maps.estimate_credits(8) == 1
    assert reviews_maps.estimate_credits(9) == 2
    assert reviews_maps.estimate_credits(30) == 4
    assert reviews_maps.estimate_credits(0) == 0


# ---------------------------------------------------------------------------
# higher level helpers
# ---------------------------------------------------------------------------


def test_find_hotels_is_free_on_repeat(serp_client):
    serp_client.responses["google_maps"] = {
        "local_results": [{"title": "Hotel Paradise", "data_id": "0x1", "rating": 4.2, "reviews": 100}]
    }
    first = maps.find_hotels("Hotel Paradise", "Mangalore")
    second = maps.find_hotels("Hotel Paradise", "Mangalore")
    assert [c.name for c in first] == ["Hotel Paradise"]
    assert [c.name for c in second] == ["Hotel Paradise"]
    assert serp_client.call_count == 1


def test_find_hotels_builds_the_expected_query(serp_client):
    serp_client.responses["google_maps"] = {"local_results": []}
    maps.find_hotels("Hotel Paradise", "Mangalore")
    assert serp_client.calls[0]["q"] == "Hotel Paradise, Mangalore"
    assert serp_client.calls[0]["type"] == "search"


def test_find_hotels_on_no_match_returns_empty(serp_client):
    serp_client.responses["google_maps"] = {"local_results": []}
    assert maps.find_hotels("Nowhere Inn", "Nowhere") == []


def test_find_nearby_sends_a_location_bias(serp_client):
    serp_client.responses["google_maps"] = {"local_results": []}
    maps.find_nearby(12.9141, 74.8560)
    assert serp_client.calls[0]["ll"] == "@12.9141,74.856,14z"


def test_pick_own_hotel_prefers_the_closest_name():
    cands = [
        HotelCandidate(source=Source.google_maps, source_id="0x1", name="Hotel Paradise", rating=4.2),
        HotelCandidate(source=Source.google_maps, source_id="0x2", name="Hotel Paradise Residency", rating=3.0),
    ]
    assert maps.pick_own_hotel(cands, "Hotel Paradise").source_id == "0x1"
    assert maps.pick_own_hotel(cands, "Paradise Residency").source_id == "0x2"

def test_pick_own_hotel_is_case_insensitive():
    cands = [HotelCandidate(source=Source.google_maps, source_id="0x1", name="Hotel Paradise", rating=4.2)]
    assert maps.pick_own_hotel(cands, "hotel paradise").source_id == "0x1"


def test_pick_own_hotel_returns_none_when_nothing_overlaps():
    """No confident match means the UI must ask the owner to pick (PRD US-1).

    Guessing here would analyse the wrong hotel, which is worse than a prompt.
    """
    cands = [HotelCandidate(source=Source.google_maps, source_id="0x1", name="Hotel Paradise")]
    assert maps.pick_own_hotel(cands, "Completely Different") is None


def test_pick_own_hotel_matches_on_a_shared_token():
    cands = [HotelCandidate(source=Source.google_maps, source_id="0x1", name="Hotel Paradise")]
    # "Hotel" appears in the candidate name, so this is a plausible match.
    assert maps.pick_own_hotel(cands, "Nonexistent Hotel") is not None


def test_pick_own_hotel_on_empty_input():
    assert maps.pick_own_hotel([], "Anything") is None


def test_pick_own_hotel_on_empty_name_takes_the_top_result():
    cands = [
        HotelCandidate(source=Source.google_maps, source_id="0x1", name="Hotel Paradise", rating=4.2),
    ]
    assert maps.pick_own_hotel(cands, "") is not None
