"""Tagger unit tests with a mocked free LLM client (PRD section 17).

The must-pass test: a non-verbatim quote is dropped, never stored.
"""

from __future__ import annotations

import json
from datetime import date
from types import SimpleNamespace

import pytest

from hotelpulse.analysis import tagger
from hotelpulse.analysis.config import PROMPT_VERSION
from hotelpulse.analysis.llm_client import LLMClientError, resolve_provider
from hotelpulse.analysis.prompts import SYSTEM_PROMPT
from hotelpulse.db import repo
from hotelpulse.models import Review, Sentiment, Topic


def _review(text: str, rid: str = "r1") -> Review:
    return Review(
        review_id=rid,
        hotel_id="google_maps:0xTEST",
        source="google_maps",
        rating=4.0,
        text=text,
        review_date=date(2026, 9, 1),
        reviewer="Guest",
    )


class FakeLLM:
    """Minimal stand-in for hotelpulse.analysis.llm_client.LLMClient."""

    def __init__(self, payloads: list[str] | None = None, provider: str = "gemini") -> None:
        self.payloads = list(payloads or [])
        self.calls: list[dict] = []
        self.provider = provider
        self.model = "fake-model"

    def complete(self, *, system: str, user: str, max_tokens: int = 4096, temperature: float = 0.0) -> str:
        self.calls.append(
            {"system": system, "user": user, "max_tokens": max_tokens, "temperature": temperature}
        )
        if not self.payloads:
            raise AssertionError("FakeLLM ran out of payloads")
        return self.payloads.pop(0)


# ---------------------------------------------------------------------------
# quote validation
# ---------------------------------------------------------------------------


def test_quote_exact_substring_matches():
    r = _review("The AC was broken all night. Room 204.")
    assert tagger.quote_matches("AC was broken all night", r.text)


def test_quote_whitespace_normalized_match():
    r = _review("The staff\nwere rude\nand slow.")
    assert tagger.quote_matches("staff were rude and slow", r.text)


def test_quote_not_in_review_is_false():
    r = _review("The breakfast was excellent.")
    assert not tagger.quote_matches("wifi was terrible", r.text)


def test_quote_over_max_length_is_false():
    r = _review("x" * 500)
    assert not tagger.quote_matches("x" * 201, r.text)


# ---------------------------------------------------------------------------
# validate_mentions — THE critical rule
# ---------------------------------------------------------------------------


def test_non_verbatim_quote_is_dropped():
    """Must-pass: hallucinated quote never becomes a TopicMention."""
    r = _review("Clean room, friendly staff.")
    raw = [
        tagger.LLMMention(
            topic="cleanliness",
            sentiment="positive",
            severity=1,
            quote="The bathroom was filthy and moldy",  # NOT in the review
            quote_en="The bathroom was filthy and moldy",
        )
    ]
    kept, dropped = tagger.validate_mentions(r, raw)
    assert kept == []
    assert dropped == 1


def test_verbatim_quote_is_kept():
    r = _review("Clean room, friendly staff.")
    raw = [
        tagger.LLMMention(
            topic="cleanliness",
            sentiment="positive",
            severity=1,
            quote="Clean room",
            quote_en="Clean room",
        )
    ]
    kept, dropped = tagger.validate_mentions(r, raw)
    assert dropped == 0
    assert len(kept) == 1
    assert kept[0].topic is Topic.cleanliness
    assert kept[0].sentiment is Sentiment.positive
    assert kept[0].quote == "Clean room"


def test_unknown_topic_is_dropped():
    r = _review("Nice pool and spa.")
    raw = [
        tagger.LLMMention(topic="pool", sentiment="positive", severity=1, quote="Nice pool")
    ]
    kept, dropped = tagger.validate_mentions(r, raw)
    assert kept == []
    assert dropped == 1


def test_duplicate_topic_keeps_first_only():
    r = _review("Staff were rude. The staff never smiled.")
    raw = [
        tagger.LLMMention(topic="staff", sentiment="negative", severity=2, quote="Staff were rude"),
        tagger.LLMMention(topic="staff", sentiment="negative", severity=1, quote="staff never smiled"),
    ]
    kept, dropped = tagger.validate_mentions(r, raw)
    assert len(kept) == 1
    assert dropped == 1
    assert kept[0].quote == "Staff were rude"


def test_severity_out_of_range_rejected_by_pydantic():
    with pytest.raises(Exception):
        tagger.LLMMention(topic="food", sentiment="positive", severity=5, quote="ok")


# ---------------------------------------------------------------------------
# JSON parsing
# ---------------------------------------------------------------------------


def test_parse_llm_json_accepts_valid_payload():
    payload = {
        "results": [
            {
                "review_id": "r1",
                "mentions": [
                    {
                        "topic": "wifi",
                        "sentiment": "negative",
                        "severity": 2,
                        "quote": "wifi was slow",
                        "quote_en": "wifi was slow",
                    }
                ],
            }
        ]
    }
    parsed = tagger.parse_llm_json(json.dumps(payload))
    assert parsed.results[0].mentions[0].topic == "wifi"


def test_parse_llm_json_strips_markdown_fences():
    payload = {
        "results": [
            {
                "review_id": "r1",
                "mentions": [
                    {
                        "topic": "noise",
                        "sentiment": "negative",
                        "severity": 2,
                        "quote": "too noisy",
                        "quote_en": "too noisy",
                    }
                ],
            }
        ]
    }
    text = "```json\n" + json.dumps(payload) + "\n```"
    parsed = tagger.parse_llm_json(text)
    assert parsed.results[0].review_id == "r1"


def test_parse_llm_json_rejects_garbage():
    with pytest.raises(tagger.TaggerError):
        tagger.parse_llm_json("not json at all")


def test_parse_llm_json_rejects_wrong_shape():
    with pytest.raises(tagger.TaggerError):
        tagger.parse_llm_json(json.dumps({"results": [{"mentions": "not-a-list"}]}))
    with pytest.raises(tagger.TaggerError):
        tagger.parse_llm_json(json.dumps({"results": "nope"}))


# ---------------------------------------------------------------------------
# call_llm_batch with mock client
# ---------------------------------------------------------------------------


def test_call_llm_batch_parses_response():
    review = _review("The AC was broken. Staff ignored us.")
    payload = {
        "results": [
            {
                "review_id": review.review_id,
                "mentions": [
                    {
                        "topic": "ac",
                        "sentiment": "negative",
                        "severity": 3,
                        "quote": "AC was broken",
                        "quote_en": "AC was broken",
                    },
                    {
                        "topic": "staff",
                        "sentiment": "negative",
                        "severity": 2,
                        "quote": "Staff ignored us",
                        "quote_en": "Staff ignored us",
                    },
                ],
            }
        ]
    }
    client = FakeLLM([json.dumps(payload)])
    result = tagger.call_llm_batch([review], client=client)
    assert len(result.results) == 1
    assert len(result.results[0].mentions) == 2
    # System prompt is sent on every call.
    assert client.calls[0]["system"] == SYSTEM_PROMPT


def test_call_llm_batch_retries_once_on_bad_json():
    review = _review("Nice location near the beach.")
    good = {
        "results": [
            {
                "review_id": review.review_id,
                "mentions": [
                    {
                        "topic": "location",
                        "sentiment": "positive",
                        "severity": 1,
                        "quote": "location near the beach",
                        "quote_en": "location near the beach",
                    }
                ],
            }
        ]
    }
    client = FakeLLM(["this is not json", json.dumps(good)])
    result = tagger.call_llm_batch([review], client=client)
    assert result.results[0].mentions[0].topic == Topic.location.value
    assert len(client.calls) == 2


def test_call_llm_batch_raises_after_two_failures():
    review = _review("Bad wifi.")
    client = FakeLLM(["nope", "still nope"])
    with pytest.raises(tagger.TaggerError):
        tagger.call_llm_batch([review], client=client)


def test_call_llm_batch_empty_returns_empty():
    client = FakeLLM([])
    assert tagger.call_llm_batch([], client=client).results == []


# ---------------------------------------------------------------------------
# tag_reviews end-to-end (mocked LLM + SQLite)
# ---------------------------------------------------------------------------


def test_tag_reviews_persists_and_skips_already_tagged():
    from hotelpulse.models import Hotel

    r1 = _review("Clean room and polite staff.", rid="r1")
    r2 = _review("Broken AC, noisy street.", rid="r2")
    hotel = Hotel(
        hotel_id="google_maps:0xTEST",
        source="google_maps",
        source_id="0xTEST",
        name="Test Hotel",
        is_own=True,
    )
    repo.upsert_hotel(hotel)
    repo.upsert_reviews([r1, r2])

    payload1 = {
        "results": [
            {
                "review_id": "r1",
                "mentions": [
                    {
                        "topic": "cleanliness",
                        "sentiment": "positive",
                        "severity": 1,
                        "quote": "Clean room",
                        "quote_en": "Clean room",
                    },
                    {
                        "topic": "staff",
                        "sentiment": "positive",
                        "severity": 1,
                        "quote": "polite staff",
                        "quote_en": "polite staff",
                    },
                    {
                        # hallucinated — must be dropped
                        "topic": "food",
                        "sentiment": "negative",
                        "severity": 3,
                        "quote": "terrible breakfast buffet",
                        "quote_en": "terrible breakfast buffet",
                    },
                ],
            },
            {
                "review_id": "r2",
                "mentions": [
                    {
                        "topic": "ac",
                        "sentiment": "negative",
                        "severity": 3,
                        "quote": "Broken AC",
                        "quote_en": "Broken AC",
                    },
                    {
                        "topic": "noise",
                        "sentiment": "negative",
                        "severity": 2,
                        "quote": "noisy street",
                        "quote_en": "noisy street",
                    },
                ],
            },
        ]
    }
    client = FakeLLM([json.dumps(payload1)])
    mentions = tagger.tag_reviews([r1, r2], client=client)

    # food mention dropped (non-verbatim); 4 kept
    assert len(mentions) == 4
    topics = {m.topic for m in mentions}
    assert Topic.food not in topics
    assert Topic.cleanliness in topics
    assert Topic.ac in topics

    stored = repo.get_mentions_for_hotel("google_maps:0xTEST", prompt_version=PROMPT_VERSION)
    assert len(stored) == 4

    # Second run: both reviews already tagged → no LLM calls.
    client2 = FakeLLM([])
    mentions2 = tagger.tag_reviews([r1, r2], client=client2)
    assert mentions2 == []
    assert client2.calls == []


def test_tag_reviews_marks_reviews_with_zero_mentions():
    from hotelpulse.models import Hotel

    hotel = Hotel(
        hotel_id="google_maps:0xZERO",
        source="google_maps",
        source_id="0xZERO",
        name="Zero Hotel",
        is_own=True,
    )
    repo.upsert_hotel(hotel)
    r = _review("Lovely courtyard garden.", rid="rz")
    r = r.model_copy(update={"hotel_id": hotel.hotel_id})
    repo.upsert_reviews([r])

    payload = {"results": [{"review_id": "rz", "mentions": []}]}
    client = FakeLLM([json.dumps(payload)])
    tagger.tag_reviews([r], client=client)
    assert "rz" in repo.tagged_review_ids(PROMPT_VERSION)


def _hotel():
    from hotelpulse.models import Hotel

    return Hotel(
        hotel_id="google_maps:0xTEST",
        source="google_maps",
        source_id="0xTEST",
        name="Test Hotel",
        is_own=True,
    )


# ---------------------------------------------------------------------------
# Hinglish / regional quote handling
# ---------------------------------------------------------------------------


def test_hinglish_quote_kept_in_original_language():
    r = _review("AC bilkul kaam nahi kar raha tha, raat bhar neend udd gayi.")
    raw = [
        tagger.LLMMention(
            topic="ac",
            sentiment="negative",
            severity=3,
            quote="AC bilkul kaam nahi kar raha tha",
            quote_en="The AC was not working at all",
        )
    ]
    kept, dropped = tagger.validate_mentions(r, raw)
    assert dropped == 0
    assert kept[0].quote == "AC bilkul kaam nahi kar raha tha"
    assert kept[0].quote_en == "The AC was not working at all"


# ---------------------------------------------------------------------------
# free LLM provider selection
# ---------------------------------------------------------------------------


def test_resolve_provider_prefers_gemini(monkeypatch):
    from hotelpulse.config import get_settings, reset_settings_cache

    monkeypatch.setenv("GEMINI_API_KEY", "gkey")
    monkeypatch.setenv("GROQ_API_KEY", "qkey")
    monkeypatch.setenv("LLM_PROVIDER", "")
    reset_settings_cache()
    assert resolve_provider() == "gemini"


def test_resolve_provider_falls_back_to_groq(monkeypatch):
    from hotelpulse.config import get_settings, reset_settings_cache

    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("GROQ_API_KEY", "qkey")
    monkeypatch.setenv("LLM_PROVIDER", "")
    reset_settings_cache()
    assert resolve_provider() == "groq"


def test_resolve_provider_errors_without_keys(monkeypatch):
    from hotelpulse.config import reset_settings_cache

    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("GROQ_API_KEY", "")
    monkeypatch.setenv("LLM_PROVIDER", "")
    reset_settings_cache()
    with pytest.raises(LLMClientError, match="GEMINI_API_KEY"):
        resolve_provider()


def test_resolve_provider_override_forces_groq(monkeypatch):
    from hotelpulse.config import reset_settings_cache

    monkeypatch.setenv("GEMINI_API_KEY", "gkey")
    monkeypatch.setenv("GROQ_API_KEY", "qkey")
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    reset_settings_cache()
    assert resolve_provider() == "groq"


# ---------------------------------------------------------------------------
# fixture replay helper
# ---------------------------------------------------------------------------


def test_tag_batch_offline_from_fixture(load_fixture):
    """llm_tag_response.json is used by eval/test_tagger when present."""
    from pathlib import Path

    path = Path(__file__).parent / "fixtures" / "llm_tag_response.json"
    if not path.exists():
        pytest.skip("llm_tag_response.json not captured yet")
    payload = load_fixture("llm_tag_response.json")
    r = _review(
        "The wifi in the room was very slow. Staff were helpful though.",
        rid=payload["results"][0]["review_id"] if payload.get("results") else "r1",
    )
    mentions = tagger.tag_batch_offline([r], payload, persist=False)
    for m in mentions:
        assert m.quote in r.text or tagger.quote_matches(m.quote, r.text)
