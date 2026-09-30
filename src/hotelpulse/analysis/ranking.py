"""PRD §11/§6.5 ranking: fix-first issues, strengths, competitor gaps."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from statistics import mean

from hotelpulse.analysis.config import MIN_MENTIONS
from hotelpulse.analysis.scoring import MentionEvent, priority_weight
from hotelpulse.models import (
    CompetitorRow,
    Issue,
    Sentiment,
    Strength,
    Topic,
    TopicScore,
)

TOPIC_LABELS: dict[Topic, str] = {
    Topic.cleanliness: "Cleanliness",
    Topic.staff: "Staff",
    Topic.food: "Food",
    Topic.wifi: "Wi-Fi",
    Topic.ac: "AC",
    Topic.noise: "Noise",
    Topic.location: "Location",
    Topic.value: "Value",
}


def topic_label(topic: Topic) -> str:
    return TOPIC_LABELS.get(topic, topic.value.title())


def _events_by_topic(events: list[MentionEvent]) -> dict[Topic, list[MentionEvent]]:
    grouped: dict[Topic, list[MentionEvent]] = defaultdict(list)
    for e in events:
        grouped[e.mention.topic].append(e)
    return grouped


def _sample_quotes(events: list[MentionEvent], limit: int = 5) -> list:
    """Top quotes: negative/mixed first by severity, then recency."""
    def sort_key(e: MentionEvent):
        sent_rank = 0 if e.mention.sentiment is Sentiment.negative else (
            1 if e.mention.sentiment is Sentiment.mixed else 2
        )
        date_rank = e.review_date.toordinal() if e.review_date else 0
        return (sent_rank, -e.mention.severity, -date_rank)

    return [e.mention for e in sorted(events, key=sort_key)[:limit]]


def fix_first(
    scores: list[TopicScore],
    events: list[MentionEvent],
    *,
    top_n: int = 3,
    as_of: date | None = None,
) -> list[Issue]:
    """Top-N topics to fix.

    Only topics with a scored value < 4.0. Tie-break: higher negative count.
    """
    grouped = _events_by_topic(events)
    candidates: list[tuple[float, int, TopicScore]] = []
    for ts in scores:
        if ts.score is None or ts.score >= 4.0:
            continue
        pr = priority_weight(ts.topic, events, as_of=as_of)
        candidates.append((pr, ts.negative_count, ts))

    candidates.sort(key=lambda t: (t[0], t[1]), reverse=True)
    out: list[Issue] = []
    for pr, _neg, ts in candidates[:top_n]:
        out.append(
            Issue(
                topic=ts.topic,
                priority=pr,
                mention_count=ts.mention_count,
                negative_count=ts.negative_count,
                topic_score=ts.score if ts.score is not None else 0.0,
                quotes=_sample_quotes(grouped.get(ts.topic, [])),
            )
        )
    return out


def strengths(
    scores: list[TopicScore],
    events: list[MentionEvent],
    *,
    top_n: int = 3,
    min_score: float = 4.0,
) -> list[Strength]:
    """Top-N topics by topic_score with mention_count >= MIN_MENTIONS.

    `min_score` keeps "what guests like" on genuinely positive topics (PRD §11
    strengths + §6.4 dashboard copy); low-score topics belong in fix-first.
    """
    grouped = _events_by_topic(events)
    eligible = [
        ts
        for ts in scores
        if ts.score is not None
        and ts.score >= min_score
        and ts.mention_count >= MIN_MENTIONS
    ]
    eligible.sort(key=lambda ts: (ts.score or 0.0, ts.mention_count), reverse=True)

    out: list[Strength] = []
    for ts in eligible[:top_n]:
        pos_share = (
            100.0 * (ts.positive_count + 0.5 * ts.mixed_count) / ts.mention_count
            if ts.mention_count
            else 0.0
        )
        out.append(
            Strength(
                topic=ts.topic,
                topic_score=ts.score or 0.0,
                mention_count=ts.mention_count,
                positive_pct=pos_share,
                quotes=_sample_quotes(grouped.get(ts.topic, []), limit=2),
            )
        )
    return out


def competitor_gap(
    own_scores: list[TopicScore],
    competitor_scores: list[list[TopicScore]],
    *,
    top_topics: list[Topic] | None = None,
) -> list[CompetitorRow]:
    """gap = own_topic_score - mean(competitor_topic_scores). Negative = you are worse."""
    own_map = {ts.topic: ts for ts in own_scores}
    by_topic: dict[Topic, list[float]] = defaultdict(list)
    for scores in competitor_scores:
        for ts in scores:
            if ts.score is not None:
                by_topic[ts.topic].append(ts.score)

    if top_topics is None:
        # Prefer topics the owner actually has, plus any with competitor data.
        topics = list(dict.fromkeys([t for t in own_map] + list(by_topic.keys())))
    else:
        topics = top_topics

    rows: list[CompetitorRow] = []
    for topic in topics:
        own = own_map.get(topic)
        own_score = own.score if own else None
        comp_scores = by_topic.get(topic, [])
        comp_avg = mean(comp_scores) if comp_scores else None
        own_n = own.mention_count if own else 0

        if own_score is None and comp_avg is None:
            gap = None
            flag = "No data"
        elif own_score is None:
            gap = None
            flag = "No data"
        elif comp_avg is None:
            gap = None
            flag = "Unique to you"
        else:
            gap = own_score - comp_avg
            # Competitors scoring strictly below own on this topic.
            lower = sum(1 for s in comp_scores if s < own_score)
            flag = "Common in the area" if lower >= max(1, len(comp_scores) // 2) else "Unique to you"

        rows.append(
            CompetitorRow(
                topic=topic,
                own_score=own_score,
                competitor_avg=comp_avg,
                gap=gap,
                own_mention_count=own_n,
                competitors_scoring_low=sum(1 for s in comp_scores if own_score is not None and s < own_score),
                competitor_count=len(comp_scores),
                flag=flag,
            )
        )
    return rows


def comparison_alert(rows: list[CompetitorRow]) -> str | None:
    """Human-readable alert for the dashboard banner."""
    gaps = [r for r in rows if r.gap is not None and r.gap < 0]
    if not gaps:
        positives = [r for r in rows if r.gap is not None and r.gap > 0]
        if positives:
            names = ", ".join(topic_label(r.topic) for r in positives[:2])
            return f"You are ahead on {names} compared with nearby hotels."
        return "Not enough comparison data yet."
    gaps.sort(key=lambda r: r.gap or 0.0)
    names = ", ".join(topic_label(r.topic) for r in gaps[:2])
    return f"{names} are your biggest gaps compared with nearby hotels."
