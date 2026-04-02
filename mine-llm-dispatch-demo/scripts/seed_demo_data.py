from __future__ import annotations

import os

import httpx


BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000")


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

    with httpx.Client(base_url=BASE_URL, timeout=10.0) as client:
        for payload in telemetry_payloads:
            client.post("/ingest/telemetry", json=payload).raise_for_status()
        client.post("/ingest/alarm", json=alarm_payload).raise_for_status()
        dispatch_resp = client.post("/agents/dispatch", json={})
        dispatch_resp.raise_for_status()
        dispatch = dispatch_resp.json()
        gatekeeper_resp = client.post(
            "/agents/gatekeeper",
            json={"proposal": dispatch, "operator_role": "dispatcher"},
        )
        gatekeeper_resp.raise_for_status()
        gatekeeper = gatekeeper_resp.json()
    print({"dispatch": dispatch, "gatekeeper": gatekeeper})


if __name__ == "__main__":
    main()
