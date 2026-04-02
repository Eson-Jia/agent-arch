from __future__ import annotations

import json
import os
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Iterator

from fastapi.testclient import TestClient

from app.main import create_app
from app.settings import get_settings


@contextmanager
def _temporary_env(overrides: dict[str, str]) -> Iterator[None]:
    original: dict[str, str | None] = {key: os.environ.get(key) for key in overrides}
    try:
        for key, value in overrides.items():
            os.environ[key] = value
        get_settings.cache_clear()
        yield
    finally:
        for key, value in original.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


def _evaluate_case(client: TestClient, case: dict[str, Any]) -> dict[str, Any]:
    for telemetry in case.get("telemetry", []):
        client.post("/ingest/telemetry", json=telemetry).raise_for_status()
    for alarm in case.get("alarms", []):
        client.post("/ingest/alarm", json=alarm).raise_for_status()

    triage = client.post("/agents/triage", json={"since_minutes": case["workflow_request"].get("since_minutes", 10)})
    triage.raise_for_status()
    triage_json = triage.json()

    dispatch = client.post("/agents/dispatch", json={})
    dispatch.raise_for_status()
    dispatch_json = dispatch.json()

    workflow = client.post("/workflows/incident-response", json=case["workflow_request"])
    workflow.raise_for_status()
    workflow_json = workflow.json()

    expected = case["expected"]
    first_alarm = triage_json["top_incidents"][0]["alarm_id"]
    blocked_routes = set(expected.get("blocked_routes_forbidden", []))
    blocked_avoided = all(item["next_task"]["route"] not in blocked_routes for item in dispatch_json["proposals"])
    doc_evidence_count = len([item for item in workflow_json["evidence"] if str(item).startswith("DOC-")])

    passed = (
        workflow_json["final_status"] == expected["final_status"]
        and first_alarm == expected["first_alarm_id"]
        and blocked_avoided
    )
    return {
        "case_id": case["case_id"],
        "passed": passed,
        "first_alarm_id": first_alarm,
        "final_status": workflow_json["final_status"],
        "blocked_route_avoided": blocked_avoided,
        "doc_evidence_count": doc_evidence_count,
        "approval_status": workflow_json["approval_status"],
    }


def run_offline_evaluation(cases_path: Path, llm_provider: str = "mock") -> dict[str, Any]:
    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    results: list[dict[str, Any]] = []

    for case in cases:
        with TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            project_root = Path(__file__).resolve().parents[2]
            with _temporary_env(
                {
                    "APP_ENV": "test",
                    "LLM_PROVIDER": llm_provider,
                    "LLM_API_KEY": "",
                    "ANTHROPIC_API_KEY": "",
                    "ANTHROPIC_AUTH_TOKEN": "",
                    "ANTHROPIC_BASE_URL": "",
                    "STATE_STORE_PATH": str(tmp_path / "state.json"),
                    "WORKFLOW_STORE_PATH": str(tmp_path / "workflows.json"),
                    "AUDIT_LOG_PATH": str(tmp_path / "audit.jsonl"),
                    "VECTOR_STORE_PATH": str(tmp_path / "vector"),
                    "KNOWLEDGE_BASE_PATH": str(project_root / "docs/knowledge_base"),
                    "RULES_PATH": str(project_root / "app/rules/sample_rules.yaml"),
                }
            ):
                with TestClient(create_app()) as client:
                    results.append(_evaluate_case(client, case))

    pass_count = sum(1 for item in results if item["passed"])
    blocked_route_avoidance_rate = sum(1 for item in results if item["blocked_route_avoided"]) / len(results)
    avg_doc_evidence_count = sum(item["doc_evidence_count"] for item in results) / len(results)
    return {
        "case_count": len(results),
        "pass_count": pass_count,
        "pass_rate": round(pass_count / len(results), 4) if results else 0.0,
        "blocked_route_avoidance_rate": round(blocked_route_avoidance_rate, 4) if results else 0.0,
        "avg_doc_evidence_count": round(avg_doc_evidence_count, 4) if results else 0.0,
        "results": results,
    }
