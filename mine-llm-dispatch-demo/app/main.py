from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from fastapi import Body, Depends, FastAPI, Request
from fastapi import HTTPException

from app.agents.diagnose_agent import DiagnoseAgent
from app.agents.dispatch_agent import DispatchAgent
from app.agents.forecast_agent import ForecastAgent
from app.agents.gatekeeper_agent import GatekeeperAgent
from app.agents.triage_agent import TriageAgent
from app.llm.client import LLMClient, build_llm_client
from app.models.alarm import SafetyAlarmEvent
from app.models.audit import AuditEvent
from app.models.proposal import (
    DiagnoseRequest,
    DispatchProposal,
    DispatchRequest,
    ForecastRequest,
    GatekeeperRequest,
    IncidentWorkflowRequest,
    WorkflowApprovalRequest,
    WorkflowResubmitRequest,
    TriageRequest,
)
from app.observability.metrics import summarize_metrics
from app.models.telemetry import VehicleTelemetry
from app.optim.solver import DispatchSolver
from app.rag.ingest import ingest_knowledge_base
from app.rules.rule_engine import RuleEngine
from app.settings import Settings, get_settings
from app.storage.audit_store import AuditStore
from app.storage.state_store import StateStore
from app.storage.vector_store import VectorStore
from app.storage.workflow_store import WorkflowStore
from app.utils.ids import generate_id
from app.utils.logging import configure_logging
from app.utils.time import now_ts
from app.workflows.incident_response import IncidentResponseOrchestrator


@dataclass
class AppServices:
    settings: Settings
    state_store: StateStore
    audit_store: AuditStore
    vector_store: VectorStore
    llm_client: LLMClient
    rule_engine: RuleEngine
    triage_agent: TriageAgent
    dispatch_agent: DispatchAgent
    gatekeeper_agent: GatekeeperAgent
    diagnose_agent: DiagnoseAgent
    forecast_agent: ForecastAgent
    workflow_store: WorkflowStore
    incident_orchestrator: IncidentResponseOrchestrator


def build_services(settings: Settings) -> AppServices:
    state_store = StateStore(
        timezone_name=settings.timezone,
        window_minutes=settings.snapshot_window_minutes,
        path=settings.resolve_path(settings.state_store_path),
    )
    audit_store = AuditStore(settings.resolve_path(settings.audit_log_path))
    vector_store = VectorStore(settings.resolve_path(settings.vector_store_path))
    workflow_store = WorkflowStore(settings.resolve_path(settings.workflow_store_path), timezone_name=settings.timezone)
    llm_client = build_llm_client(settings)
    rule_engine = RuleEngine(settings.resolve_path(settings.rules_path))
    solver = DispatchSolver(rule_engine)
    triage_agent = TriageAgent(state_store, audit_store, vector_store, llm_client, settings.timezone)
    dispatch_agent = DispatchAgent(state_store, audit_store, vector_store, llm_client, settings.timezone, solver=solver)
    gatekeeper_agent = GatekeeperAgent(state_store, audit_store, vector_store, llm_client, settings.timezone, rule_engine=rule_engine)
    diagnose_agent = DiagnoseAgent(state_store, audit_store, vector_store, llm_client, settings.timezone)
    forecast_agent = ForecastAgent(state_store, audit_store, vector_store, llm_client, settings.timezone)
    incident_orchestrator = IncidentResponseOrchestrator(
        state_store=state_store,
        audit_store=audit_store,
        workflow_store=workflow_store,
        triage_agent=triage_agent,
        dispatch_agent=dispatch_agent,
        gatekeeper_agent=gatekeeper_agent,
        diagnose_agent=diagnose_agent,
        forecast_agent=forecast_agent,
        timezone_name=settings.timezone,
    )
    return AppServices(
        settings=settings,
        state_store=state_store,
        audit_store=audit_store,
        vector_store=vector_store,
        llm_client=llm_client,
        rule_engine=rule_engine,
        triage_agent=triage_agent,
        dispatch_agent=dispatch_agent,
        gatekeeper_agent=gatekeeper_agent,
        diagnose_agent=diagnose_agent,
        forecast_agent=forecast_agent,
        workflow_store=workflow_store,
        incident_orchestrator=incident_orchestrator,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    settings = get_settings()
    services = build_services(settings)
    ingest_knowledge_base(services.vector_store, settings.resolve_path(settings.knowledge_base_path))
    app.state.services = services
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Mine LLM Dispatch Demo",
        version="0.1.0",
        description="FastAPI MVP for mine dispatch room multi-agent orchestration.",
        lifespan=lifespan,
    )

    def get_services(request: Request) -> AppServices:
        return request.app.state.services

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/ingest/telemetry")
    def ingest_telemetry(telemetry: VehicleTelemetry, services: AppServices = Depends(get_services)) -> dict[str, str]:
        accepted, event_key = services.state_store.upsert_telemetry(telemetry)
        result = "accepted" if accepted else "duplicate"
        services.audit_store.append(
            AuditEvent(
                event_id=generate_id("AUD"),
                ts=now_ts(services.settings.timezone),
                event_type="telemetry_ingest",
                actor="telemetry_ingest_api",
                trace_id=event_key,
                meta={"result": result, "event_key": event_key},
                payload={"truck_id": telemetry.truck_id, "ts": telemetry.ts.isoformat()},
            )
        )
        return {"status": result, "truck_id": telemetry.truck_id, "event_key": event_key}

    @app.post("/ingest/alarm")
    def ingest_alarm(alarm: SafetyAlarmEvent, services: AppServices = Depends(get_services)) -> dict[str, str]:
        accepted, event_key = services.state_store.add_alarm(alarm)
        result = "accepted" if accepted else "duplicate"
        services.audit_store.append(
            AuditEvent(
                event_id=generate_id("AUD"),
                ts=now_ts(services.settings.timezone),
                event_type="alarm_ingest",
                actor="alarm_ingest_api",
                trace_id=event_key,
                meta={"result": result, "event_key": event_key},
                payload={"alarm_id": alarm.alarm_id, "ts": alarm.ts.isoformat()},
            )
        )
        return {"status": result, "alarm_id": alarm.alarm_id, "event_key": event_key}

    @app.get("/state/snapshot")
    def get_snapshot(services: AppServices = Depends(get_services)) -> dict:
        return services.state_store.snapshot()

    @app.get("/audit/events")
    def get_audit_events(services: AppServices = Depends(get_services), limit: int = 100) -> list[dict]:
        return services.audit_store.list_events(limit=limit)

    @app.get("/metrics/summary")
    def get_metrics_summary(services: AppServices = Depends(get_services)) -> dict:
        events = services.audit_store.list_events(limit=5000)
        workflows = services.workflow_store.list_records(limit=500)
        return summarize_metrics(events, workflows)

    @app.post("/agents/triage")
    def run_triage(
        services: AppServices = Depends(get_services),
        request_body: TriageRequest | None = Body(default=None),
    ):
        body = request_body or TriageRequest()
        return services.triage_agent.run(body.model_dump())

    @app.post("/agents/dispatch", response_model=DispatchProposal)
    def run_dispatch(
        services: AppServices = Depends(get_services),
        request_body: DispatchRequest | None = Body(default=None),
    ):
        body = request_body or DispatchRequest()
        return services.dispatch_agent.run(body.model_dump())

    @app.post("/agents/gatekeeper")
    def run_gatekeeper(request_body: GatekeeperRequest, services: AppServices = Depends(get_services)):
        return services.gatekeeper_agent.run(request_body.model_dump(mode="json"))

    @app.post("/agents/diagnose")
    def run_diagnose(
        services: AppServices = Depends(get_services),
        request_body: DiagnoseRequest | None = Body(default=None),
    ):
        body = request_body or DiagnoseRequest()
        return services.diagnose_agent.run(body.model_dump())

    @app.post("/agents/forecast")
    def run_forecast(
        services: AppServices = Depends(get_services),
        request_body: ForecastRequest | None = Body(default=None),
    ):
        body = request_body or ForecastRequest()
        return services.forecast_agent.run(body.model_dump())

    @app.post("/workflows/incident-response")
    def run_incident_workflow(
        services: AppServices = Depends(get_services),
        request_body: IncidentWorkflowRequest | None = Body(default=None),
    ):
        body = request_body or IncidentWorkflowRequest()
        return services.incident_orchestrator.run(body)

    @app.get("/workflows/{workflow_id}")
    def get_workflow(workflow_id: str, services: AppServices = Depends(get_services)):
        record = services.incident_orchestrator.get(workflow_id)
        if record is None:
            raise HTTPException(status_code=404, detail="workflow not found")
        return record

    @app.post("/workflows/{workflow_id}/approval")
    def approve_workflow(
        workflow_id: str,
        request_body: WorkflowApprovalRequest,
        services: AppServices = Depends(get_services),
    ):
        try:
            return services.incident_orchestrator.approve(workflow_id, request_body)
        except KeyError:
            raise HTTPException(status_code=404, detail="workflow not found") from None
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/workflows/{workflow_id}/resubmit")
    def resubmit_workflow(
        workflow_id: str,
        request_body: WorkflowResubmitRequest,
        services: AppServices = Depends(get_services),
    ):
        try:
            return services.incident_orchestrator.resubmit(workflow_id, request_body)
        except KeyError:
            raise HTTPException(status_code=404, detail="workflow not found") from None
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    return app


app = create_app()
