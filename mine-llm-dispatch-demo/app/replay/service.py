from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from app.agents.diagnose_agent import DiagnoseAgent
from app.agents.dispatch_agent import DispatchAgent
from app.agents.forecast_agent import ForecastAgent
from app.agents.gatekeeper_agent import GatekeeperAgent
from app.agents.triage_agent import TriageAgent
from app.llm.client import LLMClient
from app.models.alarm import SafetyAlarmEvent
from app.models.execution import AuditReplayRequest, AuditReplayResponse
from app.models.proposal import IncidentWorkflowRequest
from app.models.telemetry import VehicleTelemetry
from app.optim.solver import DispatchSolver
from app.rules.rule_engine import RuleEngine
from app.storage.audit_store import AuditStore
from app.storage.state_store import StateStore
from app.storage.vector_store import VectorStore
from app.storage.workflow_store import WorkflowStore
from app.utils.ids import generate_id
from app.workflows.incident_response import IncidentResponseOrchestrator


class AuditReplayService:
    def __init__(
        self,
        *,
        audit_store: AuditStore,
        vector_store: VectorStore,
        llm_client: LLMClient,
        rule_engine: RuleEngine,
        timezone_name: str,
        snapshot_window_minutes: int,
    ) -> None:
        self.audit_store = audit_store
        self.vector_store = vector_store
        self.llm_client = llm_client
        self.rule_engine = rule_engine
        self.timezone_name = timezone_name
        self.snapshot_window_minutes = snapshot_window_minutes

    def replay(self, request: AuditReplayRequest) -> AuditReplayResponse:
        events = self.audit_store.list_events(limit=request.limit)
        replay_id = generate_id("RPL")
        replayed_telemetry_count = 0
        replayed_alarm_count = 0

        with TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            temp_state_store = StateStore(
                timezone_name=self.timezone_name,
                window_minutes=self.snapshot_window_minutes,
            )
            temp_audit_store = AuditStore(tmp_path / "replay_audit.jsonl")
            temp_workflow_store = WorkflowStore(tmp_path / "replay_workflows.json", timezone_name=self.timezone_name)
            triage_agent = TriageAgent(temp_state_store, temp_audit_store, self.vector_store, self.llm_client, self.timezone_name)
            dispatch_agent = DispatchAgent(
                temp_state_store,
                temp_audit_store,
                self.vector_store,
                self.llm_client,
                self.timezone_name,
                solver=DispatchSolver(self.rule_engine),
            )
            gatekeeper_agent = GatekeeperAgent(
                temp_state_store,
                temp_audit_store,
                self.vector_store,
                self.llm_client,
                self.timezone_name,
                rule_engine=self.rule_engine,
            )
            diagnose_agent = DiagnoseAgent(temp_state_store, temp_audit_store, self.vector_store, self.llm_client, self.timezone_name)
            forecast_agent = ForecastAgent(temp_state_store, temp_audit_store, self.vector_store, self.llm_client, self.timezone_name)
            orchestrator = IncidentResponseOrchestrator(
                state_store=temp_state_store,
                audit_store=temp_audit_store,
                workflow_store=temp_workflow_store,
                triage_agent=triage_agent,
                dispatch_agent=dispatch_agent,
                gatekeeper_agent=gatekeeper_agent,
                diagnose_agent=diagnose_agent,
                forecast_agent=forecast_agent,
                timezone_name=self.timezone_name,
            )

            for event in events:
                event_type = event.get("event_type")
                meta = event.get("meta", {})
                if meta.get("result") != "accepted":
                    continue
                if event_type == "telemetry_ingest":
                    temp_state_store.upsert_telemetry(VehicleTelemetry.model_validate(event["payload"]))
                    replayed_telemetry_count += 1
                if event_type == "alarm_ingest":
                    temp_state_store.add_alarm(SafetyAlarmEvent.model_validate(event["payload"]))
                    replayed_alarm_count += 1

            snapshot = temp_state_store.snapshot(since_minutes=request.since_minutes)
            workflow = None
            if request.run_workflow:
                workflow = orchestrator.run(
                    IncidentWorkflowRequest(
                        since_minutes=request.since_minutes,
                        operator_role=request.operator_role,
                        include_diagnose=request.include_diagnose,
                        include_forecast=request.include_forecast,
                    )
                )

        return AuditReplayResponse(
            replay_id=replay_id,
            replayed_event_count=replayed_telemetry_count + replayed_alarm_count,
            replayed_telemetry_count=replayed_telemetry_count,
            replayed_alarm_count=replayed_alarm_count,
            snapshot=snapshot,
            workflow=workflow,
        )
