"""SQLite connection handling.

Streamlit runs script reruns and button callbacks on different threads, so a
single process-wide connection (old `@lru_cache` design) raises:

    sqlite3.ProgrammingError: SQLite objects created in a thread can only be
    used in that same thread.

Fix: one connection per thread (`threading.local`), plus
`check_same_thread=False` as a safety net if a handle is ever passed across
threads. Writers still go through `db_session()`, which opens a short-lived
connection and commits/rolls back explicitly.
"""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from hotelpulse.config import get_settings

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"

_thread_local = threading.local()


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(
        str(db_path),
        # Rows behave like dicts; sqlite3.Row also supports index access.
        detect_types=0,
        timeout=30.0,
        # Streamlit may hand a handle to another thread; WAL makes this safe
        # enough for reads, and writes use their own db_session connections.
        check_same_thread=False,
    )
    conn.row_factory = sqlite3.Row
    # Off by default in SQLite, and the reviews/mentions foreign keys depend on it.
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def get_conn() -> sqlite3.Connection:
    """Return this thread's connection to the configured database.

    Prefer `db_session()` on write paths — it opens, commits, and closes.
    This exists for the read-heavy helpers in repo.py and for `init_db()`.
    """
    db_path = get_settings().db_path
    conn = getattr(_thread_local, "conn", None)
    cached_path = getattr(_thread_local, "db_path", None)
    if conn is None or cached_path != db_path:
        if conn is not None:
            try:
                conn.close()
            except sqlite3.Error:
                pass
        conn = _connect(db_path)
        _thread_local.conn = conn
        _thread_local.db_path = db_path
    return conn


def reset_conn() -> None:
    """Close this thread's cached connection (e.g. after changing DB_PATH)."""
    conn = getattr(_thread_local, "conn", None)
    if conn is not None:
        try:
            conn.close()
        except sqlite3.Error:
            pass
    _thread_local.conn = None
    _thread_local.db_path = None


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
