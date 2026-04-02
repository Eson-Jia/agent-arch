from __future__ import annotations

from abc import ABC, abstractmethod
from copy import deepcopy
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
        self._last_llm_status = "not_applicable"
        self._last_rag_metrics: dict[str, Any] = {}

    def _snapshot(self, since_minutes: int | None = None) -> dict[str, Any]:
        return self.state_store.snapshot(since_minutes=since_minutes)

    def _resolve_snapshot(
        self,
        input_data: dict[str, Any] | None = None,
        *,
        since_minutes: int | None = None,
    ) -> dict[str, Any]:
        if input_data and "_snapshot" in input_data:
            return deepcopy(input_data["_snapshot"])
        return self._snapshot(since_minutes=since_minutes)

    def _trace_id(self, input_data: dict[str, Any] | None = None) -> str | None:
        if not input_data:
            return None
        trace_id = input_data.get("_trace_id")
        return str(trace_id) if trace_id else None

    def _retrieve(self, query: str, k: int = 3) -> tuple[list[dict[str, Any]], list[str]]:
        hits = retrieve_top_k(self.vector_store, query, k=k)
        scores = [round(hit.score, 4) for hit in hits]
        self._last_rag_metrics = {
            "rag_query": query,
            "rag_hit_count": len(hits),
            "rag_top_score": max(scores) if scores else 0.0,
            "rag_avg_score": round(sum(scores) / len(scores), 4) if scores else 0.0,
            "embedding_provider": self.vector_store.embedding_provider.name,
            "embedding_status": getattr(self.vector_store.embedding_provider, "last_outcome_reason", "unknown"),
        }
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

    def _rag_meta(self) -> dict[str, Any]:
        return dict(self._last_rag_metrics)

    def _audit(
        self,
        payload: dict[str, Any],
        evidence: list[str],
        *,
        trace_id: str | None = None,
        snapshot_version: int | None = None,
        meta: dict[str, Any] | None = None,
    ) -> None:
        event = AuditEvent(
            event_id=generate_id("AUD"),
            ts=now_ts(self.timezone_name),
            event_type="agent_output",
            actor=self.agent_name,
            trace_id=trace_id,
            snapshot_version=snapshot_version,
            meta=meta or {},
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
            self._last_llm_status = self.llm_client.last_outcome_reason
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
            self._last_llm_status = self.llm_client.last_outcome_reason
            return None
        try:
            validated = response_model.model_validate(payload)
            self._last_llm_status = "success"
            return validated
        except ValidationError:
            self._last_llm_status = "validation_error"
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
