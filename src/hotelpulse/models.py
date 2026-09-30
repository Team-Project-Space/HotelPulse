"""Pydantic data models.

The first block (Topic, Sentiment, Hotel, Review, TopicMention, Issue) is the
schema specified in PRD section 9 and is treated as a contract -- change it only
with a reason, and bump PROMPT_VERSION if tagging changes.

Everything below `Issue` is additive: scoring, ranking and comparison output
shapes needed by the analysis layer and the dashboard.
"""

from __future__ import annotations

import hashlib
from datetime import date
from enum import Enum

from pydantic import AliasChoices, BaseModel, Field, field_validator


class Topic(str, Enum):
    cleanliness = "cleanliness"
    staff = "staff"
    food = "food"
    wifi = "wifi"
    ac = "ac"
    noise = "noise"
    location = "location"
    value = "value"


class Sentiment(str, Enum):
    positive = "positive"
    negative = "negative"
    mixed = "mixed"


def _coerce_float(value: float | str | None) -> float | None:
    """SerpApi mixes floats and numeric strings; return None for junk."""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_int(value: int | str | None) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


class Hotel(BaseModel):
    hotel_id: str  # internal: source + ":" + source_id
    source: str  # "google_maps" | "tripadvisor"
    source_id: str  # data_id for maps
    name: str
    address: str | None = None
    lat: float | None = None
    lng: float | None = None
    rating: float | None = None
    review_count: int | None = None
    is_own: bool = False

    @field_validator("rating", "lat", "lng", mode="before")
    @classmethod
    def _num(cls, v: object) -> object:
        return _coerce_float(v)  # type: ignore[arg-type]

    @field_validator("review_count", mode="before")
    @classmethod
    def _count(cls, v: object) -> object:
        return _coerce_int(v)  # type: ignore[arg-type]


class Review(BaseModel):
    review_id: str  # sha1(source + hotel_id + reviewer + date + text[:80])
    hotel_id: str
    source: str
    rating: float | None = None
    text: str
    review_date: date | None = None
    reviewer: str | None = None
    language: str | None = None

    @field_validator("rating", mode="before")
    @classmethod
    def _num(cls, v: object) -> object:
        return _coerce_float(v)  # type: ignore[arg-type]


class TopicMention(BaseModel):
    review_id: str
    topic: Topic
    sentiment: Sentiment
    severity: int = Field(ge=1, le=3)  # 1 minor, 2 clear, 3 severe
    quote: str  # verbatim substring of review text
    quote_en: str | None = None


class Issue(BaseModel):
    topic: Topic
    priority: float
    mention_count: int
    negative_count: int
    topic_score: float
    quotes: list[TopicMention]  # top 2-5 by severity then recency


# ---------------------------------------------------------------------------
# Additive: analysis output shapes
# ---------------------------------------------------------------------------


class Source(str, Enum):
    google_maps = "google_maps"
    tripadvisor = "tripadvisor"


class HotelCandidate(BaseModel):
    """A hotel returned from a search, before the owner picks one.

    SerpApi names the review total `reviews` and nests coordinates under
    `gps_coordinates`, so both spellings are accepted here.
    """

    model_config = {"extra": "ignore", "populate_by_name": True}

    source: Source
    source_id: str
    place_id: str | None = None
    name: str
    address: str | None = None
    lat: float | None = None
    lng: float | None = None
    rating: float | None = None
    review_count: int | None = Field(
        default=None, validation_alias=AliasChoices("review_count", "reviews")
    )

    @field_validator("rating", "lat", "lng", mode="before")
    @classmethod
    def _num(cls, v: object) -> object:
        return _coerce_float(v)  # type: ignore[arg-type]

    @field_validator("review_count", mode="before")
    @classmethod
    def _count(cls, v: object) -> object:
        return _coerce_int(v)  # type: ignore[arg-type]

    @classmethod
    def from_maps_place(cls, raw: dict) -> "HotelCandidate | None":
        """Build a candidate from one `local_results[]` / `place_results[]` entry.

        Returns None when the entry has no usable identity (`data_id`) or name,
        so callers can filter junk in one comprehension.
        """
        if not isinstance(raw, dict):
            return None
        data_id = raw.get("data_id") or raw.get("data_cid")
        place_id = raw.get("place_id")
        name = (raw.get("title") or raw.get("name") or "").strip()
        if not data_id or not name:
            return None

        gps = raw.get("gps_coordinates") or {}
        if not isinstance(gps, dict):
            gps = {}

        return cls(
            source=Source.google_maps,
            source_id=str(data_id),
            place_id=str(place_id) if place_id else None,
            name=name,
            address=(raw.get("address") or None),
            lat=gps.get("latitude"),
            lng=gps.get("longitude"),
            rating=raw.get("rating"),
            review_count=raw.get("reviews"),
        )

    def to_hotel(self, *, is_own: bool = False) -> Hotel:
        return Hotel(
            hotel_id=f"{self.source.value}:{self.source_id}",
            source=self.source.value,
            source_id=self.source_id,
            name=self.name,
            address=self.address,
            lat=self.lat,
            lng=self.lng,
            rating=self.rating,
            review_count=self.review_count,
            is_own=is_own,
        )


class TopicScore(BaseModel):
    """PRD section 11 topic score for one hotel on one topic."""

    topic: Topic
    score: float | None = None  # None => "not enough data"
    mention_count: int
    negative_count: int
    positive_count: int
    mixed_count: int


class OverallStats(BaseModel):
    """PRD section 11 overall block."""

    average_rating: float | None = None
    reviews_analyzed: int = 0
    positive_pct: float | None = None
    negative_pct: float | None = None
    mixed_pct: float | None = None


class Strength(BaseModel):
    topic: Topic
    topic_score: float
    mention_count: int
    positive_pct: float
    quotes: list[TopicMention] = Field(default_factory=list)


class CompetitorRow(BaseModel):
    """PRD section 6.5 gap table row."""

    topic: Topic
    own_score: float | None
    competitor_avg: float | None
    gap: float | None  # negative means the owner is worse
    own_mention_count: int
    competitors_scoring_low: int
    competitor_count: int
    flag: str  # "Unique to you" | "Common in the area" | "No data"


class AnalysisResult(BaseModel):
    """Everything the dashboard needs for one hotel."""

    hotel: Hotel
    reviews_analyzed: int = 0
    overall: OverallStats = Field(default_factory=OverallStats)
    topic_scores: list[TopicScore] = Field(default_factory=list)
    fix_first: list[Issue] = Field(default_factory=list)
    strengths: list[Strength] = Field(default_factory=list)
    reviews: list[Review] = Field(default_factory=list)
    data_updated_at: str | None = None

    def score_for(self, topic: Topic) -> TopicScore | None:
        for row in self.topic_scores:
            if row.topic == topic:
                return row
        return None


class ComparisonResult(BaseModel):
    """Competitor comparison for one hotel (PRD section 6.5)."""

    hotel_id: str
    competitors: list[Hotel] = Field(default_factory=list)
    rows: list[CompetitorRow] = Field(default_factory=list)
    alert_text: str | None = None


class ApiBudget(BaseModel):
    """SerpApi credit accounting surfaced in the sidebar."""

    calls_this_month: int = 0
    monthly_budget: int = 250
    remaining: int = 250
    cache_hits: int = 0
    cache_misses: int = 0

    @property
    def used_pct(self) -> float:
        if self.monthly_budget <= 0:
            return 0.0
        return min(100.0, 100.0 * self.calls_this_month / self.monthly_budget)


# ---------------------------------------------------------------------------
# Identity helpers
# ---------------------------------------------------------------------------


def make_hotel_id(source: str, source_id: str) -> str:
    """Internal hotel id: source + ':' + source_id (PRD section 9)."""
    return f"{source}:{source_id}"


def make_review_id(
    source: str,
    hotel_id: str,
    reviewer: str | None,
    review_date: date | None,
    text: str,
) -> str:
    """sha1(source + hotel_id + reviewer + date + text[:80]) per PRD section 9.

    Deterministic so re-fetching the same review produces the same primary key
    and the reviews table dedupes itself.
    """
    parts = [
        source,
        hotel_id,
        reviewer or "",
        review_date.isoformat() if review_date else "",
        text[:80],
    ]
    digest = hashlib.sha1("".join(parts).encode("utf-8", errors="replace")).hexdigest()
    return digest
