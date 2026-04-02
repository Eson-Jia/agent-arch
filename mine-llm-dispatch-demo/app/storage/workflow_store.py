from __future__ import annotations

import json
from pathlib import Path
from threading import RLock

from app.models.proposal import IncidentWorkflowResponse, WorkflowApprovalRequest, WorkflowApprovalRecord
from app.utils.time import now_ts


class WorkflowStore:
    def __init__(self, path: Path, timezone_name: str = "Asia/Shanghai") -> None:
        self.path = path
        self.timezone_name = timezone_name
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._records: dict[str, IncidentWorkflowResponse] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            self.path.write_text("{}", encoding="utf-8")
            return
        raw = self.path.read_text(encoding="utf-8").strip()
        if not raw:
            return
        payload = json.loads(raw)
        self._records = {
            workflow_id: IncidentWorkflowResponse.model_validate(record)
            for workflow_id, record in payload.items()
        }

    def _persist_locked(self) -> None:
        payload = {
            workflow_id: record.model_dump(mode="json")
            for workflow_id, record in self._records.items()
        }
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def upsert(self, record: IncidentWorkflowResponse) -> IncidentWorkflowResponse:
        with self._lock:
            self._records[record.workflow_id] = record
            self._persist_locked()
        return record

    def get(self, workflow_id: str) -> IncidentWorkflowResponse | None:
        with self._lock:
            record = self._records.get(workflow_id)
            if record is None:
                return None
            return IncidentWorkflowResponse.model_validate(record.model_dump(mode="json"))

    def list_records(self, limit: int = 100) -> list[IncidentWorkflowResponse]:
        with self._lock:
            values = list(self._records.values())
        return [
            IncidentWorkflowResponse.model_validate(record.model_dump(mode="json"))
            for record in values[-limit:]
        ]

    def apply_approval(self, workflow_id: str, request: WorkflowApprovalRequest) -> IncidentWorkflowResponse:
        with self._lock:
            record = self._records.get(workflow_id)
            if record is None:
                raise KeyError(workflow_id)
            if record.approval_status != "PENDING_APPROVAL":
                raise ValueError(f"workflow {workflow_id} is not pending approval")
            if (
                request.expected_proposal_revision is not None
                and request.expected_proposal_revision != record.proposal_revision
            ):
                raise ValueError("proposal revision mismatch")

            record.approval_status = "APPROVED" if request.action == "APPROVE" else "REJECTED"
            record.approval_history.append(
                WorkflowApprovalRecord(
                    approval_id=record.approval_id or "",
                    action=request.action,
                    actor=request.actor,
                    ts=now_ts(self.timezone_name),
                    comment=request.comment,
                    proposal_revision=record.proposal_revision,
                )
            )
            self._records[workflow_id] = record
            self._persist_locked()
            return IncidentWorkflowResponse.model_validate(record.model_dump(mode="json"))
