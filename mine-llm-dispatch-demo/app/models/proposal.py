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


WorkflowApprovalStatus = Literal["PENDING_APPROVAL", "APPROVED", "REJECTED", "FAILED_GATEKEEPER"]


class ConversationMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class WorkflowBrief(BaseModel):
    workflow_id: str
    incident_id: str
    approval_status: WorkflowApprovalStatus
    final_status: Literal["PASS", "FAIL"]
    proposal_revision: int


AssistantIntent = Literal[
    "alarm_summary",
    "workflow_status",
    "dispatch_guidance",
    "metrics_summary",
    "general_support",
]


class AssistantChatRequest(BaseModel):
    query: str = ""
    history: list[ConversationMessage] = Field(default_factory=list)
    workflow_id: str | None = None
    since_minutes: int = 30
    workflow_limit: int = 5


class AssistantChatResponse(BaseModel):
    ts: datetime
    intent: AssistantIntent
    answer: str
    suggested_actions: list[str] = Field(default_factory=list)
    follow_up_questions: list[str] = Field(default_factory=list)
    related_workflows: list[WorkflowBrief] = Field(default_factory=list)
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


class IncidentWorkflowRequest(BaseModel):
    since_minutes: int = 10
    operator_role: str = "dispatcher"
    include_diagnose: bool = False
    include_forecast: bool = False


class WorkflowApprovalRecord(BaseModel):
    approval_id: str
    action: Literal["SUBMIT", "APPROVE", "REJECT"]
    actor: str
    ts: datetime
    comment: str = ""
    proposal_revision: int


class WorkflowApprovalRequest(BaseModel):
    action: Literal["APPROVE", "REJECT"]
    actor: str
    comment: str = ""
    expected_proposal_revision: int | None = None


class WorkflowResubmitRequest(BaseModel):
    since_minutes: int = 10
    operator_role: str = "dispatcher"
    include_diagnose: bool = False
    include_forecast: bool = False
    actor: str = "dispatcher"
    comment: str = ""


class IncidentWorkflowResponse(BaseModel):
    workflow_id: str
    incident_id: str
    snapshot_id: str
    snapshot_version: int
    final_status: Literal["PASS", "FAIL"]
    approval_id: str | None = None
    approval_status: WorkflowApprovalStatus
    proposal_revision: int = 1
    requires_human_confirmation: bool = True
    triage: TriageResponse
    dispatch: DispatchProposal
    gatekeeper: GatekeeperResponse
    diagnose: DiagnoseResponse | None = None
    forecast: ForecastResponse | None = None
    approval_history: list[WorkflowApprovalRecord] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
