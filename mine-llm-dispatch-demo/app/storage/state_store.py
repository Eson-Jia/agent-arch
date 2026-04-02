from __future__ import annotations

from collections import deque
from copy import deepcopy
from datetime import timedelta
import json
from pathlib import Path
from threading import RLock
from typing import Any

from app.models.alarm import SafetyAlarmEvent
from app.models.proposal import DispatchProposal
from app.models.telemetry import VehicleTelemetry
from app.utils.time import now_ts


LOAD_SITES: dict[str, dict[str, float | int]] = {
    "L1": {"x": 980.0, "y": 820.0, "capacity": 2},
    "L2": {"x": 1010.0, "y": 850.0, "capacity": 2},
    "L3": {"x": 1045.0, "y": 900.0, "capacity": 3},
}

DUMP_SITES: dict[str, dict[str, float | int]] = {
    "D1": {"x": 1180.0, "y": 960.0, "capacity": 2},
    "D2": {"x": 1265.0, "y": 1025.0, "capacity": 3},
}

TASK_CATALOG: list[dict[str, Any]] = [
    {
        "task_id": "TASK-L1-D1-R5",
        "load": "L1",
        "dump": "D1",
        "route": "R5",
        "route_segments": ["R5"],
        "route_distance_km": 2.2,
        "queue_wait_min": 2.0,
        "capacity": 2,
    },
    {
        "task_id": "TASK-L2-D2-R7",
        "load": "L2",
        "dump": "D2",
        "route": "R7",
        "route_segments": ["R7"],
        "route_distance_km": 2.7,
        "queue_wait_min": 1.8,
        "capacity": 1,
    },
    {
        "task_id": "TASK-L3-D2-R9",
        "load": "L3",
        "dump": "D2",
        "route": "R9",
        "route_segments": ["R9"],
        "route_distance_km": 2.9,
        "queue_wait_min": 1.2,
        "capacity": 3,
    },
    {
        "task_id": "TASK-L2-D1-R11",
        "load": "L2",
        "dump": "D1",
        "route": "R11",
        "route_segments": ["R11"],
        "route_distance_km": 3.0,
        "queue_wait_min": 1.5,
        "capacity": 2,
    },
]

DEFAULT_SHIFT_PLAN: dict[str, Any] = {
    "target_throughput_tph": 820,
    "priority_loads": ["L3", "L2"],
    "priority_dumps": ["D2", "D1"],
}


class StateStore:
    def __init__(
        self,
        timezone_name: str = "Asia/Shanghai",
        window_minutes: int = 30,
        path: Path | None = None,
    ) -> None:
        self.timezone_name = timezone_name
        self.window_minutes = window_minutes
        self.path = path
        self._lock = RLock()
        self._vehicles: dict[str, VehicleTelemetry] = {}
        self._alarms: deque[SafetyAlarmEvent] = deque(maxlen=500)
        self._last_suggested_routes: dict[str, str] = {}
        self._processed_event_keys: deque[str] = deque(maxlen=5000)
        self._processed_event_index: set[str] = set()
        self._state_version = 0
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._load_state()

    def _load_state(self) -> None:
        if self.path is None or not self.path.exists():
            return
        raw = self.path.read_text(encoding="utf-8").strip()
        if not raw:
            return
        payload = json.loads(raw)
        self._state_version = int(payload.get("state_version", 0))
        self._vehicles = {
            item["truck_id"]: VehicleTelemetry.model_validate(item)
            for item in payload.get("vehicles", [])
        }
        self._alarms = deque(
            (SafetyAlarmEvent.model_validate(item) for item in payload.get("alarms", [])),
            maxlen=500,
        )
        self._last_suggested_routes = {
            str(key): str(value)
            for key, value in payload.get("last_suggested_routes", {}).items()
        }
        self._processed_event_keys = deque(
            (str(item) for item in payload.get("processed_event_keys", [])),
            maxlen=5000,
        )
        self._processed_event_index = set(self._processed_event_keys)

    def _persist_locked(self) -> None:
        if self.path is None:
            return
        payload = {
            "state_version": self._state_version,
            "vehicles": [vehicle.model_dump(mode="json") for vehicle in self._vehicles.values()],
            "alarms": [alarm.model_dump(mode="json") for alarm in self._alarms],
            "last_suggested_routes": deepcopy(self._last_suggested_routes),
            "processed_event_keys": list(self._processed_event_keys),
        }
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _touch_locked(self) -> None:
        self._state_version += 1
        self._persist_locked()

    def reset(self) -> None:
        with self._lock:
            self._vehicles.clear()
            self._alarms.clear()
            self._last_suggested_routes.clear()
            self._processed_event_keys.clear()
            self._processed_event_index.clear()
            self._state_version = 0
            self._persist_locked()

    def _mark_event_processed_locked(self, event_key: str) -> bool:
        if event_key in self._processed_event_index:
            return False
        if len(self._processed_event_keys) == self._processed_event_keys.maxlen:
            removed = self._processed_event_keys.popleft()
            self._processed_event_index.discard(removed)
        self._processed_event_keys.append(event_key)
        self._processed_event_index.add(event_key)
        return True

    def _telemetry_event_key(self, telemetry: VehicleTelemetry) -> str:
        return telemetry.source_event_id or f"telemetry::{telemetry.truck_id}::{telemetry.ts.isoformat()}"

    def _alarm_event_key(self, alarm: SafetyAlarmEvent) -> str:
        return alarm.source_event_id or f"alarm::{alarm.alarm_id}"

    def upsert_telemetry(self, telemetry: VehicleTelemetry) -> tuple[bool, str]:
        event_key = self._telemetry_event_key(telemetry)
        with self._lock:
            if not self._mark_event_processed_locked(event_key):
                return False, event_key
            self._vehicles[telemetry.truck_id] = telemetry
            self._touch_locked()
        return True, event_key

    def add_alarm(self, alarm: SafetyAlarmEvent) -> tuple[bool, str]:
        event_key = self._alarm_event_key(alarm)
        with self._lock:
            if not self._mark_event_processed_locked(event_key):
                return False, event_key
            self._alarms.append(alarm)
            self._touch_locked()
        return True, event_key

    def remember_suggestion(self, proposal: DispatchProposal) -> None:
        with self._lock:
            for item in proposal.proposals:
                self._last_suggested_routes[item.truck_id] = item.next_task.route
            self._touch_locked()

    def last_suggested_route(self, truck_id: str) -> str | None:
        with self._lock:
            return self._last_suggested_routes.get(truck_id)

    def recent_alarms(self, since_minutes: int | None = None) -> list[SafetyAlarmEvent]:
        with self._lock:
            alarms = list(self._alarms)
        if not alarms:
            return []
        reference_ts = max(alarm.ts for alarm in alarms)
        cutoff = reference_ts - timedelta(minutes=since_minutes or self.window_minutes)
        return [alarm for alarm in alarms if alarm.ts >= cutoff]

    def active_trucks(self) -> list[VehicleTelemetry]:
        with self._lock:
            return list(self._vehicles.values())

    def snapshot(self, since_minutes: int | None = None) -> dict[str, Any]:
        window = since_minutes or self.window_minutes
        with self._lock:
            state_version = self._state_version
            last_suggested_routes = deepcopy(self._last_suggested_routes)
        alarms = self.recent_alarms(window)
        vehicles = self.active_trucks()
        blocked_segments = sorted(
            {
                alarm.location.road_segment
                for alarm in alarms
                if alarm.impact_zone.blocked or alarm.level == "RED"
            }
        )
        latest_map_ver = max((vehicle.pos.map_ver for vehicle in vehicles), default="map_2026_04_01")
        available_trucks = [
            vehicle
            for vehicle in vehicles
            if vehicle.motion.mode == "AUTO" and vehicle.health.fault_code is None
        ]
        queue_factor = max(0.0, min(1.0, len(alarms) * 0.08))
        queue_estimates = {
            "L1": round(1.2 + queue_factor, 2),
            "L2": round(1.5 + queue_factor, 2),
            "L3": round(0.8 + queue_factor, 2),
            "D1": round(1.0 + queue_factor, 2),
            "D2": round(1.4 + queue_factor, 2),
        }
        road_status = {
            "blocked_segments": blocked_segments,
            "active_levels": {
                alarm.location.road_segment: alarm.level for alarm in alarms
            },
        }
        return {
            "snapshot_id": f"SNP-{state_version:06d}",
            "snapshot_version": state_version,
            "ts": now_ts(self.timezone_name),
            "window_minutes": window,
            "map_ver": latest_map_ver,
            "plan": deepcopy(DEFAULT_SHIFT_PLAN),
            "vehicles": [vehicle.model_dump(mode="json") for vehicle in vehicles],
            "available_trucks": [vehicle.model_dump(mode="json") for vehicle in available_trucks],
            "alarms": [alarm.model_dump(mode="json") for alarm in alarms],
            "blocked_segments": blocked_segments,
            "queue_estimates": queue_estimates,
            "road_status": road_status,
            "load_sites": deepcopy(LOAD_SITES),
            "dump_sites": deepcopy(DUMP_SITES),
            "task_catalog": deepcopy(TASK_CATALOG),
            "last_suggested_routes": last_suggested_routes,
            "summary": {
                "active_vehicle_count": len(vehicles),
                "available_vehicle_count": len(available_trucks),
                "active_alarm_count": len(alarms),
                "blocked_segment_count": len(blocked_segments),
            },
        }
