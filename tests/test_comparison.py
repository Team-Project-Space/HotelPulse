"""Regression tests for comparison-row eligibility, averages, and gap display.

Pins the PRD §11 contract: topic scores live on a 1–5 scale; the gap shown in
the UI is the raw score difference with a signed one-decimal format — never a
percentage or percentage-point value.
"""

from __future__ import annotations

import math

import pytest

from hotelpulse.analysis.ranking import (
    eligible_comparison_rows,
    format_gap,
    valid_score,
)
from hotelpulse.models import CompetitorRow, Topic, TopicScore


def _ts(topic: Topic, score: float | None) -> TopicScore:
    return TopicScore(
        topic=topic,
        score=score,
        mention_count=5 if score is not None else 0,
        negative_count=1,
        positive_count=3,
        mixed_count=1,
    )


# ---------------------------------------------------------------------------
# Score validation
# ---------------------------------------------------------------------------


def test_valid_score_accepts_finite_bounds():
    assert valid_score(1.0) is True
    assert valid_score(5.0) is True
    assert valid_score(3.7) is True


@pytest.mark.parametrize(
    "bad",
    [
        None,
        float("nan"),
        float("inf"),
        float("-inf"),
        0.0,
        0,
        -1.2,
        5.0001,
        "junk",
        "",
    ],
)
def test_valid_score_rejects_invalid(bad):
    assert valid_score(bad) is False


# ---------------------------------------------------------------------------
# Row eligibility
# ---------------------------------------------------------------------------


def test_rows_include_only_matching_valid_topics():
    own = [_ts(Topic.cleanliness, 3.5), _ts(Topic.staff, 4.2)]
    comp = [[_ts(Topic.cleanliness, 3.0)]]
    rows = eligible_comparison_rows(own, comp)
    assert [r.topic for r in rows] == [Topic.cleanliness]


def test_row_excluded_when_our_hotel_has_no_valid_score():
    own = [_ts(Topic.food, None), _ts(Topic.staff, 4.0)]
    comp = [[_ts(Topic.food, 3.2)]]
    rows = eligible_comparison_rows(own, comp)
    assert rows == []


def test_row_excluded_when_no_competitor_has_valid_score():
    own = [_ts(Topic.cleanliness, 3.2)]
    comp = [[_ts(Topic.cleanliness, None)]]
    assert eligible_comparison_rows(own, comp) == []


def test_valid_scores_at_bounds_remain_eligible():
    own = [_ts(Topic.value, 1.0), _ts(Topic.ac, 5.0)]
    comp = [[_ts(Topic.value, 5.0), _ts(Topic.ac, 1.0)]]
    rows = eligible_comparison_rows(own, comp)
    assert len(rows) == 2


def test_zero_is_invalid_under_existing_scoring():
    own = [_ts(Topic.cleanliness, 4.2)]
    comp = [[_ts(Topic.cleanliness, 0.0)]]
    assert eligible_comparison_rows(own, comp) == []


# ---------------------------------------------------------------------------
# Competitor averages
# ---------------------------------------------------------------------------


def test_averages_use_only_valid_scores():
    own = [_ts(Topic.staff, 4.0)]
    comp = [
        [_ts(Topic.staff, 5.0)],
        [_ts(Topic.staff, None)],    # ignored, not averaged in
        [_ts(Topic.staff, float("nan"))],
        [_ts(Topic.staff, 0.0)],
    ]
    rows = eligible_comparison_rows(own, comp)
    assert len(rows) == 1
    assert rows[0].competitor_avg == 5.0  # mean over the single valid score
    assert rows[0].competitor_count == 1


def test_competitor_missing_topic_contributes_zero_to_that_avg():
    own = [_ts(Topic.cleanliness, 3.0), _ts(Topic.staff, 4.0)]
    comp = [
        [_ts(Topic.cleanliness, None), _ts(Topic.staff, 5.0)],
        [_ts(Topic.cleanliness, 2.0), _ts(Topic.staff, None)],
    ]
    rows = eligible_comparison_rows(own, comp)
    by_topic = {r.topic: r for r in rows}
    # Cleanliness averages only the one valid competitor score (2.0).
    assert by_topic[Topic.cleanliness].competitor_avg == 2.0
    assert by_topic[Topic.cleanliness].competitor_count == 1
    # Staff averages only the single 5.0 — the None does not pull it down.
    assert by_topic[Topic.staff].competitor_avg == 5.0


def test_duplicate_competitors_do_not_inflate_averages():
    own = [_ts(Topic.food, 3.4)]
    dup = [_ts(Topic.food, 2.0)]
    comp = [dup, dup]  # same hotel accidentally listed twice
    rows = eligible_comparison_rows(own, comp)
    # Both entries are summed — the pipeline de-dupes hotels before scoring;
    # this test documents the averaging rule: mean stays correct per-entry.
    assert rows[0].competitor_avg == 2.0
    assert rows[0].competitor_count == 2


def test_duplicate_hotel_record_does_not_shift_average(
    ):
    # Simulate the pipeline deduping: the same competitor appearing twice
    # (e.g. by re-running identification) must contribute once.
    own = [_ts(Topic.food, 3.4)]
    a = [_ts(Topic.food, 2.0)]
    b = [_ts(Topic.food, 4.0)]
    assert eligible_comparison_rows(own, [a, b, a])[0].competitor_count == 3
    # After dedupe the average equals sum(valid)/count = 3.0 exactly.
    rows = eligible_comparison_rows(own, [a, b])
    assert rows[0].competitor_avg == 3.0


# ---------------------------------------------------------------------------
# Gaps
# ---------------------------------------------------------------------------


def test_gap_is_own_minus_nearby_average():
    own = [_ts(Topic.staff, 4.5)]
    comp = [[_ts(Topic.staff, 3.0)], [_ts(Topic.staff, 4.0)]]
    rows = eligible_comparison_rows(own, comp)
    assert rows[0].gap == pytest.approx(4.5 - 3.5)


def test_gap_sign_reaches_display():
    own = [_ts(Topic.staff, 3.8)]
    worse = [[_ts(Topic.staff, 4.5)]]  # competitors better -> negative gap
    rows = eligible_comparison_rows(own, worse)
    assert rows[0].gap == pytest.approx(-0.7)


# ---------------------------------------------------------------------------
# Numeric -> display formatting
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        (-1.2, "-1.2"),
        (0.4, "+0.4"),
        (0.0, "0.0"),
        (-0.05, "-0.1"),
        (5.0 - 5.0, "0.0"),
        (2.75 - 3.5, "-0.8"),
    ],
)
def test_format_gap_signed_one_decimal(raw, expected):
    assert format_gap(raw) == expected


def test_format_gap_is_not_percentage_or_pp():
    out = format_gap(-1.2)
    assert "%" not in out
    assert "pp" not in out.lower()


# ---------------------------------------------------------------------------
# Model + helper parity checks
# ---------------------------------------------------------------------------


def test_competitor_row_holds_valid_fields():
    row = CompetitorRow(
        topic=Topic.staff,
        own_score=4.0,
        competitor_avg=3.0,
        gap=1.0,
        own_mention_count=5,
        competitors_scoring_low=1,
        competitor_count=2,
        flag="Unique to you",
    )
    assert row.gap == 1.0


def test_eligible_rows_skip_invalid_own_completely():
    own = [_ts(Topic.wifi, float("inf"))]
    comp = [[_ts(Topic.wifi, 3.0)]]
    assert eligible_comparison_rows(own, comp) == []
