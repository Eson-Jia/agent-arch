from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.models.audit import AuditEvent
from app.rag.retrieve import retrieve_top_k
from app.storage.audit_store import AuditStore
from app.storage.state_store import StateStore
from app.storage.vector_store import VectorStore
from app.utils.ids import generate_id
from app.utils.time import now_ts


class BaseAgent(ABC):
    agent_name = "base_agent"

    def __init__(
        self,
        state_store: StateStore,
        audit_store: AuditStore,
        vector_store: VectorStore,
        timezone_name: str,
    ) -> None:
        self.state_store = state_store
        self.audit_store = audit_store
        self.vector_store = vector_store
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

    @abstractmethod
    def run(self, input_data: dict[str, Any] | None = None) -> Any:
        raise NotImplementedError
