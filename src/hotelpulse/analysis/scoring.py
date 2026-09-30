"""PRD section 11 scoring: recency-weighted topic scores and overall stats."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from hotelpulse.analysis.config import MIN_MENTIONS, RECENCY_HALF_LIFE_DAYS
from hotelpulse.models import (
    OverallStats,
    Review,
    Sentiment,
    Topic,
    TopicMention,
    TopicScore,
)


def recency_weight(review_date: date | None, *, as_of: date | None = None) -> float:
    """w = 0.5 ** (age_days / half_life); undated reviews get w = 0.5."""
    if review_date is None:
        return 0.5
    today = as_of or date.today()
    age_days = max(0, (today - review_date).days)
    return 0.5 ** (age_days / RECENCY_HALF_LIFE_DAYS)


@dataclass(frozen=True)
class MentionEvent:
    """One mention joined to its review date (for recency weighting)."""

    mention: TopicMention
    review_date: date | None
    review_id: str


def load_mention_events(hotel_id: str) -> list[MentionEvent]:
    """Mentions for a hotel, each carrying the parent review's date."""
    from hotelpulse.db import repo
    from hotelpulse.db.connection import get_conn
    from hotelpulse.models import Sentiment as Sent, Topic as Top

    rows = get_conn().execute(
        """
        SELECT m.review_id, m.topic, m.sentiment, m.severity, m.quote, m.quote_en,
               r.review_date
        FROM mentions m
        JOIN reviews r ON r.review_id = m.review_id
        WHERE r.hotel_id = ?
        ORDER BY m.severity DESC, r.review_date DESC
        """,
        (hotel_id,),
    ).fetchall()

    out: list[MentionEvent] = []
    for row in rows:
        try:
            mention = TopicMention(
                review_id=row["review_id"],
                topic=Top(row["topic"]),
                sentiment=Sent(row["sentiment"]),
                severity=int(row["severity"]),
                quote=row["quote"],
                quote_en=row["quote_en"],
            )
        except (ValueError, TypeError):
            continue
        raw_date = row["review_date"]
        review_date: date | None = None
        if raw_date:
            try:
                review_date = date.fromisoformat(str(raw_date)[:10])
            except ValueError:
                review_date = None
        out.append(
            MentionEvent(
                mention=mention,
                review_date=review_date,
                review_id=mention.review_id,
            )
        )
    return out


def score_topic(
    topic: Topic,
    events: list[MentionEvent],
    *,
    as_of: date | None = None,
) -> TopicScore:
    """PRD §11 topic score.

    topic_score = 1 + 4 * (pos + 0.5 * mix) / weighted_total
    Fewer than MIN_MENTIONS mentions -> score is None ("not enough data").
    """
    topic_events = [e for e in events if e.mention.topic == topic]
    n = len(topic_events)
    pos = neg = mix = 0
    weighted_total = 0.0
    pos_w = mix_w = 0.0

    for e in topic_events:
        w = recency_weight(e.review_date, as_of=as_of)
        weighted_total += w
        if e.mention.sentiment is Sentiment.positive:
            pos += 1
            pos_w += w
        elif e.mention.sentiment is Sentiment.mixed:
            mix += 1
            mix_w += w
        else:
            neg += 1

    score: float | None
    if n < MIN_MENTIONS or weighted_total <= 0:
        score = None
    else:
        score = 1.0 + 4.0 * (pos_w + 0.5 * mix_w) / weighted_total
        score = max(1.0, min(5.0, score))

    return TopicScore(
        topic=topic,
        score=score,
        mention_count=n,
        negative_count=neg,
        positive_count=pos,
        mixed_count=mix,
    )


def score_all_topics(
    events: list[MentionEvent],
    *,
    as_of: date | None = None,
) -> list[TopicScore]:
    return [score_topic(t, events, as_of=as_of) for t in Topic]


def overall_stats(
    reviews: list[Review],
    events: list[MentionEvent],
    *,
    average_rating: float | None = None,
) -> OverallStats:
    """Average star rating + sentiment split of all mentions (PRD §11)."""
    n = len(events)
    if n == 0:
        return OverallStats(
            average_rating=average_rating,
            reviews_analyzed=len(reviews),
        )

    pos = sum(1 for e in events if e.mention.sentiment is Sentiment.positive)
    neg = sum(1 for e in events if e.mention.sentiment is Sentiment.negative)
    mix = sum(1 for e in events if e.mention.sentiment is Sentiment.mixed)

    rating = average_rating
    if rating is None:
        rated = [r.rating for r in reviews if r.rating is not None]
        rating = sum(rated) / len(rated) if rated else None

    return OverallStats(
        average_rating=rating,
        reviews_analyzed=len(reviews),
        positive_pct=100.0 * pos / n,
        negative_pct=100.0 * neg / n,
        mixed_pct=100.0 * mix / n,
    )


def priority_weight(topic: Topic, events: list[MentionEvent], *, as_of: date | None = None) -> float:
    """Fix-first priority = sum(severity * w) over negative and mixed mentions."""
    total = 0.0
    for e in events:
        if e.mention.topic is not topic:
            continue
        if e.mention.sentiment not in (Sentiment.negative, Sentiment.mixed):
            continue
        total += e.mention.severity * recency_weight(e.review_date, as_of=as_of)
    return total
