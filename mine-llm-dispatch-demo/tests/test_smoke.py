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
    monkeypatch.setenv("AUDIT_LOG_PATH", str(tmp_path / "audit.jsonl"))
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
