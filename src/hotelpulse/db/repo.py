"""Repository helpers over the SQLite schema (PRD section 10).

Writes use `ON CONFLICT ... DO UPDATE` so re-fetching the same hotel or review
is idempotent -- important because a cached SerpApi response can be replayed
many times across Streamlit reruns.

Reads return plain dicts or Pydantic models rather than `sqlite3.Row`, so the
rest of the app never touches the database layer directly.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Sequence
from datetime import date, datetime, timezone
from typing import Any

from hotelpulse.db.connection import db_session, get_conn
from hotelpulse.models import (
    Hotel,
    Review,
    Sentiment,
    Topic,
    TopicMention,
    make_review_id,
)

# ---------------------------------------------------------------------------
# api_cache
# ---------------------------------------------------------------------------


def cache_key(engine: str, params: dict[str, Any]) -> str:
    """sha256(engine + sorted params json) per PRD section 6.1.

    Sorted keys so `{"q": "a", "type": "search"}` and `{"type": "search",
    "q": "a"}` produce the same key, and two params sets differing only in key
    order share one cache entry (and therefore one credit).
    """
    import hashlib

    payload = engine + json.dumps(params, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def cache_get(key: str) -> dict[str, Any] | None:
    """Return the cached response payload, or None on a miss."""
    row = get_conn().execute(
        "SELECT response_json, fetched_at FROM api_cache WHERE cache_key = ?", (key,)
    ).fetchone()
    if row is None:
        return None
    try:
        payload = json.loads(row["response_json"])
    except json.JSONDecodeError:
        # Corrupt row: treat as a miss so the next call repairs it.
        return None
    if isinstance(payload, dict):
        payload["_cached_at"] = row["fetched_at"]
    return payload


def cache_put(
    key: str,
    engine: str,
    params: dict[str, Any],
    response: dict[str, Any],
    fetched_at: str | None = None,
) -> None:
    stamp = fetched_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    with db_session() as conn:
        conn.execute(
            """
            INSERT INTO api_cache (cache_key, engine, params_json, response_json, fetched_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(cache_key) DO UPDATE SET
                engine        = excluded.engine,
                params_json   = excluded.params_json,
                response_json = excluded.response_json,
                fetched_at    = excluded.fetched_at
            """,
            (
                key,
                engine,
                json.dumps(params, sort_keys=True, default=str),
                json.dumps(response, default=str),
                stamp,
            ),
        )


def api_calls_this_month(month: str | None = None) -> int:
    """Count SerpApi calls made this month, i.e. the credit spend.

    One row in `api_cache` equals one credit spent, because a response is only
    written after a real API call. Cached replays never insert a row, so this
    counts spend rather than usage. `month` defaults to the current UTC month
    in `YYYY-MM` form.
    """
    stamp = month or datetime.now(timezone.utc).strftime("%Y-%m")
    row = get_conn().execute(
        "SELECT COUNT(*) AS n FROM api_cache WHERE fetched_at LIKE ?",
        (f"{stamp}%",),
    ).fetchone()
    return int(row["n"]) if row else 0


def cache_stats() -> tuple[int, int]:
    """(total cached responses, engines represented)."""
    row = get_conn().execute(
        "SELECT COUNT(*) AS n, COUNT(DISTINCT engine) AS e FROM api_cache"
    ).fetchone()
    return (int(row["n"]), int(row["e"])) if row else (0, 0)


# ---------------------------------------------------------------------------
# hotels
# ---------------------------------------------------------------------------

_HOTEL_COLUMNS = (
    "hotel_id",
    "source",
    "source_id",
    "name",
    "address",
    "lat",
    "lng",
    "rating",
    "review_count",
    "is_own",
)


def _row_to_hotel(row: sqlite3.Row) -> Hotel:
    data = {k: row[k] for k in _HOTEL_COLUMNS}
    data["is_own"] = bool(data["is_own"])
    return Hotel(**data)


def upsert_hotel(hotel: Hotel) -> None:
    with db_session() as conn:
        conn.execute(
            """
            INSERT INTO hotels
                (hotel_id, source, source_id, name, address, lat, lng, rating, review_count, is_own)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(hotel_id) DO UPDATE SET
                source       = excluded.source,
                source_id    = excluded.source_id,
                name         = excluded.name,
                address      = excluded.address,
                lat          = excluded.lat,
                lng          = excluded.lng,
                rating       = excluded.rating,
                review_count = excluded.review_count,
                is_own       = excluded.is_own
            """,
            (
                hotel.hotel_id,
                hotel.source,
                hotel.source_id,
                hotel.name,
                hotel.address,
                hotel.lat,
                hotel.lng,
                hotel.rating,
                hotel.review_count,
                int(hotel.is_own),
            ),
        )


def get_hotel(hotel_id: str) -> Hotel | None:
    row = get_conn().execute("SELECT * FROM hotels WHERE hotel_id = ?", (hotel_id,)).fetchone()
    return _row_to_hotel(row) if row else None


def get_own_hotel() -> Hotel | None:
    row = get_conn().execute("SELECT * FROM hotels WHERE is_own = 1 LIMIT 1").fetchone()
    return _row_to_hotel(row) if row else None


def list_hotels(own_only: bool = False) -> list[Hotel]:
    sql = "SELECT * FROM hotels"
    if own_only:
        sql += " WHERE is_own = 1"
    sql += " ORDER BY name"
    return [_row_to_hotel(r) for r in get_conn().execute(sql).fetchall()]


# ---------------------------------------------------------------------------
# reviews
# ---------------------------------------------------------------------------


def upsert_reviews(reviews: Iterable[Review]) -> int:
    """Insert reviews, replacing any existing row with the same review_id.

    Returns the number of rows written. `upsert` rather than `insert or ignore`
    so a corrected extraction overwrites the stale text.
    """
    rows = [
        (
            r.review_id,
            r.hotel_id,
            r.source,
            r.rating,
            r.text,
            r.review_date.isoformat() if r.review_date else None,
            r.reviewer,
            r.language,
        )
        for r in reviews
    ]
    if not rows:
        return 0
    with db_session() as conn:
        # The hotels row must exist or the foreign key rejects the write.
        conn.executemany(
            """
            INSERT INTO reviews
                (review_id, hotel_id, source, rating, text, review_date, reviewer, language)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(review_id) DO UPDATE SET
                hotel_id    = excluded.hotel_id,
                source      = excluded.source,
                rating      = excluded.rating,
                text        = excluded.text,
                review_date = excluded.review_date,
                reviewer    = excluded.reviewer,
                language    = excluded.language
            """,
            rows,
        )
    return len(rows)


def _row_to_review(row: sqlite3.Row) -> Review:
    raw_date = row["review_date"]
    parsed: date | None = None
    if raw_date:
        try:
            parsed = date.fromisoformat(str(raw_date)[:10])
        except ValueError:
            parsed = None
    return Review(
        review_id=row["review_id"],
        hotel_id=row["hotel_id"],
        source=row["source"],
        rating=row["rating"],
        text=row["text"],
        review_date=parsed,
        reviewer=row["reviewer"],
        language=row["language"],
    )


def get_reviews_for_hotel(hotel_id: str, limit: int | None = None) -> list[Review]:
    """Reviews for a hotel, newest first; undated reviews last."""
    sql = """
        SELECT * FROM reviews
        WHERE hotel_id = ?
        ORDER BY (review_date IS NULL), review_date DESC, review_id
    """
    params: list[Any] = [hotel_id]
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)
    return [_row_to_review(r) for r in get_conn().execute(sql, params).fetchall()]


def count_reviews(hotel_id: str) -> int:
    row = get_conn().execute(
        "SELECT COUNT(*) AS n FROM reviews WHERE hotel_id = ?", (hotel_id,)
    ).fetchone()
    return int(row["n"]) if row else 0


def get_review(review_id: str) -> Review | None:
    row = get_conn().execute("SELECT * FROM reviews WHERE review_id = ?", (review_id,)).fetchone()
    return _row_to_review(row) if row else None


# ---------------------------------------------------------------------------
# mentions + tagged_reviews (populated by the Phase 2 tagger)
# ---------------------------------------------------------------------------


def replace_mentions(review_id: str, mentions: Sequence[TopicMention], prompt_version: str) -> int:
    """Replace all mentions for one review and mark it tagged.

    Delete-then-insert rather than upsert because `mentions` has a surrogate
    `id` primary key, so re-running the tagger with the same output would
    otherwise duplicate rows.
    """
    with db_session() as conn:
        conn.execute("DELETE FROM mentions WHERE review_id = ?", (review_id,))
        if mentions:
            conn.executemany(
                """
                INSERT INTO mentions
                    (review_id, topic, sentiment, severity, quote, quote_en, prompt_version)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        review_id,
                        m.topic.value,
                        m.sentiment.value,
                        m.severity,
                        m.quote,
                        m.quote_en,
                        prompt_version,
                    )
                    for m in mentions
                ],
            )
        conn.execute(
            "INSERT OR IGNORE INTO tagged_reviews (review_id, prompt_version) VALUES (?, ?)",
            (review_id, prompt_version),
        )
    return len(mentions)


def get_mentions_for_hotel(
    hotel_id: str,
    topic: Topic | None = None,
    prompt_version: str | None = None,
) -> list[TopicMention]:
    """Mentions joined to their hotel's reviews."""
    sql = """
        SELECT m.review_id, m.topic, m.sentiment, m.severity, m.quote, m.quote_en
        FROM mentions m
        JOIN reviews r ON r.review_id = m.review_id
        WHERE r.hotel_id = ?
    """
    params: list[Any] = [hotel_id]
    if topic is not None:
        sql += " AND m.topic = ?"
        params.append(topic.value)
    if prompt_version is not None:
        sql += " AND m.prompt_version = ?"
        params.append(prompt_version)
    sql += " ORDER BY m.severity DESC, r.review_date DESC"

    out: list[TopicMention] = []
    for row in get_conn().execute(sql, params).fetchall():
        try:
            out.append(
                TopicMention(
                    review_id=row["review_id"],
                    topic=Topic(row["topic"]),
                    sentiment=Sentiment(row["sentiment"]),
                    severity=row["severity"],
                    quote=row["quote"],
                    quote_en=row["quote_en"],
                )
            )
        except ValueError:
            # Unknown topic/sentiment written by a future version: skip rather
            # than blow up the whole dashboard.
            continue
    return out


def tagged_review_ids(prompt_version: str) -> set[str]:
    """Reviews already sent to the LLM at this prompt version, so they are not resent."""
    rows = get_conn().execute(
        "SELECT review_id FROM tagged_reviews WHERE prompt_version = ?", (prompt_version,)
    ).fetchall()
    return {r["review_id"] for r in rows}


def untagged_reviews(reviews: Sequence[Review], prompt_version: str) -> list[Review]:
    """Subset of `reviews` that still needs tagging at this prompt version."""
    done = tagged_review_ids(prompt_version)
    return [r for r in reviews if r.review_id not in done]


# ---------------------------------------------------------------------------
# convenience
# ---------------------------------------------------------------------------


def store_reviews_with_ids(reviews: Iterable[Review]) -> list[Review]:
    """Persist reviews, assigning a `review_id` to any that lack one.

    `Review` requires an id, so callers normalizing raw SerpApi JSON build
    reviews without one and pass them through here.
    """
    prepared: list[Review] = []
    for r in reviews:
        if not r.review_id:
            r = r.model_copy(
                update={
                    "review_id": make_review_id(
                        r.source, r.hotel_id, r.reviewer, r.review_date, r.text
                    )
                }
            )
        prepared.append(r)
    upsert_reviews(prepared)
    return prepared
