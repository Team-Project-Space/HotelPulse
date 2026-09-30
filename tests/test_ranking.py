"""Offline tests for PRD §11 fix-first / strengths / competitor gap ranking."""

from __future__ import annotations

from datetime import date

from hotelpulse.analysis.ranking import (
    comparison_alert,
    competitor_gap,
    fix_first,
    strengths,
    topic_label,
)
from hotelpulse.analysis.scoring import MentionEvent, score_all_topics
from hotelpulse.models import Sentiment, Topic, TopicMention, TopicScore


def _ev(topic: Topic, sentiment: Sentiment, severity: int, rid: str, d: date | None) -> MentionEvent:
    return MentionEvent(
        mention=TopicMention(
            review_id=rid,
            topic=topic,
            sentiment=sentiment,
            severity=severity,
            quote=f"quote-{rid}-{topic.value}",
        ),
        review_date=d,
        review_id=rid,
    )


def _dataset(today: date):
    events = [
        # cleanliness: strong negative -> should be #1 fix
        _ev(Topic.cleanliness, Sentiment.negative, 3, "c1", today),
        _ev(Topic.cleanliness, Sentiment.negative, 3, "c2", today),
        _ev(Topic.cleanliness, Sentiment.negative, 2, "c3", today),
        # wifi: negative
        _ev(Topic.wifi, Sentiment.negative, 3, "w1", today),
        _ev(Topic.wifi, Sentiment.negative, 2, "w2", today),
        _ev(Topic.wifi, Sentiment.mixed, 1, "w3", today),
        # staff: excellent
        _ev(Topic.staff, Sentiment.positive, 1, "s1", today),
        _ev(Topic.staff, Sentiment.positive, 1, "s2", today),
        _ev(Topic.staff, Sentiment.positive, 1, "s3", today),
        # location: excellent
        _ev(Topic.location, Sentiment.positive, 1, "l1", today),
        _ev(Topic.location, Sentiment.positive, 1, "l2", today),
        _ev(Topic.location, Sentiment.positive, 1, "l3", today),
        # food: mediocre (score ~3) — not a strength, maybe not top fix
        _ev(Topic.food, Sentiment.positive, 1, "f1", today),
        _ev(Topic.food, Sentiment.mixed, 1, "f2", today),
        _ev(Topic.food, Sentiment.negative, 1, "f3", today),
        # noise: not enough mentions
        _ev(Topic.noise, Sentiment.negative, 1, "n1", today),
        _ev(Topic.noise, Sentiment.negative, 1, "n2", today),
    ]
    return events, score_all_topics(events, as_of=today)


def test_topic_labels():
    assert topic_label(Topic.wifi) == "Wi-Fi"
    assert topic_label(Topic.value) == "Value"
    assert topic_label(Topic.ac) == "AC"


def test_fix_first_orders_by_priority_and_excludes_good_topics():
    today = date(2026, 9, 30)
    events, scores = _dataset(today)
    issues = fix_first(scores, events, as_of=today)
    assert issues, "expected at least one fix topic"
    # First should be cleanliness (more severe negatives)
    assert issues[0].topic is Topic.cleanliness
    assert issues[0].priority > 0
    # Strength topics (score ~5) must not appear
    topics = {i.topic for i in issues}
    assert Topic.staff not in topics
    assert Topic.location not in topics
    # noise has only 2 mentions -> score None -> excluded
    assert Topic.noise not in topics
    # Quotes are attached and mention the topic
    assert issues[0].quotes
    assert issues[0].quotes[0].quote.startswith("quote-")


def test_strengths_top_scored_topics():
    today = date(2026, 9, 30)
    events, scores = _dataset(today)
    strengths_list = strengths(scores, events)
    assert len(strengths_list) == 2  # staff + location only have score 5
    topics = [s.topic for s in strengths_list]
    assert Topic.staff in topics
    assert Topic.location in topics
    assert all(s.topic_score == 5.0 for s in strengths_list)
    assert all(s.positive_pct == 100.0 for s in strengths_list)


def test_competitor_gap_negative_means_worse():
    today = date(2026, 9, 30)
    _, own_scores = _dataset(today)

    # Competitors are better on cleanliness, worse on location
    def ts(topic: Topic, score: float) -> TopicScore:
        return TopicScore(
            topic=topic,
            score=score,
            mention_count=3,
            negative_count=0 if score >= 4 else 3,
            positive_count=3 if score >= 4 else 0,
            mixed_count=0,
        )

    comp = [
        [ts(Topic.cleanliness, 4.5), ts(Topic.location, 2.0)],
        [ts(Topic.cleanliness, 4.0), ts(Topic.location, 2.5)],
    ]
    rows = competitor_gap(own_scores, comp, top_topics=[Topic.cleanliness, Topic.location, Topic.staff])
    by_topic = {r.topic: r for r in rows}

    clean = by_topic[Topic.cleanliness]
    # own cleanliness is 1.0; competitors avg 4.25 -> gap negative
    assert clean.gap is not None and clean.gap < 0
    assert clean.competitor_avg is not None
    assert abs(clean.competitor_avg - 4.25) < 1e-9

    loc = by_topic[Topic.location]
    # own 5.0; competitors avg 2.25 -> gap positive
    assert loc.gap is not None and loc.gap > 0

    # staff has no competitor data -> Unique to you
    staff = by_topic[Topic.staff]
    assert staff.flag == "Unique to you"
    assert staff.competitor_avg is None


def test_comparison_alert_mentions_worst_gaps():
    today = date(2026, 9, 30)
    _, own_scores = _dataset(today)

    def ts(topic: Topic, score: float) -> TopicScore:
        return TopicScore(
            topic=topic,
            score=score,
            mention_count=3,
            negative_count=0,
            positive_count=0,
            mixed_count=0,
        )

    comp = [[ts(Topic.cleanliness, 4.5), ts(Topic.wifi, 4.0)]]
    rows = competitor_gap(own_scores, comp, top_topics=[Topic.cleanliness, Topic.wifi])
    alert = comparison_alert(rows)
    assert alert is not None
    assert "Cleanliness" in alert
    assert "Wi-Fi" in alert
