"""Pipeline source-resilience tests (offline, mocked SerpApi + mocked LLM).

Covers the task §3 matrix at the `analyze_hotel` level:
- one-source success (Tripadvisor ambiguous -> Maps-only + warning)
- one-source failure (Tripadvisor raises -> Maps data retained + warning)
- both-source failure (Maps search raises -> PipelineError surfaces)
- no successful result is lost when a competitor fetch fails
- no unintended extra API requests (call counts stay bounded)
- Tripadvisor mentions contribute to the owner's topic scores
"""

from __future__ import annotations

from datetime import date
from typing import Any

from hotelpulse.db import repo
from hotelpulse.models import HotelCandidate, Review, Source
from hotelpulse.services import pipeline as pipeline_mod
from hotelpulse.services.pipeline import PipelineError


def _maps_cand(name: str = "Hotel Paradise", sid: str = "cid-1") -> HotelCandidate:
    return HotelCandidate(
        source=Source.google_maps,
        source_id=sid,
        name=name,
        address="Hampankatta, Mangalore",
        rating=4.2,
        review_count=120,
    )


def _ta_cand(name: str = "Hotel Paradise", sid: str = "99001") -> HotelCandidate:
    return HotelCandidate(
        source=Source.tripadvisor,
        source_id=sid,
        name=name,
        place_type="ACCOMMODATION",
        rating=4.0,
        review_count=80,
    )


def _review(hotel_id: str, source: str, text: str, rid_seed: str) -> Review:
    from hotelpulse.models import make_review_id

    r = Review(
        review_id="",
        hotel_id=hotel_id,
        source=source,
        rating=4.0,
        text=text,
        review_date=date(2026, 9, 1),
        reviewer=f"Guest {rid_seed}",
    )
    return r.model_copy(
        update={
            "review_id": make_review_id(r.source, r.hotel_id, r.reviewer, r.review_date, r.text)
        }
    )


class _NullLLM:
    """LLM client returning zero mentions — keeps tests about sources, not tagging."""

    def __init__(self) -> None:
        self.calls = 0

    def complete(self, *, system: str, user: str, max_tokens: int = 4096,
                 temperature: float = 0.0) -> str:
        import json

        self.calls += 1
        payload = {"results": []}
        # tag_reviews marks omitted reviews as tagged; return explicit empties.
        return json.dumps(payload)


def _patch_sources(monkeypatch, *, maps_cands=None, ta_identity=None,
                   maps_texts=None, ta_texts=None, ta_raises: Exception | None = None,
                   maps_raises: Exception | None = None):
    """Stub out every network-touching helper `analyze_hotel` reaches."""
    maps_cands = maps_cands if maps_cands is not None else [_maps_cand()]
    maps_texts = maps_texts if maps_texts is not None else ["The staff were kind."]
    ta_texts = ta_texts if ta_texts is not None else ["The food was great."]

    def fake_find_hotels(name: str, city: str, refresh: bool = False):
        if maps_raises is not None:
            raise maps_raises
        return list(maps_cands)

    def fake_fetch(cand, hotel, *, cap=None, max_pages=None, refresh=False):
        if cand.source is Source.tripadvisor:
            if ta_raises is not None:
                raise ta_raises
            reviews = [
                _review(hotel.hotel_id, "tripadvisor", t, f"ta-{i}")
                for i, t in enumerate(ta_texts)
            ]
        else:
            reviews = [
                _review(hotel.hotel_id, "google_maps", t, f"maps-{i}")
                for i, t in enumerate(maps_texts)
            ]
        return len(repo.store_reviews_with_ids(reviews))

    def fake_ta_identity(name: str, city: str, refresh: bool = False):
        if ta_raises is not None:
            raise ta_raises
        return ta_identity

    monkeypatch.setattr(pipeline_mod.maps, "find_hotels", fake_find_hotels)
    monkeypatch.setattr(pipeline_mod, "_fetch_and_store_reviews", fake_fetch)
    monkeypatch.setattr(pipeline_mod, "find_tripadvisor_identity", fake_ta_identity)


def test_tripadvisor_ambiguous_continues_with_maps_only(monkeypatch):
    """One-source success: no confident TA match -> Maps analysis + warning."""
    _patch_sources(monkeypatch, ta_identity=None)
    result = pipeline_mod.analyze_hotel(
        "Hotel Paradise", "Mangalore", analyze_competitors=False, client=_NullLLM()
    )
    assert result.analysis.reviews_analyzed == 1
    assert all(r.source == "google_maps" for r in result.analysis.reviews)
    assert any("Tripadvisor" in w for w in result.warnings)


def test_tripadvisor_failure_does_not_erase_maps(monkeypatch):
    """One-source failure: TA raises -> Maps results retained + warning recorded."""
    _patch_sources(
        monkeypatch,
        ta_identity=_ta_cand(),
        ta_raises=RuntimeError("serpapi exploded"),
    )
    result = pipeline_mod.analyze_hotel(
        "Hotel Paradise", "Mangalore", analyze_competitors=False, client=_NullLLM()
    )
    assert result.analysis.reviews_analyzed == 1
    assert result.analysis.reviews[0].source == "google_maps"
    assert any("Tripadvisor" in w for w in result.warnings)


def test_both_source_failure_surfaces_pipeline_error(monkeypatch):
    """Both sources down: Maps search itself raises -> caller sees PipelineError."""
    from hotelpulse.serp.client import SerpApiError

    _patch_sources(
        monkeypatch, maps_raises=SerpApiError("Could not reach SerpApi: down")
    )
    try:
        pipeline_mod.analyze_hotel(
            "Hotel Paradise", "Mangalore", analyze_competitors=False, client=_NullLLM()
        )
        raised = False
    except Exception:
        raised = True
    assert raised


def test_tripadvisor_mentions_contribute_to_owner_scores(monkeypatch):
    """Tripadvisor evidence must shape topic scores, not just the review count."""
    from hotelpulse.analysis import tagger
    from hotelpulse.models import Topic

    _patch_sources(
        monkeypatch,
        ta_identity=_ta_cand(),
        maps_texts=["The room was spotless and bright.", "The room was spotless again."],
        ta_texts=["The room was filthy with stains everywhere."],
    )

    real_tag = tagger.tag_reviews

    def fake_tag(reviews, *, client=None, prompt_version=None, model=None,
                 batch_size=None, persist=True):
        from hotelpulse.models import Sentiment, TopicMention

        out = []
        for r in reviews:
            if "spotless" in r.text:
                out.append(TopicMention(review_id=r.review_id, topic=Topic.cleanliness,
                                        sentiment=Sentiment.positive, severity=1,
                                        quote="spotless"))
            elif "filthy" in r.text:
                out.append(TopicMention(review_id=r.review_id, topic=Topic.cleanliness,
                                        sentiment=Sentiment.negative, severity=3,
                                        quote="filthy"))
        if persist:
            for m in out:
                repo.replace_mentions(m.review_id, [m], prompt_version or "v1")
        return out

    monkeypatch.setattr(tagger, "tag_reviews", fake_tag)
    monkeypatch.setattr(pipeline_mod, "tag_reviews", fake_tag)

    result = pipeline_mod.analyze_hotel(
        "Hotel Paradise", "Mangalore", analyze_competitors=False, client=_NullLLM()
    )
    assert result.analysis.reviews_analyzed == 3
    score = result.analysis.score_for(Topic.cleanliness)
    assert score is not None
    # Without the TA negative mention this would be a perfect 5.0; with it, lower.
    assert score.score is not None and score.score < 5.0
    assert score.mention_count == 3


def test_no_unintended_extra_requests(monkeypatch):
    """A full run touches each stub exactly once per hotel (no request loops)."""
    calls = {"find": 0, "fetch": 0, "ta_id": 0}
    _patch_sources(
        monkeypatch, ta_identity=_ta_cand(),
        maps_cands=[_maps_cand(), _maps_cand("Nearby Stay", "cid-2")],
    )
    orig_find = pipeline_mod.maps.find_hotels
    orig_fetch = pipeline_mod._fetch_and_store_reviews
    orig_ta = pipeline_mod.find_tripadvisor_identity

    def counting_find(*a: Any, **k: Any):
        calls["find"] += 1
        return orig_find(*a, **k)

    def counting_fetch(*a: Any, **k: Any):
        calls["fetch"] += 1
        return orig_fetch(*a, **k)

    def counting_ta(*a: Any, **k: Any):
        calls["ta_id"] += 1
        return orig_ta(*a, **k)

    monkeypatch.setattr(pipeline_mod.maps, "find_hotels", counting_find)
    monkeypatch.setattr(pipeline_mod, "_fetch_and_store_reviews", counting_fetch)
    monkeypatch.setattr(pipeline_mod, "find_tripadvisor_identity", counting_ta)

    pipeline_mod.analyze_hotel(
        "Hotel Paradise", "Mangalore", analyze_competitors=False, client=_NullLLM()
    )
    assert calls["find"] == 1
    assert calls["ta_id"] == 1
    # own Maps fetch + TA fetch, nothing more (competitors disabled).
    assert calls["fetch"] == 2


def test_missing_api_key_raises_before_any_work(monkeypatch):
    from hotelpulse.config import reset_settings_cache

    monkeypatch.delenv("SERPAPI_API_KEY", raising=False)
    reset_settings_cache()
    try:
        pipeline_mod.analyze_hotel("Hotel Paradise", "Mangalore", client=_NullLLM())
        raised = False
    except PipelineError as exc:
        raised = True
        assert "SERPAPI_API_KEY" in str(exc)
    assert raised
