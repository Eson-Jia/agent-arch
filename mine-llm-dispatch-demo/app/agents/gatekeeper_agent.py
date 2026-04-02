from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent
from app.models.proposal import DispatchProposal, GatekeeperResponse
from app.rules.rule_engine import RuleEngine


class GatekeeperAgent(BaseAgent):
    agent_name = "gatekeeper_agent_v1"

    def __init__(self, *args: Any, rule_engine: RuleEngine, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.rule_engine = rule_engine

    def run(self, input_data: dict[str, Any] | None = None) -> GatekeeperResponse:
        if not input_data or "proposal" not in input_data:
            raise ValueError("proposal is required")
        proposal = DispatchProposal.model_validate(input_data["proposal"])
        operator_role = input_data.get("operator_role", "dispatcher")
        snapshot = self._resolve_snapshot(input_data)
        alarms = snapshot["alarms"]
        response = self.rule_engine.validate_proposal(proposal, alarms, operator_role=operator_role)
        response.evidence = [*response.evidence, *(alarm["alarm_id"] for alarm in alarms)]
        self._audit(
            response.model_dump(mode="json"),
            response.evidence,
            trace_id=self._trace_id(input_data),
            snapshot_version=snapshot["snapshot_version"],
            meta={"rule_status": response.status},
        )
        return response
