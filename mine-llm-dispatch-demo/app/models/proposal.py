from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class TaskRef(BaseModel):
    load: str
    dump: str
    route: str


class ProposalExpectation(BaseModel):
    eta_min: float
    queue_wait_min: float


class TruckProposal(BaseModel):
    truck_id: str
    next_task: TaskRef
    constraints_checked: list[str] = Field(default_factory=list)
    expected: ProposalExpectation
    risk_notes: list[str] = Field(default_factory=list)


class DispatchExpectedImpact(BaseModel):
    throughput_delta_pct: float
    empty_distance_delta_pct: float
    queue_time_delta_pct: float


class DispatchProposal(BaseModel):
    proposal_id: str
    generated_by: str
    ts: datetime
    dispatch_cycle_seconds: int
    proposals: list[TruckProposal]
    expected_impact: DispatchExpectedImpact
    requires_human_confirmation: bool = True
    evidence: list[str] = Field(default_factory=list)
    model_config = ConfigDict(extra="forbid")


class IncidentSummary(BaseModel):
    alarm_id: str
    level: str
    why: str
    impact: str


class TriageAction(BaseModel):
    action: str
    owner: Literal["调度员", "安全员", "运维"]
    deadline_min: int


class WorkOrderDraft(BaseModel):
    status: Literal["OPEN", "IN_PROGRESS", "DONE"] = "OPEN"
    incident_owner: str
    response_steps: list[str] = Field(default_factory=list)
    follow_up: list[str] = Field(default_factory=list)


class TriageResponse(BaseModel):
    ts: datetime
    top_incidents: list[IncidentSummary]
    triage_actions: list[TriageAction]
    work_order_draft: WorkOrderDraft
    requires_human_confirmation: bool = True
    confidence: float = Field(ge=0, le=1)
    evidence: list[str] = Field(default_factory=list)


class GatekeeperResponse(BaseModel):
    status: Literal["PASS", "FAIL"]
    violations: list[str] = Field(default_factory=list)
    required_changes: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)


class RcaHypothesis(BaseModel):
    hypothesis: str
    supporting_evidence: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    next_check: str


class DiagnoseResponse(BaseModel):
    ts: datetime
    rca_tree: list[RcaHypothesis]
    workaround: list[str] = Field(default_factory=list)
    rollback_plan: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    evidence: list[str] = Field(default_factory=list)


class ForecastPoint(BaseModel):
    horizon_min: int
    throughput_tph: float
    queue_wait_min: float
    congestion_index: float


class ScenarioCompare(BaseModel):
    scenario: str
    throughput_delta_pct: float
    queue_time_delta_pct: float
    note: str


class ForecastResponse(BaseModel):
    ts: datetime
    forecast: list[ForecastPoint]
    what_if: list[ScenarioCompare]
    confidence: float = Field(ge=0, le=1)
    evidence: list[str] = Field(default_factory=list)


class DispatchRequest(BaseModel):
    plan: dict[str, Any] = Field(default_factory=dict)
    operator_intent: str = "保障安全、降低空驶并控制调度频率"


class GatekeeperRequest(BaseModel):
    proposal: DispatchProposal
    operator_role: str = "dispatcher"


class ForecastRequest(BaseModel):
    horizons: list[int] = Field(default_factory=lambda: [30, 60])


class TriageRequest(BaseModel):
    since_minutes: int = 10


class DiagnoseRequest(BaseModel):
    focus: str = "current_shift"
