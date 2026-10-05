"""LLM client abstraction with Gemini and Mock implementations.

All LLM calls in the application go through this interface so that
switching between live API and deterministic mock is a config change.

Key design decisions:
- Structured output via JSON schema (pydantic model → dict schema).
- Exponential backoff on HTTP 429 (rate limit) built into the Gemini client.
- Every call returns a standardised ``LLMResponse`` with raw text, parsed
  object, model ID, and latency — all logged downstream.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Type

from pydantic import BaseModel

from app.schemas import (
    Emotion,
    PersonaOutput,
    SupervisorAction,
    SupervisorVerdict,
)
from app.llm.rate_limiter import RateLimiterRegistry

logger = logging.getLogger(__name__)


# ── Response wrapper ─────────────────────────────────────────────────────────


@dataclass
class LLMResponse:
    """Standardised wrapper returned by every ``LLMClient.generate`` call."""

    raw: str = ""
    parsed: dict[str, Any] = field(default_factory=dict)
    model: str = ""
    latency_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0


# ── Abstract interface ───────────────────────────────────────────────────────


class LLMClient(ABC):
    """Abstract interface for LLM providers."""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        *,
        system_instruction: str = "",
        response_schema: Type[BaseModel] | None = None,
        temperature: float = 1.0,
        model_override: str | None = None,
    ) -> LLMResponse:
        """Generate a structured response.

        Args:
            prompt: The user/conversation prompt.
            system_instruction: System-level instruction prepended.
            response_schema: Optional Pydantic model for structured output.
            temperature: Sampling temperature.
            model_override: Use this model instead of the default.

        Returns:
            An ``LLMResponse`` with parsed and raw outputs.
        """
        ...


# ── Mock client ──────────────────────────────────────────────────────────────


class MockLLMClient(LLMClient):
    """Deterministic mock for development and testing (``LLM_MODE=mock``).

    Returns canned responses based on the expected ``response_schema``.
    No network calls, no quota usage.
    """

    def __init__(self, default_model: str = "mock-model"):
        self._model = default_model
        self._call_count = 0

    async def generate(
        self,
        prompt: str,
        *,
        system_instruction: str = "",
        response_schema: Type[BaseModel] | None = None,
        temperature: float = 1.0,
        model_override: str | None = None,
    ) -> LLMResponse:
        self._call_count += 1
        model = model_override or self._model

        # Simulate a small delay
        await asyncio.sleep(0.05)
        start = time.perf_counter()

        if response_schema is PersonaOutput:
            # Alternate between two mock responses
            if self._call_count % 2 == 1:
                parsed = {
                    "text": f"[Mock giliran {self._call_count}] "
                    "Halo semuanya! / Selamat pagi dari studio HITS.",
                    "emotion": "happy",
                }
            else:
                parsed = {
                    "text": f"[Mock giliran {self._call_count}] "
                    "Iya bener banget! // Semangat pagi ya semuanya.",
                    "emotion": "excited",
                }
        elif response_schema is SupervisorVerdict:
            parsed = {
                "drift_detected": False,
                "drift_types": [],
                "severity": 0,
                "evidence": "",
                "action": "forward",
                "correction_memory": {
                    "persona_reminder": "",
                    "conversation_summary": "",
                    "facts_to_enforce": [],
                },
                "ledger_updates": [],
            }
        elif "JSON array of numbers" in prompt or "Rate each" in prompt or "questionnaire" in prompt.lower():
            # Mock questionnaire response for experiment testing
            import re
            item_matches = re.findall(r"^\s*(\d+)\.\s+", prompt, flags=re.MULTILINE)
            count = len(set(item_matches)) if item_matches else 10
            mock_ratings = [((self._call_count + i) % 4) + 2 for i in range(count)]
            parsed = mock_ratings
            raw = json.dumps(parsed)
        else:
            # Generic mock
            parsed = {"text": f"[Mock response {self._call_count}]"}
            raw = json.dumps(parsed, ensure_ascii=False)
        latency_ms = int((time.perf_counter() - start) * 1000)

        return LLMResponse(
            raw=raw,
            parsed=parsed,
            model=model,
            latency_ms=latency_ms,
            input_tokens=len(prompt.split()),
            output_tokens=len(raw.split()),
        )


# ── Gemini client ────────────────────────────────────────────────────────────


class GeminiLLMClient(LLMClient):
    """Google Gemini API client via ``google-genai`` SDK.

    Features:
    - Structured output (JSON schema from Pydantic models).
    - Per-model rate limiting via ``RateLimiterRegistry``.
    - Exponential backoff on HTTP 429.
    - Fail injection for testing (``FAIL_INJECT=llm``).
    """

    MAX_RETRIES = 5
    BASE_BACKOFF_SEC = 2.0

    def __init__(
        self,
        api_key: str,
        default_model: str,
        rate_limiter_registry: RateLimiterRegistry | None = None,
        fail_inject: bool = False,
    ):
        from google import genai

        self._client = genai.Client(api_key=api_key)
        self._default_model = default_model
        self._rate_limiters = rate_limiter_registry or RateLimiterRegistry()
        self._fail_inject = fail_inject

    async def generate(
        self,
        prompt: str,
        *,
        system_instruction: str = "",
        response_schema: Type[BaseModel] | None = None,
        temperature: float = 1.0,
        model_override: str | None = None,
    ) -> LLMResponse:
        from google import genai
        from google.genai import types

        if self._fail_inject:
            raise RuntimeError("FAIL_INJECT=llm: simulated LLM failure")

        model = model_override or self._default_model

        # Rate limit
        limiter = self._rate_limiters.get(model)
        await limiter.acquire()

        # Build config
        config_kwargs: dict[str, Any] = {
            "temperature": temperature,
        }
        if system_instruction:
            config_kwargs["system_instruction"] = system_instruction
        if response_schema:
            config_kwargs["response_mime_type"] = "application/json"
            config_kwargs["response_schema"] = response_schema

        config = types.GenerateContentConfig(**config_kwargs)

        # Retry loop with exponential backoff
        last_error: Exception | None = None
        for attempt in range(self.MAX_RETRIES):
            try:
                start = time.perf_counter()
                response = await asyncio.to_thread(
                    self._client.models.generate_content,
                    model=model,
                    contents=prompt,
                    config=config,
                )
                latency_ms = int((time.perf_counter() - start) * 1000)

                raw_text = response.text or ""

                # Parse structured output
                parsed: dict[str, Any] = {}
                if response_schema:
                    try:
                        parsed = json.loads(raw_text)
                        # Validate with pydantic
                        response_schema.model_validate(parsed)
                    except (json.JSONDecodeError, Exception) as parse_err:
                        logger.warning(
                            "Failed to parse structured output: %s",
                            parse_err,
                        )
                        parsed = {"raw_text": raw_text, "parse_error": str(parse_err)}

                # Extract token counts if available
                input_tokens = 0
                output_tokens = 0
                if hasattr(response, "usage_metadata") and response.usage_metadata:
                    input_tokens = getattr(
                        response.usage_metadata, "prompt_token_count", 0
                    ) or 0
                    output_tokens = getattr(
                        response.usage_metadata, "candidates_token_count", 0
                    ) or 0

                logger.info(
                    "Gemini call: model=%s latency=%dms tokens_in=%d tokens_out=%d",
                    model,
                    latency_ms,
                    input_tokens,
                    output_tokens,
                )

                return LLMResponse(
                    raw=raw_text,
                    parsed=parsed,
                    model=model,
                    latency_ms=latency_ms,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                )

            except Exception as e:
                last_error = e
                error_str = str(e).lower()
                is_rate_limit = any(code in error_str for code in ["429", "rate", "503", "unavailable"])

                if is_rate_limit and attempt < self.MAX_RETRIES - 1:
                    backoff = self.BASE_BACKOFF_SEC * (2**attempt)
                    logger.warning(
                        "Rate limited (attempt %d/%d), backing off %.1fs: %s",
                        attempt + 1,
                        self.MAX_RETRIES,
                        backoff,
                        e,
                    )
                    await asyncio.sleep(backoff)
                elif attempt < self.MAX_RETRIES - 1:
                    backoff = self.BASE_BACKOFF_SEC * (2**attempt)
                    logger.warning(
                        "LLM error (attempt %d/%d), retrying in %.1fs: %s",
                        attempt + 1,
                        self.MAX_RETRIES,
                        backoff,
                        e,
                    )
                    await asyncio.sleep(backoff)
                else:
                    logger.error(
                        "LLM failed after %d attempts: %s",
                        self.MAX_RETRIES,
                        e,
                    )

        raise RuntimeError(
            f"LLM call failed after {self.MAX_RETRIES} retries"
        ) from last_error


# ── Factory ──────────────────────────────────────────────────────────────────


def create_llm_client(
    mode: str,
    api_key: str = "",
    default_model: str = "",
    rate_limiter_registry: RateLimiterRegistry | None = None,
    fail_inject: str = "",
) -> LLMClient:
    """Create the appropriate LLM client based on mode.

    Args:
        mode: "live" or "mock".
        api_key: Gemini API key (required for live).
        default_model: Default model ID (required for live).
        rate_limiter_registry: Shared rate limiter registry.
        fail_inject: If contains "llm", inject failures.

    Returns:
        An ``LLMClient`` instance.
    """
    if mode == "mock":
        logger.info("Using MockLLMClient")
        return MockLLMClient(default_model=default_model or "mock-model")

    if not api_key:
        raise ValueError("GEMINI_API_KEY is required when LLM_MODE=live")
    if not default_model:
        raise ValueError(
            "A default model ID is required when LLM_MODE=live"
        )

    logger.info("Using GeminiLLMClient with model=%s", default_model)
    return GeminiLLMClient(
        api_key=api_key,
        default_model=default_model,
        rate_limiter_registry=rate_limiter_registry,
        fail_inject="llm" in fail_inject,
    )
