from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from app.models.alarm import SafetyAlarmEvent
from app.models.proposal import DispatchProposal, GatekeeperResponse


class RuleEngine:
    def __init__(self, rule_path: Path) -> None:
        self.rule_path = rule_path
        self.rules = yaml.safe_load(rule_path.read_text(encoding="utf-8"))

    @property
    def no_go_segments(self) -> set[str]:
        return set(self.rules.get("no_go_segments", []))

    def route_segments(self, route: str) -> list[str]:
        return list(self.rules.get("route_segments", {}).get(route, [route]))

    def permissions_for(self, role: str) -> dict[str, Any]:
        permissions = self.rules.get("permissions", {})
        return permissions.get(role, permissions.get("guest", {}))

    def is_route_allowed(self, route: str, alarms: list[dict[str, Any]] | list[SafetyAlarmEvent]) -> tuple[bool, list[str]]:
        violations: list[str] = []
        segments = set(self.route_segments(route))
        if route == "HOLD":
            return True, violations
        intersect_no_go = segments & self.no_go_segments
        if intersect_no_go:
            violations.append(f"Route {route} enters no-go segments: {sorted(intersect_no_go)}")
        for alarm in alarms:
            if isinstance(alarm, SafetyAlarmEvent):
                road_segment = alarm.location.road_segment
                blocked = alarm.impact_zone.blocked
                level = alarm.level
            else:
                road_segment = alarm["location"]["road_segment"]
                blocked = alarm["impact_zone"]["blocked"]
                level = alarm["level"]
            if road_segment in segments and (blocked or level == "RED"):
                violations.append(f"Route {route} crosses blocked segment {road_segment} ({level})")
        return (len(violations) == 0), violations

    def validate_proposal(
        self,
        proposal: DispatchProposal,
        alarms: list[dict[str, Any]] | list[SafetyAlarmEvent],
        operator_role: str = "dispatcher",
    ) -> GatekeeperResponse:
        violations: list[str] = []
        required_changes: list[str] = []
        permissions = self.permissions_for(operator_role)
        if not permissions.get("can_submit_proposal", False):
            violations.append(f"Role {operator_role} is not allowed to submit proposals")
        if permissions.get("requires_human_confirmation", True) and not proposal.requires_human_confirmation:
            violations.append("Human confirmation is mandatory for this role")
        for item in proposal.proposals:
            allowed, route_violations = self.is_route_allowed(item.next_task.route, alarms)
            if not allowed:
                violations.extend(route_violations)
                required_changes.append(f"Truck {item.truck_id} must avoid route {item.next_task.route}")
        status = "PASS" if not violations else "FAIL"
        evidence = [f"RULE-{self.rule_path.name}#no_go_segments", f"RULE-{self.rule_path.name}#permissions"]
        return GatekeeperResponse(
            status=status,
            violations=sorted(set(violations)),
            required_changes=sorted(set(required_changes)),
            evidence=evidence,
        )
