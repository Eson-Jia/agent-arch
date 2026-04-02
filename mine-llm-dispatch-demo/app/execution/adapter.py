from __future__ import annotations

from app.models.execution import ExecutionRecord, ExecutionRequest
from app.models.proposal import IncidentWorkflowResponse
from app.storage.execution_store import ExecutionStore
from app.utils.ids import generate_id
from app.utils.time import now_ts


class MockExecutionAdapter:
    adapter_name = "mock_fms"

    def __init__(self, execution_store: ExecutionStore, timezone_name: str) -> None:
        self.execution_store = execution_store
        self.timezone_name = timezone_name

    def execute(self, workflow: IncidentWorkflowResponse, request: ExecutionRequest) -> ExecutionRecord:
        record = ExecutionRecord(
            execution_id=generate_id("EXE"),
            ts=now_ts(self.timezone_name),
            workflow_id=workflow.workflow_id,
            incident_id=workflow.incident_id,
            proposal_revision=workflow.proposal_revision,
            actor=request.actor,
            adapter=request.adapter or self.adapter_name,
            status="SUBMITTED",
            comment=request.comment,
            workflow=workflow,
        )
        self.execution_store.append(record)
        return record
