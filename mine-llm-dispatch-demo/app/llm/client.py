from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from app.settings import Settings

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(
        self,
        provider: str,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        max_tokens: int = 1500,
        timeout_seconds: float = 20.0,
    ) -> None:
        self.provider = provider
        self.model = model
        self.max_tokens = max_tokens
        self.timeout_seconds = timeout_seconds
        self._client: Any | None = None
        self._live = False
        if provider != "anthropic" or not api_key:
            return
        try:
            from anthropic import Anthropic
        except ImportError:
            logger.warning("Anthropic SDK is not installed; falling back to deterministic agent outputs")
            return
        self._client = Anthropic(
            api_key=api_key,
            base_url=base_url,
            http_client=httpx.Client(timeout=timeout_seconds, trust_env=False),
            timeout=timeout_seconds,
            max_retries=1,
        )
        self._live = True

    @property
    def is_live(self) -> bool:
        return self._live

    def generate_json(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any] | None:
        if not self._live or self._client is None or not self.model:
            return None
        try:
            message = self._client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=0,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            text = self._extract_text(message)
            return self._extract_json(text)
        except Exception:
            logger.exception("Anthropic request failed; using deterministic fallback")
            return None

    def _extract_text(self, message: Any) -> str:
        blocks = getattr(message, "content", [])
        parts = [getattr(block, "text", "") for block in blocks if getattr(block, "type", None) == "text"]
        return "\n".join(part for part in parts if part).strip()

    def _extract_json(self, text: str) -> dict[str, Any]:
        candidate = text.strip()
        if candidate.startswith("```"):
            candidate = re.sub(r"^```(?:json)?\s*", "", candidate, count=1)
            candidate = re.sub(r"\s*```$", "", candidate, count=1)
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("No JSON object found in Anthropic response")
        return json.loads(candidate[start : end + 1])


def build_llm_client(settings: Settings) -> LLMClient:
    if settings.llm_provider == "anthropic":
        return LLMClient(
            provider="anthropic",
            model=settings.anthropic_model,
            api_key=settings.resolved_llm_api_key,
            base_url=settings.anthropic_base_url,
            max_tokens=settings.anthropic_max_tokens,
            timeout_seconds=settings.anthropic_timeout_seconds,
        )
    return LLMClient(provider="mock")
