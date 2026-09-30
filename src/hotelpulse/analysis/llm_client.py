"""Provider-agnostic LLM client for HotelPulse tagging.

Replaces the paid Anthropic SDK with free alternatives:

* **Google Gemini** (`google-genai`) — preferred when `GEMINI_API_KEY` is set.
* **Groq** (`groq`) — fallback when only `GROQ_API_KEY` is set.

Selection order (PRD free-tier requirement):
1. `LLM_PROVIDER=gemini|groq` if set in env
2. Gemini if `GEMINI_API_KEY` present
3. Groq if `GROQ_API_KEY` present
4. Otherwise raise `LLMClientError`

The tagger only needs raw completion text; JSON parsing and quote validation
stay in `analysis/tagger.py`.
"""

from __future__ import annotations

import logging
from typing import Any

from hotelpulse.config import get_settings

logger = logging.getLogger(__name__)

# Fallback model ids used when TAG_MODEL is empty or provider-specific.
# gemini-3.1-flash-lite verified working + fast on free tier (2026-09-30).
# gemini-3.8-flash is often 503 under load; 2.5-flash is blocked for new users.
DEFAULT_MODELS: dict[str, str] = {
    "gemini": "gemini-3.1-flash-lite",
    "groq": "llama-3.3-70b-versatile",
}


class LLMClientError(RuntimeError):
    """Raised when no free LLM provider is configured or a call fails."""


def resolve_provider() -> str:
    """Return 'gemini' or 'groq'. Raises LLMClientError when neither key exists."""
    settings = get_settings()
    override = settings.llm_provider_override
    if override in ("gemini", "groq"):
        if override == "gemini" and not settings.gemini_api_key:
            raise LLMClientError(
                "LLM_PROVIDER=gemini but GEMINI_API_KEY is empty in .env."
            )
        if override == "groq" and not settings.groq_api_key:
            raise LLMClientError(
                "LLM_PROVIDER=groq but GROQ_API_KEY is empty in .env."
            )
        return override

    if settings.gemini_api_key:
        return "gemini"
    if settings.groq_api_key:
        return "groq"

    raise LLMClientError(
        "No free LLM key configured. Copy .env.example to .env and set "
        "GEMINI_API_KEY (preferred, https://aistudio.google.com/apikey) "
        "or GROQ_API_KEY (https://console.groq.com/keys)."
    )


class LLMClient:
    """Thin wrapper that returns raw completion text from Gemini or Groq."""

    def __init__(self, provider: str, model: str | None = None) -> None:
        if provider not in ("gemini", "groq"):
            raise LLMClientError(f"Unknown LLM provider: {provider!r}")
        settings = get_settings()
        self.provider = provider
        raw_model = model or settings.tag_model or DEFAULT_MODELS[provider]
        # If TAG_MODEL still holds a Claude id from an old .env, remap.
        if provider == "gemini" and raw_model.startswith("claude"):
            raw_model = DEFAULT_MODELS["gemini"]
        if provider == "groq" and raw_model.startswith("claude"):
            raw_model = DEFAULT_MODELS["groq"]
        self.model = raw_model
        self._client: Any | None = None

    # -- construction -------------------------------------------------

    def _gemini_client(self) -> Any:
        if self._client is not None:
            return self._client
        key = get_settings().gemini_api_key
        if not key:
            raise LLMClientError("GEMINI_API_KEY is empty in .env.")
        try:
            from google import genai
        except ImportError as exc:  # pragma: no cover - dependency declared
            raise LLMClientError(
                "The google-genai package is not installed. "
                "Run: py -m pip install google-genai"
            ) from exc
        self._client = genai.Client(api_key=key)
        return self._client

    def _groq_client(self) -> Any:
        if self._client is not None:
            return self._client
        key = get_settings().groq_api_key
        if not key:
            raise LLMClientError("GROQ_API_KEY is empty in .env.")
        try:
            from groq import Groq
        except ImportError as exc:  # pragma: no cover
            raise LLMClientError(
                "The groq package is not installed. Run: py -m pip install groq"
            ) from exc
        self._client = Groq(api_key=key)
        return self._client

    # -- completion ---------------------------------------------------

    def complete(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> str:
        """Run one chat completion. Returns the model text (may include fences)."""
        if self.provider == "gemini":
            return self._complete_gemini(system, user, max_tokens, temperature)
        return self._complete_groq(system, user, max_tokens, temperature)

    def _complete_gemini(
        self, system: str, user: str, max_tokens: int, temperature: float
    ) -> str:
        client = self._gemini_client()
        try:
            from google.genai import types
        except ImportError as exc:  # pragma: no cover
            raise LLMClientError("google-genai types unavailable.") from exc

        # Thinking models burn tokens before the visible answer; keep a floor.
        max_tokens = max(int(max_tokens), 1024)
        config = types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=max_tokens,
            temperature=temperature,
        )
        last_exc: Exception | None = None
        for attempt in range(4):
            try:
                response = client.models.generate_content(
                    model=self.model,
                    contents=user,
                    config=config,
                )
                text = _response_text(response)
                if text:
                    return text
                last_exc = LLMClientError("Gemini returned an empty response.")
            except Exception as exc:
                last_exc = exc
                msg = str(exc)
                transient = any(
                    token in msg
                    for token in ("503", "429", "UNAVAILABLE", "RESOURCE_EXHAUSTED", "overloaded")
                )
                if attempt < 3 and transient:
                    import time

                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise LLMClientError(f"Gemini call failed: {exc}") from exc
        raise LLMClientError(f"Gemini call failed: {last_exc}") from last_exc


def _response_text(response: Any) -> str:
    """Extract visible text from a GenerateContentResponse."""
    text = getattr(response, "text", None)
    if text:
        return str(text)
    try:
        parts = response.candidates[0].content.parts
        chunks = []
        for p in parts or []:
            t = getattr(p, "text", None)
            if t:
                chunks.append(str(t))
        if chunks:
            return "".join(chunks)
    except Exception:
        pass
    return ""

    def _complete_groq(
        self, system: str, user: str, max_tokens: int, temperature: float
    ) -> str:
        client = self._groq_client()
        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                max_tokens=max_tokens,
                temperature=temperature,
            )
        except Exception as exc:
            raise LLMClientError(f"Groq call failed: {exc}") from exc

        try:
            content = response.choices[0].message.content
        except Exception as exc:
            raise LLMClientError("Groq returned an unexpected response shape.") from exc
        if not content:
            raise LLMClientError("Groq returned an empty response.")
        return str(content)


def get_llm_client(model: str | None = None) -> LLMClient:
    """Build the active free LLM client (Gemini preferred, then Groq)."""
    provider = resolve_provider()
    client = LLMClient(provider, model=model)
    logger.info("LLM provider=%s model=%s", client.provider, client.model)
    return client


__all__ = [
    "DEFAULT_MODELS",
    "LLMClient",
    "LLMClientError",
    "get_llm_client",
    "resolve_provider",
]
