"""SQLite connection handling.

The database is a local cache and analysis store, so the connection is opened
per operation rather than held globally. That keeps Streamlit's script reruns
safe: each rerun gets a clean connection and cannot trip over a stale handle.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

from hotelpulse.config import get_settings

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(
        str(db_path),
        # Rows behave like dicts; sqlite3.Row also supports index access.
        detect_types=0,
        timeout=30.0,
    )
    conn.row_factory = sqlite3.Row
    # Off by default in SQLite, and the reviews/mentions foreign keys depend on it.
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


@lru_cache(maxsize=1)
def get_conn() -> sqlite3.Connection:
    """Return a shared connection to the configured database.

    For library code prefer `db_session()`, which is re-entrant and closes
    cleanly. This exists for the read-heavy helpers in repo.py and for
    `init_db()`.
    """
    return _connect(get_settings().db_path)


def reset_conn() -> None:
    """Drop the cached connection. Call after changing DB_PATH (e.g. in tests)."""
    if get_conn.cache_info().currsize:
        try:
            get_conn().close()
        except sqlite3.Error:
            pass
    get_conn.cache_clear()


@contextmanager
def db_session() -> Iterator[sqlite3.Connection]:
    """Context manager yielding a connection committed on success.

    Rolls back on exception. Use this for any write path::

        with db_session() as conn:
            conn.execute(...)
    """
    conn = _connect(get_settings().db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: Path | None = None) -> Path:
    """Create the database file and apply schema.sql. Safe to call repeatedly."""
    if db_path is not None:
        target = Path(db_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        conn = _connect(target)
    else:
        conn = get_conn()

    try:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        conn.commit()
    finally:
        if db_path is not None:
            conn.close()
    return Path(db_path) if db_path is not None else get_settings().db_path
