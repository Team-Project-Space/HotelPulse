"""Contextual sentiment tests (offline, mocked LLM outputs).

The tagger must classify *meaning*, not keywords: whatever per-topic sentiment
the model returns is preserved per topic, with verbatim-quote validation as the
only filter. These tests pin that contract with deterministic mocked model
outputs for the task §4 examples:

- "The food was not bad." -> must NOT become negative
- "The room was clean, but the staff were rude." -> split by topic
- "Excellent location, terrible service." -> split by topic
- "The room was okay, but the WiFi kept disconnecting." -> mixed/neutral + negative
- Hinglish "Bahut accha staff tha, lekin room clean nahi tha." -> split by topic

Live-model accuracy itself is NOT claimed here — that needs `eval/run_eval.py
--live`. What is verified: the pipeline never re-derives sentiment by keyword
and never flips, drops, or merges the model's per-topic readings.

Also covered: synonyms, empty text, malformed responses, provider failures.
"""

from __future__ import annotations

import json
from datetime import date

import pytest

from hotelpulse.analysis import tagger
from hotelpulse.db import repo
from hotelpulse.models import Review, Sentiment, Topic


def _review(text: str, rid: str = "r1") -> Review:
    return Review(
        review_id=rid,
        hotel_id="google_maps:0xCTX",
        source="google_maps",
        rating=4.0,
        text=text,
        review_date=date(2026, 9, 1),
        reviewer="Guest",
    )


class FakeLLM:
    def __init__(self, payloads: list[str] | None = None, *, fail_with: Exception | None = None) -> None:
        self.payloads = list(payloads or [])
        self.calls: list[dict] = []
        self.fail_with = fail_with
        self.model = "fake-model"

    def complete(self, *, system: str, user: str, max_tokens: int = 4096,
                 temperature: float = 0.0) -> str:
        self.calls.append({"system": system, "user": user})
        if self.fail_with is not None:
            raise self.fail_with
        if not self.payloads:
            raise AssertionError("FakeLLM ran out of payloads")
        return self.payloads.pop(0)


def _payload(rid: str, mentions: list[dict]) -> str:
    return json.dumps({"results": [{"review_id": rid, "mentions": mentions}]})


def _m(topic: str, sentiment: str, quote: str, severity: int = 1) -> dict:
    return {"topic": topic, "sentiment": sentiment, "severity": severity,
            "quote": quote, "quote_en": quote}


def _tag(text: str, mentions: list[dict], rid: str = "r1"):
    r = _review(text, rid)
    client = FakeLLM([_payload(rid, mentions)])
    parsed = tagger.call_llm_batch([r], client=client)
    kept, dropped = tagger.validate_mentions(r, parsed.results[0].mentions)
    return kept, dropped


# ---------------------------------------------------------------------------
# Task §4 examples (mocked model readings preserved verbatim by the pipeline)
# ---------------------------------------------------------------------------

def test_negation_not_bad_is_not_negative():
    text = "The food was not bad."
    kept, dropped = _tag(text, [_m("food", "positive", "food was not bad")])
    assert dropped == 0
    assert len(kept) == 1
    assert kept[0].topic is Topic.food
    assert kept[0].sentiment is Sentiment.positive


def test_contrast_clean_room_rude_staff_split_by_topic():
    text = "The room was clean, but the staff were rude."
    kept, dropped = _tag(text, [
        _m("cleanliness", "positive", "room was clean"),
        _m("staff", "negative", "staff were rude", severity=2),
    ])
    assert dropped == 0
    by_topic = {m.topic: m.sentiment for m in kept}
    assert by_topic == {Topic.cleanliness: Sentiment.positive,
                        Topic.staff: Sentiment.negative}


def test_location_positive_service_negative_same_review():
    text = "Excellent location, terrible service."
    kept, dropped = _tag(text, [
        _m("location", "positive", "Excellent location"),
        _m("staff", "negative", "terrible service", severity=2),
    ])
    assert dropped == 0
    by_topic = {m.topic: m.sentiment for m in kept}
    assert by_topic[Topic.location] is Sentiment.positive
    assert by_topic[Topic.staff] is Sentiment.negative


def test_mixed_room_negative_wifi_same_review():
    text = "The room was okay, but the WiFi kept disconnecting."
    kept, dropped = _tag(text, [
        _m("cleanliness", "mixed", "room was okay", severity=2),
        _m("wifi", "negative", "WiFi kept disconnecting", severity=2),
    ])
    assert dropped == 0
    by_topic = {m.topic: m.sentiment for m in kept}
    assert by_topic[Topic.cleanliness] is Sentiment.mixed
    assert by_topic[Topic.wifi] is Sentiment.negative


def test_hinglish_positive_staff_negative_cleanliness():
    text = "Bahut accha staff tha, lekin room clean nahi tha."
    kept, dropped = _tag(text, [
        _m("staff", "positive", "Bahut accha staff tha"),
        _m("cleanliness", "negative", "room clean nahi tha", severity=2),
    ])
    assert dropped == 0
    by_topic = {m.topic: m.sentiment for m in kept}
    assert by_topic[Topic.staff] is Sentiment.positive
    assert by_topic[Topic.cleanliness] is Sentiment.negative


# ---------------------------------------------------------------------------
# Synonyms / natural variation (model reading preserved, not keyword-derived)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("quote,sentiment,severity", [
    ("filthy bathroom", "negative", 3),
    ("spotless room", "positive", 1),
    ("courteous front desk", "positive", 1),
    ("sluggish internet", "negative", 2),
    ("overpriced for what you get", "negative", 2),
])
def test_synonym_readings_are_preserved(quote, sentiment, severity):
    text = f"Our stay had {quote} throughout."
    kept, dropped = _tag(text, [_m("cleanliness" if "room" in quote or "bath" in quote else "staff",
                                    sentiment, quote, severity=severity)])
    assert dropped == 0
    assert kept[0].sentiment is Sentiment(sentiment)


def test_negative_synonym_not_flipped_to_positive():
    text = "The bathroom was filthy and the sheets were stained."
    kept, _ = _tag(text, [_m("cleanliness", "negative", "bathroom was filthy", severity=3)])
    assert kept[0].sentiment is Sentiment.negative


# ---------------------------------------------------------------------------
# Empty / degenerate input
# ---------------------------------------------------------------------------

def test_empty_quote_never_matches():
    r = _review("Some real review text.")
    assert not tagger.quote_matches("", r.text)


def test_empty_review_text_matches_nothing():
    r = _review("", "rempty")
    assert not tagger.quote_matches("anything at all", r.text)


def test_tag_reviews_empty_text_review_yields_no_mentions():
    from hotelpulse.models import Hotel

    hotel = Hotel(hotel_id="google_maps:0xCTX", source="google_maps",
                  source_id="0xCTX", name="Ctx Hotel", is_own=True)
    repo.upsert_hotel(hotel)
    r = _review("", "rempty").model_copy(update={"hotel_id": hotel.hotel_id})
    repo.upsert_reviews([r])
    client = FakeLLM([json.dumps({"results": [{"review_id": "rempty",
                                               "mentions": []}]})])
    mentions = tagger.tag_reviews([r], client=client)
    assert mentions == []


# ---------------------------------------------------------------------------
# Malformed responses + provider failures
# ---------------------------------------------------------------------------

def test_malformed_json_raises_tagger_error():
    with pytest.raises(tagger.TaggerError):
        tagger.parse_llm_json("{not valid json")


def test_tag_reviews_skips_batch_on_malformed_response():
    from hotelpulse.models import Hotel

    hotel = Hotel(hotel_id="google_maps:0xCTX", source="google_maps",
                  source_id="0xCTX", name="Ctx Hotel", is_own=True)
    repo.upsert_hotel(hotel)
    r = _review("The wifi was slow.", "rslow").model_copy(
        update={"hotel_id": hotel.hotel_id})
    repo.upsert_reviews([r])
    client = FakeLLM(["garbage {{{", "still garbage {{{"])
    mentions = tagger.tag_reviews([r], client=client)
    # Batch failed; nothing fabricated, review left untagged for a later retry.
    assert mentions == []
    assert "rslow" not in repo.tagged_review_ids(tagger.PROMPT_VERSION)


def test_provider_failure_yields_no_mentions_and_warning_path():
    from hotelpulse.models import Hotel

    hotel = Hotel(hotel_id="google_maps:0xCTX", source="google_maps",
                  source_id="0xCTX", name="Ctx Hotel", is_own=True)
    repo.upsert_hotel(hotel)
    r = _review("Great location.", "rloc").model_copy(
        update={"hotel_id": hotel.hotel_id})
    repo.upsert_reviews([r])
    client = FakeLLM(fail_with=RuntimeError("connection reset"))
    mentions = tagger.tag_reviews([r], client=client)
    assert mentions == []


def test_missing_llm_keys_raise_tagger_error(monkeypatch):
    from hotelpulse.config import reset_settings_cache

    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("GROQ_API_KEY", "")
    monkeypatch.setenv("LLM_PROVIDER", "")
    reset_settings_cache()
    r = _review("Nice stay.")
    with pytest.raises(tagger.TaggerError):
        tagger.call_llm_batch([r], client=None)


def test_unknown_topic_and_sentiment_from_model_are_dropped():
    text = "The pool was amazing and the vibe was meh."
    r = _review(text)
    raw = [
        tagger.LLMMention(topic="pool", sentiment="positive", severity=1,
                          quote="pool was amazing"),
        tagger.LLMMention(topic="value", sentiment="excellent", severity=1,
                          quote="vibe was meh"),
    ]
    kept, dropped = tagger.validate_mentions(r, raw)
    assert kept == []
    assert dropped == 2
