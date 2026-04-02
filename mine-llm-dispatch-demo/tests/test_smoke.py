from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.settings import get_settings


def test_smoke_script_exists():
    project_root = Path(__file__).resolve().parents[1]
    assert (project_root / "scripts" / "smoke_test.py").exists()


def _configure_env(tmp_path, monkeypatch, llm_provider: str = "mock"):
    project_root = Path(__file__).resolve().parents[1]
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("LLM_PROVIDER", llm_provider)
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "")
    monkeypatch.setenv("STATE_STORE_PATH", str(tmp_path / "state.json"))
    monkeypatch.setenv("WORKFLOW_STORE_PATH", str(tmp_path / "workflows.json"))
    monkeypatch.setenv("AUDIT_LOG_PATH", str(tmp_path / "audit.jsonl"))
    monkeypatch.setenv("EXECUTION_LOG_PATH", str(tmp_path / "executions.jsonl"))
    monkeypatch.setenv("VECTOR_STORE_PATH", str(tmp_path / "vector"))
    monkeypatch.setenv("KNOWLEDGE_BASE_PATH", str(project_root / "docs/knowledge_base"))
    monkeypatch.setenv("RULES_PATH", str(project_root / "app/rules/sample_rules.yaml"))
    get_settings.cache_clear()


def _seed_demo_state(client: TestClient) -> None:
    telemetry_payloads = [
        {
            "ts": "2026-04-02T10:15:23+08:00",
            "truck_id": "T12",
            "pos": {"x": 1023.4, "y": 884.2, "z": 56.7, "map_ver": "map_2026_04_01"},
            "motion": {"speed_mps": 8.2, "heading_deg": 172.3, "mode": "AUTO"},
            "load": {"state": "EMPTY", "payload_t": 0},
            "health": {"fault_code": None, "soc_pct": 63, "engine_temp_c": 72.1},
            "comms": {"rssi_dbm": -82, "uplink_kbps": 3200, "loss_pct_5s": 0.8},
        },
        {
            "ts": "2026-04-02T10:15:30+08:00",
            "truck_id": "T18",
            "pos": {"x": 1004.0, "y": 846.0, "z": 59.4, "map_ver": "map_2026_04_01"},
            "motion": {"speed_mps": 6.8, "heading_deg": 148.0, "mode": "AUTO"},
            "load": {"state": "EMPTY", "payload_t": 0},
            "health": {"fault_code": None, "soc_pct": 71, "engine_temp_c": 69.2},
            "comms": {"rssi_dbm": -85, "uplink_kbps": 3000, "loss_pct_5s": 1.4},
        },
    ]
    alarm_payload = {
        "alarm_id": "ALM-20260402-000872",
        "ts": "2026-04-02T10:16:01+08:00",
        "level": "ORANGE",
        "category": "ROAD_OBSTACLE",
        "location": {"road_segment": "R7", "bbox": [1000, 860, 1060, 910]},
        "impact_zone": {"blocked": True, "detour_routes": ["R9", "R11"]},
        "evidence": [{"type": "cv_event", "id": "CV-77821", "confidence": 0.91}],
    }
    for payload in telemetry_payloads:
        response = client.post("/ingest/telemetry", json=payload)
        assert response.status_code == 200
    response = client.post("/ingest/alarm", json=alarm_payload)
    assert response.status_code == 200


def test_smoke_flow(tmp_path, monkeypatch):
    _configure_env(tmp_path, monkeypatch, llm_provider="mock")

    with TestClient(create_app()) as client:
        _seed_demo_state(client)

        triage = client.post("/agents/triage", json={})
        assert triage.status_code == 200
        assert triage.json()["top_incidents"][0]["alarm_id"] == "ALM-20260402-000872"

        dispatch = client.post("/agents/dispatch", json={})
        assert dispatch.status_code == 200
        dispatch_json = dispatch.json()
        assert dispatch_json["requires_human_confirmation"] is True
        assert dispatch_json["proposals"]
        assert all(item["next_task"]["route"] != "R7" for item in dispatch_json["proposals"])

        gatekeeper = client.post(
            "/agents/gatekeeper",
            json={"proposal": dispatch_json, "operator_role": "dispatcher"},
        )
        assert gatekeeper.status_code == 200
        assert gatekeeper.json()["status"] == "PASS"

        audit = client.get("/audit/events")
        assert audit.status_code == 200
        events = audit.json()
        assert len(events) >= 3
        assert any(event["actor"] == "dispatch_agent_v1" for event in events)

    get_settings.cache_clear()


def test_anthropic_without_key_falls_back_to_deterministic_path(tmp_path, monkeypatch):
    _configure_env(tmp_path, monkeypatch, llm_provider="anthropic")

    with TestClient(create_app()) as client:
        _seed_demo_state(client)

        triage = client.post("/agents/triage", json={})
        assert triage.status_code == 200
        triage_json = triage.json()
        assert triage_json["top_incidents"][0]["alarm_id"] == "ALM-20260402-000872"
        assert "ALM-20260402-000872" in triage_json["evidence"]

        diagnose = client.post("/agents/diagnose", json={})
        assert diagnose.status_code == 200
        assert diagnose.json()["rca_tree"]

        forecast = client.post("/agents/forecast", json={"horizons": [30]})
        assert forecast.status_code == 200
        assert forecast.json()["forecast"][0]["horizon_min"] == 30

    get_settings.cache_clear()


def test_settings_accepts_anthropic_auth_token(tmp_path, monkeypatch):
    _configure_env(tmp_path, monkeypatch, llm_provider="anthropic")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "test-token")
    settings = get_settings()
    assert settings.resolved_llm_api_key == "test-token"
    get_settings.cache_clear()


def test_incident_workflow_uses_versioned_snapshot_and_persists_state(tmp_path, monkeypatch):
    _configure_env(tmp_path, monkeypatch, llm_provider="mock")

    with TestClient(create_app()) as client:
        _seed_demo_state(client)

        workflow = client.post(
            "/workflows/incident-response",
            json={
                "since_minutes": 10,
                "operator_role": "dispatcher",
                "include_diagnose": True,
                "include_forecast": True,
            },
        )
        assert workflow.status_code == 200
        workflow_json = workflow.json()
        assert workflow_json["snapshot_version"] >= 3
        assert workflow_json["snapshot_id"].startswith("SNP-")
        assert workflow_json["incident_id"].startswith("INC-")
        assert workflow_json["approval_status"] == "PENDING_APPROVAL"
        assert workflow_json["proposal_revision"] == 1
        assert workflow_json["triage"]["top_incidents"][0]["alarm_id"] == "ALM-20260402-000872"
        assert workflow_json["dispatch"]["proposals"]
        assert workflow_json["gatekeeper"]["status"] == "PASS"
        assert workflow_json["diagnose"] is not None
        assert workflow_json["forecast"] is not None

        workflow_get = client.get(f"/workflows/{workflow_json['workflow_id']}")
        assert workflow_get.status_code == 200
        assert workflow_get.json()["approval_status"] == "PENDING_APPROVAL"

        rejection = client.post(
            f"/workflows/{workflow_json['workflow_id']}/approval",
            json={
                "action": "REJECT",
                "actor": "shift_supervisor",
                "comment": "needs another proposal revision",
                "expected_proposal_revision": 1,
            },
        )
        assert rejection.status_code == 200
        assert rejection.json()["approval_status"] == "REJECTED"

        resubmit = client.post(
            f"/workflows/{workflow_json['workflow_id']}/resubmit",
            json={
                "since_minutes": 10,
                "operator_role": "dispatcher",
                "include_diagnose": True,
                "include_forecast": True,
                "actor": "dispatcher",
                "comment": "rerun after rejection",
            },
        )
        assert resubmit.status_code == 200
        assert resubmit.json()["proposal_revision"] == 2
        assert resubmit.json()["approval_status"] == "PENDING_APPROVAL"

        approval = client.post(
            f"/workflows/{workflow_json['workflow_id']}/approval",
            json={
                "action": "APPROVE",
                "actor": "shift_supervisor",
                "comment": "approved for execution",
                "expected_proposal_revision": 2,
            },
        )
        assert approval.status_code == 200
        assert approval.json()["approval_status"] == "APPROVED"
        assert approval.json()["proposal_revision"] == 2

        metrics = client.get("/metrics/summary")
        assert metrics.status_code == 200
        metrics_json = metrics.json()
        assert metrics_json["workflow_approved_count"] == 1
        assert metrics_json["workflow_pending_approval_count"] == 0
        assert metrics_json["gatekeeper_pass_count"] >= 1

    get_settings.cache_clear()

    with TestClient(create_app()) as client:
        snapshot = client.get("/state/snapshot")
        assert snapshot.status_code == 200
        snapshot_json = snapshot.json()
        assert snapshot_json["summary"]["active_vehicle_count"] == 2
        assert snapshot_json["summary"]["active_alarm_count"] == 1
        assert snapshot_json["last_suggested_routes"]

    get_settings.cache_clear()


def test_ingest_idempotency_and_metrics_capture_duplicates_and_gatekeeper_failures(tmp_path, monkeypatch):
    _configure_env(tmp_path, monkeypatch, llm_provider="mock")

    telemetry_payload = {
        "source_event_id": "evt-telemetry-1",
        "ts": "2026-04-02T10:15:23+08:00",
        "truck_id": "T12",
        "pos": {"x": 1023.4, "y": 884.2, "z": 56.7, "map_ver": "map_2026_04_01"},
        "motion": {"speed_mps": 8.2, "heading_deg": 172.3, "mode": "AUTO"},
        "load": {"state": "EMPTY", "payload_t": 0},
        "health": {"fault_code": None, "soc_pct": 63, "engine_temp_c": 72.1},
        "comms": {"rssi_dbm": -82, "uplink_kbps": 3200, "loss_pct_5s": 0.8},
    }
    alarm_payload = {
        "source_event_id": "evt-alarm-1",
        "alarm_id": "ALM-20260402-000872",
        "ts": "2026-04-02T10:16:01+08:00",
        "level": "ORANGE",
        "category": "ROAD_OBSTACLE",
        "location": {"road_segment": "R7", "bbox": [1000, 860, 1060, 910]},
        "impact_zone": {"blocked": True, "detour_routes": ["R9", "R11"]},
        "evidence": [{"type": "cv_event", "id": "CV-77821", "confidence": 0.91}],
    }

    with TestClient(create_app()) as client:
        first = client.post("/ingest/telemetry", json=telemetry_payload)
        second = client.post("/ingest/telemetry", json=telemetry_payload)
        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json()["status"] == "accepted"
        assert second.json()["status"] == "duplicate"

        first_alarm = client.post("/ingest/alarm", json=alarm_payload)
        second_alarm = client.post("/ingest/alarm", json=alarm_payload)
        assert first_alarm.json()["status"] == "accepted"
        assert second_alarm.json()["status"] == "duplicate"

        invalid_proposal = {
            "proposal_id": "DSP-TEST-0001",
            "generated_by": "manual",
            "ts": "2026-04-02T10:20:00+08:00",
            "dispatch_cycle_seconds": 60,
            "proposals": [
                {
                    "truck_id": "T12",
                    "next_task": {"load": "L2", "dump": "D2", "route": "R7"},
                    "constraints_checked": [],
                    "expected": {"eta_min": 5.0, "queue_wait_min": 1.0},
                    "risk_notes": [],
                }
            ],
            "expected_impact": {
                "throughput_delta_pct": 0.0,
                "empty_distance_delta_pct": 0.0,
                "queue_time_delta_pct": 0.0,
            },
            "requires_human_confirmation": True,
            "evidence": [],
        }
        gatekeeper = client.post(
            "/agents/gatekeeper",
            json={"proposal": invalid_proposal, "operator_role": "dispatcher"},
        )
        assert gatekeeper.status_code == 200
        assert gatekeeper.json()["status"] == "FAIL"

        metrics = client.get("/metrics/summary")
        assert metrics.status_code == 200
        metrics_json = metrics.json()
        assert metrics_json["duplicate_telemetry_count"] == 1
        assert metrics_json["duplicate_alarm_count"] == 1
        assert metrics_json["gatekeeper_fail_count"] >= 1
        assert metrics_json["gatekeeper_reject_rate"] > 0

    get_settings.cache_clear()


def test_workflow_execution_and_audit_replay(tmp_path, monkeypatch):
    _configure_env(tmp_path, monkeypatch, llm_provider="mock")

    with TestClient(create_app()) as client:
        _seed_demo_state(client)
        workflow = client.post(
            "/workflows/incident-response",
            json={
                "since_minutes": 10,
                "operator_role": "dispatcher",
                "include_diagnose": True,
                "include_forecast": True,
            },
        )
        assert workflow.status_code == 200
        workflow_json = workflow.json()

        approval = client.post(
            f"/workflows/{workflow_json['workflow_id']}/approval",
            json={
                "action": "APPROVE",
                "actor": "shift_supervisor",
                "comment": "approved for execution",
                "expected_proposal_revision": 1,
            },
        )
        assert approval.status_code == 200
        assert approval.json()["approval_status"] == "APPROVED"

        execution = client.post(
            f"/workflows/{workflow_json['workflow_id']}/execute",
            json={"actor": "dispatch_operator", "comment": "submit to mock fms", "adapter": "mock_fms"},
        )
        assert execution.status_code == 200
        execution_json = execution.json()
        assert execution_json["status"] == "SUBMITTED"
        assert execution_json["workflow_id"] == workflow_json["workflow_id"]

        executions = client.get("/executions")
        assert executions.status_code == 200
        execution_records = executions.json()
        assert len(execution_records) == 1
        assert execution_records[0]["workflow_id"] == workflow_json["workflow_id"]

        replay = client.post(
            "/replay/audit",
            json={
                "limit": 200,
                "since_minutes": 10,
                "operator_role": "dispatcher",
                "include_diagnose": False,
                "include_forecast": True,
                "run_workflow": True,
            },
        )
        assert replay.status_code == 200
        replay_json = replay.json()
        assert replay_json["replayed_telemetry_count"] == 2
        assert replay_json["replayed_alarm_count"] == 1
        assert replay_json["snapshot"]["summary"]["active_vehicle_count"] == 2
        assert replay_json["workflow"]["final_status"] == "PASS"

    get_settings.cache_clear()
