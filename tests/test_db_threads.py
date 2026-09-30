"""SQLite connections must be safe under Streamlit's multi-threaded reruns."""

from __future__ import annotations

import threading

from hotelpulse.db import connection as conn_mod
from hotelpulse.db.connection import get_conn, init_db, reset_conn


def test_get_conn_is_thread_local(tmp_path):
    db = tmp_path / "t.db"
    conn_mod.get_settings.cache_clear()
    import os

    old = os.environ.get("DB_PATH")
    os.environ["DB_PATH"] = str(db)
    try:
        conn_mod.get_settings.cache_clear()
        reset_conn()
        init_db()

        main_conn = get_conn()
        errors: list[BaseException] = []
        other_ids: list[int] = []

        def worker():
            try:
                c = get_conn()
                other_ids.append(id(c))
                c.execute("SELECT 1").fetchone()
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)

        t = threading.Thread(target=worker)
        t.start()
        t.join(timeout=10)

        assert not errors, f"thread saw {errors!r}"
        assert other_ids, "worker never ran"
        # Different thread => different connection object (thread-local cache).
        assert other_ids[0] != id(main_conn)
        # Main thread handle still usable after worker ran.
        main_conn.execute("SELECT 1").fetchone()
    finally:
        reset_conn()
        if old is None:
            os.environ.pop("DB_PATH", None)
        else:
            os.environ["DB_PATH"] = old
        conn_mod.get_settings.cache_clear()


def test_db_session_commits_in_worker_thread(tmp_path):
    import os

    from hotelpulse.db import repo
    from hotelpulse.models import Hotel

    db = tmp_path / "sess.db"
    old = os.environ.get("DB_PATH")
    os.environ["DB_PATH"] = str(db)
    try:
        conn_mod.get_settings.cache_clear()
        reset_conn()
        init_db()

        errors: list[BaseException] = []

        def worker():
            try:
                hotel = Hotel(
                    hotel_id="google_maps:test",
                    source="google_maps",
                    source_id="test",
                    name="Thread Hotel",
                    is_own=False,
                )
                repo.upsert_hotel(hotel)
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)

        t = threading.Thread(target=worker)
        t.start()
        t.join(timeout=10)
        assert not errors, f"worker write failed: {errors!r}"

        # Read from the main thread's connection (separate handle).
        row = get_conn().execute(
            "SELECT name FROM hotels WHERE hotel_id = ?", ("google_maps:test",)
        ).fetchone()
        assert row is not None
        assert row["name"] == "Thread Hotel"
    finally:
        reset_conn()
        if old is None:
            os.environ.pop("DB_PATH", None)
        else:
            os.environ["DB_PATH"] = old
        conn_mod.get_settings.cache_clear()
