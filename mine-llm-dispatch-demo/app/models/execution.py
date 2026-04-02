from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.proposal import IncidentWorkflowResponse


class ExecutionRequest(BaseModel):
    actor: str
    comment: str = ""
    adapter: str = "mock_fms"


class ExecutionRecord(BaseModel):
    execution_id: str
    ts: datetime
    workflow_id: str
    incident_id: str
    proposal_revision: int
    actor: str
    adapter: str
    status: Literal["SUBMITTED", "ACKNOWLEDGED", "REJECTED"] = "SUBMITTED"
    comment: str = ""
    workflow: IncidentWorkflowResponse
    model_config = ConfigDict(extra="forbid")


class AuditReplayRequest(BaseModel):
    limit: int = Field(default=500, ge=1, le=5000)
    since_minutes: int = 10
    operator_role: str = "dispatcher"
    include_diagnose: bool = False
    include_forecast: bool = False
    run_workflow: bool = True


class AuditReplayResponse(BaseModel):
    replay_id: str
    replayed_event_count: int
    replayed_telemetry_count: int
    replayed_alarm_count: int
    snapshot: dict
    workflow: IncidentWorkflowResponse | None = None
