from __future__ import annotations

from abc import ABC, abstractmethod
import json
import logging
from typing import Any

from pydantic import BaseModel, ValidationError

from app.llm.client import LLMClient
from app.models.audit import AuditEvent
from app.rag.retrieve import retrieve_top_k
from app.storage.audit_store import AuditStore
from app.storage.state_store import StateStore
from app.storage.vector_store import VectorStore
from app.utils.ids import generate_id
from app.utils.time import now_ts

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    agent_name = "base_agent"

    def __init__(
        self,
        state_store: StateStore,
        audit_store: AuditStore,
        vector_store: VectorStore,
        llm_client: LLMClient,
        timezone_name: str,
    ) -> None:
        self.state_store = state_store
        self.audit_store = audit_store
        self.vector_store = vector_store
        self.llm_client = llm_client
        self.timezone_name = timezone_name

    def _snapshot(self, since_minutes: int | None = None) -> dict[str, Any]:
        return self.state_store.snapshot(since_minutes=since_minutes)

    def _retrieve(self, query: str, k: int = 3) -> tuple[list[dict[str, Any]], list[str]]:
        hits = retrieve_top_k(self.vector_store, query, k=k)
        evidence = [hit.doc_id for hit in hits]
        payload = [
            {
                "doc_id": hit.doc_id,
                "snippet": hit.snippet,
                "score": round(hit.score, 4),
                "metadata": hit.metadata,
            }
            for hit in hits
        ]
        return payload, evidence

    def _audit(self, payload: dict[str, Any], evidence: list[str]) -> None:
        event = AuditEvent(
            event_id=generate_id("AUD"),
            ts=now_ts(self.timezone_name),
            event_type="agent_output",
            actor=self.agent_name,
            evidence=evidence,
            payload=payload,
        )
        self.audit_store.append(event)

    def _llm_refine(
        self,
        response_model: type[BaseModel],
        system_prompt: str,
        prompt_context: dict[str, Any],
    ) -> BaseModel | None:
        if not self.llm_client.is_live:
            return None
        schema = response_model.model_json_schema()
        prompt = "\n\n".join(
            [
                "Return exactly one JSON object that matches the schema.",
                f"JSON schema:\n{json.dumps(schema, ensure_ascii=False)}",
                f"Context:\n{json.dumps(prompt_context, ensure_ascii=False, default=str)}",
                "Do not include markdown fences or explanatory text.",
            ]
        )
        payload = self.llm_client.generate_json(system_prompt=system_prompt, user_prompt=prompt)
        if payload is None:
            return None
        try:
            return response_model.model_validate(payload)
        except ValidationError:
            logger.exception("LLM output failed validation for %s", response_model.__name__)
            return None

    def _merge_evidence(self, primary: list[str], fallback: list[str]) -> list[str]:
        merged: list[str] = []
        for item in [*primary, *fallback]:
            if item and item not in merged:
                merged.append(item)
        return merged

    @abstractmethod
    def run(self, input_data: dict[str, Any] | None = None) -> Any:
        raise NotImplementedError
