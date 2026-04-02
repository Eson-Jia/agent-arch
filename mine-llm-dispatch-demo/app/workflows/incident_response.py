from __future__ import annotations

from app.agents.diagnose_agent import DiagnoseAgent
from app.agents.dispatch_agent import DispatchAgent
from app.agents.forecast_agent import ForecastAgent
from app.agents.gatekeeper_agent import GatekeeperAgent
from app.agents.triage_agent import TriageAgent
from app.models.audit import AuditEvent
from app.models.proposal import (
    IncidentWorkflowRequest,
    IncidentWorkflowResponse,
    WorkflowApprovalRecord,
    WorkflowApprovalRequest,
    WorkflowResubmitRequest,
)
from app.storage.audit_store import AuditStore
from app.storage.state_store import StateStore
from app.storage.workflow_store import WorkflowStore
from app.utils.ids import generate_id
from app.utils.time import now_ts


class IncidentResponseOrchestrator:
    actor_name = "incident_response_orchestrator_v1"

    def __init__(
        self,
        state_store: StateStore,
        audit_store: AuditStore,
        workflow_store: WorkflowStore,
        triage_agent: TriageAgent,
        dispatch_agent: DispatchAgent,
        gatekeeper_agent: GatekeeperAgent,
        diagnose_agent: DiagnoseAgent,
        forecast_agent: ForecastAgent,
        timezone_name: str,
    ) -> None:
        self.state_store = state_store
        self.audit_store = audit_store
        self.workflow_store = workflow_store
        self.triage_agent = triage_agent
        self.dispatch_agent = dispatch_agent
        self.gatekeeper_agent = gatekeeper_agent
        self.diagnose_agent = diagnose_agent
        self.forecast_agent = forecast_agent
        self.timezone_name = timezone_name

    def _execute(
        self,
        *,
        workflow_id: str,
        incident_id: str,
        since_minutes: int,
        operator_role: str,
        include_diagnose: bool,
        include_forecast: bool,
        proposal_revision: int,
        approval_history: list[WorkflowApprovalRecord],
        audit_event_type: str,
    ) -> IncidentWorkflowResponse:
        snapshot = self.state_store.snapshot(since_minutes=since_minutes)

        triage = self.triage_agent.run(
            {
                "since_minutes": since_minutes,
                "_snapshot": snapshot,
                "_trace_id": workflow_id,
            }
        )
        dispatch = self.dispatch_agent.run({"_snapshot": snapshot, "_trace_id": workflow_id})
        gatekeeper = self.gatekeeper_agent.run(
            {
                "proposal": dispatch.model_dump(mode="json"),
                "operator_role": operator_role,
                "_snapshot": snapshot,
                "_trace_id": workflow_id,
            }
        )

        diagnose = None
        if include_diagnose:
            diagnose = self.diagnose_agent.run({"_snapshot": snapshot, "_trace_id": workflow_id})

        forecast = None
        if include_forecast:
            forecast = self.forecast_agent.run(
                {
                    "horizons": [30, 60],
                    "_snapshot": snapshot,
                    "_trace_id": workflow_id,
                }
            )

        evidence: list[str] = []
        for source in [
            triage.evidence,
            dispatch.evidence,
            gatekeeper.evidence,
            diagnose.evidence if diagnose else [],
            forecast.evidence if forecast else [],
        ]:
            for item in source:
                if item and item not in evidence:
                    evidence.append(item)

        requires_human_confirmation = dispatch.requires_human_confirmation or triage.requires_human_confirmation
        approval_status = (
            "FAILED_GATEKEEPER"
            if gatekeeper.status == "FAIL"
            else "PENDING_APPROVAL"
            if requires_human_confirmation
            else "APPROVED"
        )
        approval_id = generate_id("APR") if approval_status == "PENDING_APPROVAL" else None
        if approval_id is not None:
            approval_history.append(
                WorkflowApprovalRecord(
                    approval_id=approval_id,
                    action="SUBMIT",
                    actor=self.actor_name,
                    ts=now_ts(self.timezone_name),
                    comment="workflow submitted for human approval",
                    proposal_revision=proposal_revision,
                )
            )

        response = IncidentWorkflowResponse(
            workflow_id=workflow_id,
            incident_id=incident_id,
            snapshot_id=snapshot["snapshot_id"],
            snapshot_version=snapshot["snapshot_version"],
            final_status=gatekeeper.status,
            approval_id=approval_id,
            approval_status=approval_status,
            proposal_revision=proposal_revision,
            requires_human_confirmation=requires_human_confirmation,
            triage=triage,
            dispatch=dispatch,
            gatekeeper=gatekeeper,
            diagnose=diagnose,
            forecast=forecast,
            approval_history=approval_history,
            evidence=evidence,
        )
        self.workflow_store.upsert(response)
        self.audit_store.append(
            AuditEvent(
                event_id=generate_id("AUD"),
                ts=now_ts(self.timezone_name),
                event_type=audit_event_type,
                actor=self.actor_name,
                trace_id=workflow_id,
                snapshot_version=snapshot["snapshot_version"],
                meta={
                    "approval_status": approval_status,
                    "proposal_revision": proposal_revision,
                },
                evidence=evidence,
                payload=response.model_dump(mode="json"),
            )
        )
        return response

    def run(self, request: IncidentWorkflowRequest) -> IncidentWorkflowResponse:
        workflow_id = generate_id("WFL")
        incident_id = generate_id("INC")
        return self._execute(
            workflow_id=workflow_id,
            incident_id=incident_id,
            since_minutes=request.since_minutes,
            operator_role=request.operator_role,
            include_diagnose=request.include_diagnose,
            include_forecast=request.include_forecast,
            proposal_revision=1,
            approval_history=[],
            audit_event_type="workflow_run",
        )

    def get(self, workflow_id: str) -> IncidentWorkflowResponse | None:
        return self.workflow_store.get(workflow_id)

    def approve(self, workflow_id: str, request: WorkflowApprovalRequest) -> IncidentWorkflowResponse:
        record = self.workflow_store.apply_approval(workflow_id, request)
        self.audit_store.append(
            AuditEvent(
                event_id=generate_id("AUD"),
                ts=now_ts(self.timezone_name),
                event_type="workflow_approval",
                actor=request.actor,
                trace_id=workflow_id,
                snapshot_version=record.snapshot_version,
                meta={
                    "approval_status": record.approval_status,
                    "proposal_revision": record.proposal_revision,
                },
                evidence=record.evidence,
                payload=record.model_dump(mode="json"),
            )
        )
        return record

    def resubmit(self, workflow_id: str, request: WorkflowResubmitRequest) -> IncidentWorkflowResponse:
        existing = self.workflow_store.get(workflow_id)
        if existing is None:
            raise KeyError(workflow_id)
        if existing.approval_status not in {"REJECTED", "FAILED_GATEKEEPER"}:
            raise ValueError(f"workflow {workflow_id} cannot be resubmitted from {existing.approval_status}")

        approval_history = list(existing.approval_history)
        return self._execute(
            workflow_id=existing.workflow_id,
            incident_id=existing.incident_id,
            since_minutes=request.since_minutes,
            operator_role=request.operator_role,
            include_diagnose=request.include_diagnose,
            include_forecast=request.include_forecast,
            proposal_revision=existing.proposal_revision + 1,
            approval_history=approval_history,
            audit_event_type="workflow_resubmit",
        )
