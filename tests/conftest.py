"""Shared pytest fixtures.

Two invariants this suite enforces (PRD 17, rule 3):

1. Every test gets an isolated temporary SQLite database, never the real one.
2. No test may touch the network. `forbid_network` patches `requests` and
   `httpx` to raise, and `fake_serpapi` is the only way to get a client, so a
   stray live call fails loudly instead of silently burning a credit.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def temp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Point the app at a throwaway database and reset all cached state."""
    from hotelpulse.config import get_settings, reset_settings_cache
    from hotelpulse.db.connection import init_db, reset_conn

    db_file = tmp_path / "hotelpulse_test.db"
    monkeypatch.setenv("DB_PATH", str(db_file))
    monkeypatch.setenv("SERPAPI_API_KEY", "test-key-not-real")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")
    monkeypatch.setenv("GROQ_API_KEY", "")
    monkeypatch.setenv("LLM_PROVIDER", "")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("SERP_MONTHLY_BUDGET", "250")

    reset_settings_cache()
    reset_conn()
    init_db()

    yield db_file

    reset_conn()
    reset_settings_cache()


@pytest.fixture(autouse=True)
def forbid_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make any real HTTP call raise."""

    def boom(*args: Any, **kwargs: Any) -> None:
        raise AssertionError(
            "Network access attempted during a test. Tests must run offline "
            "against fixtures (PRD section 17)."
        )

    for mod_name in ("requests", "httpx", "http.client"):
        try:
            mod = __import__(mod_name, fromlist=["*"])
        except ImportError:
            continue
        if mod_name == "requests":
            monkeypatch.setattr(mod, "get", boom)
            monkeypatch.setattr(mod, "post", boom)
            monkeypatch.setattr(mod.Session, "request", boom)
        elif mod_name == "httpx":
            monkeypatch.setattr(mod, "get", boom)
            monkeypatch.setattr(mod, "post", boom)
            monkeypatch.setattr(mod, "Client", boom)
        else:
            monkeypatch.setattr(mod, "HTTPConnection", boom)


class FakeSerpResults(dict):
    """Stand-in for serpapi.models.SerpResults (a UserDict with as_dict)."""

    def as_dict(self) -> dict[str, Any]:
        return dict(self)


class RecordingClient:
    """Fake `serpapi.Client` that records every search it is handed."""

    def __init__(self, responses: dict[str, Any] | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self.responses = responses or {}
        self._default = FakeSerpResults({"search_metadata": {"id": "default", "status": "Success"}})

    def search(self, params: dict[str, Any]) -> FakeSerpResults:
        self.calls.append(dict(params))
        engine = params.get("engine")
        handler = self.responses.get(engine)
        if callable(handler):
            return FakeSerpResults(handler(params))
        if isinstance(handler, dict):
            return FakeSerpResults(handler)
        if isinstance(handler, Exception):
            raise handler
        return self._default

    def account(self) -> FakeSerpResults:
        return FakeSerpResults({"total_searches_left": 240, "this_month_usage": 10})

    @property
    def call_count(self) -> int:
        return len(self.calls)

    def engines_used(self) -> list[str]:
        return [c.get("engine", "") for c in self.calls]


@pytest.fixture
def serp_client(monkeypatch: pytest.MonkeyPatch) -> RecordingClient:
    """Install a fake SerpApi client for the duration of one test."""
    from hotelpulse.serp import client as client_mod

    recorder = RecordingClient()
    monkeypatch.setattr(client_mod, "get_client", lambda: recorder)
    client_mod.reset_client()
    return recorder


@pytest.fixture
def load_fixture():
    """Read a JSON fixture from tests/fixtures/."""

    def _load(name: str) -> dict[str, Any]:
        import json

        path = FIXTURES_DIR / name
        if not path.exists():
            raise FileNotFoundError(
                f"Missing fixture {path}. See tests/fixtures/README.md for how to "
                "capture one from a real SerpApi response."
            )
        return json.loads(path.read_text(encoding="utf-8"))

    return _load


@pytest.fixture
def no_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulate a machine with no SERPAPI_API_KEY configured."""
    from hotelpulse.config import reset_settings_cache
    from hotelpulse.serp import client as client_mod

    monkeypatch.delenv("SERPAPI_API_KEY", raising=False)
    reset_settings_cache()
    client_mod.reset_client()
