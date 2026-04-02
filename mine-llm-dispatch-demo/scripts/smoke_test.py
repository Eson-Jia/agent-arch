from __future__ import annotations

import os
from typing import Any

import httpx


BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000")
TIMEOUT_SECONDS = float(os.getenv("SMOKE_TIMEOUT_SECONDS", "10"))


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def _post(client: httpx.Client, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = client.post(path, json=payload)
    response.raise_for_status()
    return response.json()


def main() -> None:
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

    with httpx.Client(base_url=BASE_URL, timeout=TIMEOUT_SECONDS) as client:
        health = client.get("/health")
        health.raise_for_status()

        for payload in telemetry_payloads:
            ingest_result = _post(client, "/ingest/telemetry", payload)
            _assert(ingest_result["status"] == "accepted", "telemetry ingest failed")

        alarm_result = _post(client, "/ingest/alarm", alarm_payload)
        _assert(alarm_result["status"] == "accepted", "alarm ingest failed")

        triage = _post(client, "/agents/triage", {})
        _assert(triage["top_incidents"][0]["alarm_id"] == alarm_payload["alarm_id"], "triage did not return the expected alarm")

        dispatch = _post(client, "/agents/dispatch", {})
        _assert(dispatch["requires_human_confirmation"] is True, "dispatch must require human confirmation")
        _assert(dispatch["proposals"], "dispatch returned no proposals")
        _assert(
            all(item["next_task"]["route"] != "R7" for item in dispatch["proposals"]),
            "dispatch proposed a blocked route",
        )

        gatekeeper = _post(
            client,
            "/agents/gatekeeper",
            {"proposal": dispatch, "operator_role": "dispatcher"},
        )
        _assert(gatekeeper["status"] == "PASS", "gatekeeper did not pass the proposal")

        workflow = _post(
            client,
            "/workflows/incident-response",
            {
                "since_minutes": 10,
                "operator_role": "dispatcher",
                "include_diagnose": True,
                "include_forecast": True,
            },
        )
        _assert(workflow["final_status"] == "PASS", "incident workflow did not pass gatekeeper validation")
        _assert(workflow["snapshot_id"].startswith("SNP-"), "workflow did not return a versioned snapshot id")
        _assert(workflow["approval_status"] == "PENDING_APPROVAL", "workflow should enter pending approval")

        approval = _post(
            client,
            f"/workflows/{workflow['workflow_id']}/approval",
            {
                "action": "REJECT",
                "actor": "shift_supervisor",
                "comment": "need another revision",
                "expected_proposal_revision": 1,
            },
        )
        _assert(approval["approval_status"] == "REJECTED", "workflow rejection did not persist")

        resubmit = _post(
            client,
            f"/workflows/{workflow['workflow_id']}/resubmit",
            {
                "since_minutes": 10,
                "operator_role": "dispatcher",
                "include_diagnose": True,
                "include_forecast": True,
                "actor": "dispatcher",
                "comment": "submit revision 2",
            },
        )
        _assert(resubmit["proposal_revision"] == 2, "workflow resubmit did not bump proposal revision")

        final_approval = _post(
            client,
            f"/workflows/{workflow['workflow_id']}/approval",
            {
                "action": "APPROVE",
                "actor": "shift_supervisor",
                "comment": "approved revision 2",
                "expected_proposal_revision": 2,
            },
        )
        _assert(final_approval["approval_status"] == "APPROVED", "workflow approval did not persist")

        metrics = client.get("/metrics/summary")
        metrics.raise_for_status()
        metrics_json = metrics.json()
        _assert(metrics_json["workflow_approved_count"] >= 1, "metrics did not count approved workflow")

        audit_response = client.get("/audit/events")
        audit_response.raise_for_status()
        audit_events = audit_response.json()
        _assert(len(audit_events) >= 10, "audit log is missing expected workflow events")

    print(
        {
            "base_url": BASE_URL,
            "triage_alarm_id": triage["top_incidents"][0]["alarm_id"],
            "dispatch_proposal_id": dispatch["proposal_id"],
            "gatekeeper_status": gatekeeper["status"],
            "workflow_id": workflow["workflow_id"],
            "workflow_snapshot_id": workflow["snapshot_id"],
            "workflow_revision": final_approval["proposal_revision"],
            "workflow_approval_status": final_approval["approval_status"],
            "workflow_approved_count": metrics_json["workflow_approved_count"],
            "audit_event_count": len(audit_events),
        }
    )


if __name__ == "__main__":
    main()
