"""SerpApi client wrapper with a SQLite-backed response cache.

Every outbound search goes through `cached_search`. A response is written to
`api_cache` only after a real API call, so one row equals one credit spent.
That is what makes the 250/month budget enforceable rather than aspirational.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from hotelpulse.config import get_settings
from hotelpulse.db import repo

logger = logging.getLogger(__name__)


class SerpApiError(RuntimeError):
    """A SerpApi failure, with a message safe to show a non-technical user.

    PRD section 13 forbids stack traces in the UI, so `str(err)` is always
    plain language.
    """


class BudgetExhausted(SerpApiError):
    """Raised before spending a credit that would exceed the configured budget."""


_client: Any | None = None


def get_client() -> Any:
    """Build (and memoize) the official `serpapi.Client`.

    Raises SerpApiError with a plain message when the key is missing, rather
    than letting the SDK raise its own.
    """
    global _client
    if _client is not None:
        return _client

    key = get_settings().serpapi_api_key
    if not key:
        raise SerpApiError(
            "No SerpApi key configured. Copy .env.example to .env and set "
            "SERPAPI_API_KEY. Cached data still works without a key."
        )

    try:
        import serpapi
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise SerpApiError("The serpapi package is not installed.") from exc

    _client = serpapi.Client(api_key=key, timeout=get_settings().serp_timeout)
    return _client


def reset_client() -> None:
    """Drop the memoized client (tests, or after changing the API key)."""
    global _client
    _client = None


def _check_budget() -> None:
    """Refuse to spend a credit past the configured cap.

    Only reached on a cache miss, because a cached response costs nothing.
    """
    settings = get_settings()
    spent = repo.api_calls_this_month()
    if spent >= settings.serp_monthly_budget:
        raise BudgetExhausted(
            f"Monthly SerpApi budget reached ({spent}/{settings.serp_monthly_budget} "
            "searches used). Cached data still works; uncheck 'Refresh data' or "
            "wait for the quota to reset."
        )


def cached_search(
    engine: str,
    params: Mapping[str, Any],
    refresh: bool = False,
    *,
    enforce_budget: bool = True,
) -> dict[str, Any]:
    """Run a SerpApi search, serving from SQLite when possible.

    Args:
        engine: SerpApi engine name, e.g. `google_maps`.
        params: request params. `engine` is added automatically.
        refresh: bypass the cache and force a live call (costs a credit).
        enforce_budget: refuse to spend a credit past the monthly cap. Tests
            pass False to avoid needing a seeded database.

    Returns:
        The response dict, with `_cached_at` set when served from the cache.
    """
    full_params: dict[str, Any] = dict(params)
    full_params["engine"] = engine
    key = repo.cache_key(engine, full_params)

    if not refresh:
        cached = repo.cache_get(key)
        if cached is not None:
            logger.info("cache hit engine=%s key=%s", engine, key[:12])
            return cached

    if enforce_budget:
        _check_budget()

    client = get_client()
    logger.info("live call engine=%s key=%s params=%s", engine, key[:12], full_params)

    try:
        raw = client.search(full_params)
    except Exception as exc:
        raise SerpApiError(_friendly_error(exc)) from exc

    # `SerpResults` is a UserDict; a failed search can come back as a plain dict
    # carrying only search_metadata with an error field.
    payload = raw.as_dict() if hasattr(raw, "as_dict") else dict(raw or {})
    if not isinstance(payload, dict):
        raise SerpApiError("SerpApi returned an unexpected response shape.")

    error = (payload.get("search_metadata") or {}).get("error")
    if error:
        raise SerpApiError(f"SerpApi could not complete that search: {error}")

    # Record the spend before writing the cache so a crash between the two
    # under-reports rather than over-reports credit usage.
    repo.log_api_call(
        key,
        engine,
        full_params,
        search_id=(payload.get("search_metadata") or {}).get("id"),
    )
    repo.cache_put(key, engine, full_params, payload)
    return payload


def _friendly_error(exc: Exception) -> str:
    """Map SDK exceptions to plain language, never a traceback."""
    name = type(exc).__name__
    text = str(exc)

    if "HTTPError" in name:
        status = getattr(exc, "status_code", None)
        if status == 429:
            return (
                "SerpApi rate limit reached. The free plan allows 50 searches "
                "per hour and 250 per month. Try again later, or reuse cached data."
            )
        if status == 401:
            return "SerpApi rejected the API key. Check SERPAPI_API_KEY in your .env file."
        if status == 400:
            return f"SerpApi rejected that request as invalid: {text[:200]}"
        return f"SerpApi returned an error (HTTP {status})."

    if "Timeout" in name:
        return "SerpApi took too long to respond. Check your connection and try again."

    return f"Could not reach SerpApi: {text[:200] or name}"


def account_snapshot() -> dict[str, Any] | None:
    """Free credit accounting from the SerpApi account endpoint.

    `client.account()` does not consume quota, so this is safe to call. Returns
    None when unavailable; callers fall back to the local `api_cache` count.
    """
    try:
        raw = get_client().account()
        return raw.as_dict() if hasattr(raw, "as_dict") else dict(raw or {})
    except Exception as exc:
        logger.info("account snapshot unavailable: %s", exc)
        return None
