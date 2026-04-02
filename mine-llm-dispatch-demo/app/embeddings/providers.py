from __future__ import annotations

import hashlib
import json
import logging
import math
from typing import Protocol

import httpx

from app.settings import Settings

logger = logging.getLogger(__name__)


class EmbeddingProvider(Protocol):
    name: str
    last_outcome_reason: str

    def embed(self, text: str) -> list[float]:
        ...

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        ...


class HashEmbeddingProvider:
    def __init__(self, dims: int = 32) -> None:
        self.name = "hash"
        self.dims = dims
        self.last_outcome_reason = "ready"

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dims
        for token in text.lower().split():
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            for index in range(self.dims):
                vector[index] += digest[index % len(digest)] / 255.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        self.last_outcome_reason = "success"
        return [value / norm for value in vector]

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(text) for text in texts]


class HttpEmbeddingProvider:
    def __init__(
        self,
        *,
        api_url: str,
        api_key: str | None,
        model: str | None,
        timeout_seconds: float,
        fallback: HashEmbeddingProvider,
    ) -> None:
        self.name = "http"
        self.api_url = api_url
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.fallback = fallback
        self.last_outcome_reason = "ready"
        self._client = httpx.Client(timeout=timeout_seconds, trust_env=False)

    def embed(self, text: str) -> list[float]:
        return self.embed_many([text])[0]

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload: dict[str, object] = {"input": texts}
        if self.model:
            payload["model"] = self.model
        try:
            response = self._client.post(self.api_url, headers=headers, content=json.dumps(payload))
            response.raise_for_status()
            body = response.json()
            data = body.get("data", [])
            embeddings = [item.get("embedding", []) for item in data]
            if len(embeddings) != len(texts) or any(not embedding for embedding in embeddings):
                raise ValueError("embedding response shape mismatch")
            self.last_outcome_reason = "success"
            return embeddings
        except ValueError:
            self.last_outcome_reason = "invalid_response"
            logger.exception("Embedding provider returned invalid payload; using hash fallback")
        except Exception:
            self.last_outcome_reason = "request_error"
            logger.exception("Embedding request failed; using hash fallback")
        return self.fallback.embed_many(texts)


def build_embedding_provider(settings: Settings) -> EmbeddingProvider:
    fallback = HashEmbeddingProvider(dims=settings.embedding_vector_dims)
    if settings.embedding_provider == "http" and settings.embedding_api_url:
        return HttpEmbeddingProvider(
            api_url=settings.embedding_api_url,
            api_key=settings.embedding_api_key,
            model=settings.embedding_model,
            timeout_seconds=settings.embedding_timeout_seconds,
            fallback=fallback,
        )
    return fallback
