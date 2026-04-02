from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from fastapi import Body, Depends, FastAPI, Request

from app.agents.diagnose_agent import DiagnoseAgent
from app.agents.dispatch_agent import DispatchAgent
from app.agents.forecast_agent import ForecastAgent
from app.agents.gatekeeper_agent import GatekeeperAgent
from app.agents.triage_agent import TriageAgent
from app.llm.client import LLMClient, build_llm_client
from app.models.alarm import SafetyAlarmEvent
from app.models.proposal import (
    DiagnoseRequest,
    DispatchProposal,
    DispatchRequest,
    ForecastRequest,
    GatekeeperRequest,
    TriageRequest,
)
from app.models.telemetry import VehicleTelemetry
from app.optim.solver import DispatchSolver
from app.rag.ingest import ingest_knowledge_base
from app.rules.rule_engine import RuleEngine
from app.settings import Settings, get_settings
from app.storage.audit_store import AuditStore
from app.storage.state_store import StateStore
from app.storage.vector_store import VectorStore
from app.utils.logging import configure_logging


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


def build_services(settings: Settings) -> AppServices:
    state_store = StateStore(
        timezone_name=settings.timezone,
        window_minutes=settings.snapshot_window_minutes,
    )
    audit_store = AuditStore(settings.resolve_path(settings.audit_log_path))
    vector_store = VectorStore(settings.resolve_path(settings.vector_store_path))
    llm_client = build_llm_client(settings)
    rule_engine = RuleEngine(settings.resolve_path(settings.rules_path))
    solver = DispatchSolver(rule_engine)
    return AppServices(
        settings=settings,
        state_store=state_store,
        audit_store=audit_store,
        vector_store=vector_store,
        llm_client=llm_client,
        rule_engine=rule_engine,
        triage_agent=TriageAgent(state_store, audit_store, vector_store, llm_client, settings.timezone),
        dispatch_agent=DispatchAgent(state_store, audit_store, vector_store, llm_client, settings.timezone, solver=solver),
        gatekeeper_agent=GatekeeperAgent(state_store, audit_store, vector_store, llm_client, settings.timezone, rule_engine=rule_engine),
        diagnose_agent=DiagnoseAgent(state_store, audit_store, vector_store, llm_client, settings.timezone),
        forecast_agent=ForecastAgent(state_store, audit_store, vector_store, llm_client, settings.timezone),
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
        services.state_store.upsert_telemetry(telemetry)
        return {"status": "accepted", "truck_id": telemetry.truck_id}

    @app.post("/ingest/alarm")
    def ingest_alarm(alarm: SafetyAlarmEvent, services: AppServices = Depends(get_services)) -> dict[str, str]:
        services.state_store.add_alarm(alarm)
        return {"status": "accepted", "alarm_id": alarm.alarm_id}

    @app.get("/state/snapshot")
    def get_snapshot(services: AppServices = Depends(get_services)) -> dict:
        return services.state_store.snapshot()

    @app.get("/audit/events")
    def get_audit_events(services: AppServices = Depends(get_services), limit: int = 100) -> list[dict]:
        return services.audit_store.list_events(limit=limit)

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

    return app


app = create_app()
