"""Offline tests for PRD §11 scoring math."""

from __future__ import annotations

from datetime import date

from hotelpulse.analysis.config import MIN_MENTIONS, RECENCY_HALF_LIFE_DAYS
from hotelpulse.analysis.scoring import (
    MentionEvent,
    overall_stats,
    priority_weight,
    recency_weight,
    score_all_topics,
    score_topic,
)
from hotelpulse.models import Review, Sentiment, Topic, TopicMention


def _mention(topic: Topic, sentiment: Sentiment, severity: int = 2, quote: str = "q") -> TopicMention:
    return TopicMention(
        review_id="r1",
        topic=topic,
        sentiment=sentiment,
        severity=severity,
        quote=quote,
    )


def _event(mention: TopicMention, d: date | None, rid: str = "r1") -> MentionEvent:
    return MentionEvent(mention=mention, review_date=d, review_id=rid)


def test_recency_weight_half_life():
    today = date(2026, 9, 30)
    assert recency_weight(None) == 0.5
    assert recency_weight(today, as_of=today) == 1.0
    half = date(2026, 9, 30).toordinal() - int(RECENCY_HALF_LIFE_DAYS)
    w = recency_weight(date.fromordinal(half), as_of=today)
    assert abs(w - 0.5) < 1e-9
    # Future dates clamp to age 0
    assert recency_weight(date(2027, 1, 1), as_of=today) == 1.0


def test_score_topic_all_positive():
    today = date(2026, 9, 30)
    events = [
        _event(_mention(Topic.cleanliness, Sentiment.positive), today),
        _event(_mention(Topic.cleanliness, Sentiment.positive), today),
        _event(_mention(Topic.cleanliness, Sentiment.positive), today),
    ]
    ts = score_topic(Topic.cleanliness, events, as_of=today)
    assert ts.score == 5.0
    assert ts.mention_count == 3
    assert ts.positive_count == 3


def test_score_topic_all_negative():
    today = date(2026, 9, 30)
    events = [
        _event(_mention(Topic.wifi, Sentiment.negative, severity=3), today),
        _event(_mention(Topic.wifi, Sentiment.negative, severity=3), today),
        _event(_mention(Topic.wifi, Sentiment.negative, severity=3), today),
    ]
    ts = score_topic(Topic.wifi, events, as_of=today)
    assert ts.score == 1.0
    assert ts.negative_count == 3


def test_score_topic_mixed_counts_half():
    today = date(2026, 9, 30)
    events = [
        _event(_mention(Topic.food, Sentiment.positive), today),
        _event(_mention(Topic.food, Sentiment.mixed), today),
        _event(_mention(Topic.food, Sentiment.negative), today),
    ]
    ts = score_topic(Topic.food, events, as_of=today)
    # 1 + 4 * (1 + 0.5) / 3 = 3.0
    assert ts.score is not None
    assert abs(ts.score - 3.0) < 1e-9


def test_score_topic_below_min_mentions_is_none():
    today = date(2026, 9, 30)
    events = [
        _event(_mention(Topic.ac, Sentiment.positive), today),
        _event(_mention(Topic.ac, Sentiment.positive), today),
    ]
    assert MIN_MENTIONS >= 3
    ts = score_topic(Topic.ac, events, as_of=today)
    assert ts.score is None
    assert ts.mention_count == 2


def test_score_topic_undated_uses_half_weight():
    today = date(2026, 9, 30)
    events = [
        _event(_mention(Topic.staff, Sentiment.positive), None),
        _event(_mention(Topic.staff, Sentiment.negative), None),
        _event(_mention(Topic.staff, Sentiment.negative), None),
    ]
    ts = score_topic(Topic.staff, events, as_of=today)
    # Equal weights cancel in the ratio: 1 + 4 * (pos / n) = 1 + 4/3
    assert ts.score is not None
    assert abs(ts.score - (1.0 + 4.0 / 3.0)) < 1e-9


def test_priority_weight_only_neg_and_mixed():
    today = date(2026, 9, 30)
    events = [
        _event(_mention(Topic.noise, Sentiment.negative, severity=3), today),
        _event(_mention(Topic.noise, Sentiment.mixed, severity=2), today),
        _event(_mention(Topic.noise, Sentiment.positive, severity=3), today),
    ]
    # positive ignored: 3*1 + 2*1 = 5
    assert abs(priority_weight(Topic.noise, events, as_of=today) - 5.0) < 1e-9


def test_score_all_topics_and_overall():
    today = date(2026, 9, 30)
    events = [
        _event(_mention(Topic.location, Sentiment.positive), today, "r1"),
        _event(_mention(Topic.location, Sentiment.positive), today, "r1"),
        _event(_mention(Topic.location, Sentiment.positive), today, "r1"),
        _event(_mention(Topic.value, Sentiment.negative), today, "r2"),
        _event(_mention(Topic.value, Sentiment.negative), today, "r2"),
        _event(_mention(Topic.value, Sentiment.negative), today, "r2"),
    ]
    scores = score_all_topics(events, as_of=today)
    by_topic = {s.topic: s for s in scores}
    assert by_topic[Topic.location].score == 5.0
    assert by_topic[Topic.value].score == 1.0
    assert by_topic[Topic.staff].score is None

    reviews = [
        Review(review_id="r1", hotel_id="h", source="google_maps", rating=5, text="ok"),
        Review(review_id="r2", hotel_id="h", source="google_maps", rating=1, text="bad"),
    ]
    stats = overall_stats(reviews, events, average_rating=None)
    assert stats.reviews_analyzed == 2
    assert stats.average_rating == 3.0
    assert stats.positive_pct == 50.0
    assert stats.negative_pct == 50.0
