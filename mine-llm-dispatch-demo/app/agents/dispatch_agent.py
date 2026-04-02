from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent
from app.models.proposal import (
    DispatchExpectedImpact,
    DispatchProposal,
    ProposalExpectation,
    TaskRef,
    TruckProposal,
)
from app.optim.solver import DispatchSolver
from app.utils.ids import generate_id
from app.utils.time import now_ts


class DispatchAgent(BaseAgent):
    agent_name = "dispatch_agent_v1"

    def __init__(self, *args: Any, solver: DispatchSolver, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.solver = solver

    def run(self, input_data: dict[str, Any] | None = None) -> DispatchProposal:
        snapshot = self._resolve_snapshot(input_data)
        assignments = self.solver.solve(snapshot)
        _doc_hits, doc_evidence = self._retrieve("调度 策略 路权 预警 绕行")
        ts = now_ts(self.timezone_name)
        items: list[TruckProposal] = []
        for assignment in assignments:
            items.append(
                TruckProposal(
                    truck_id=assignment["truck_id"],
                    next_task=TaskRef(load=assignment["load"], dump=assignment["dump"], route=assignment["route"]),
                    constraints_checked=assignment["constraints_checked"],
                    expected=ProposalExpectation(
                        eta_min=assignment["eta_min"],
                        queue_wait_min=assignment["queue_wait_min"],
                    ),
                    risk_notes=assignment["risk_notes"],
                )
            )
        blocked_count = len(snapshot["blocked_segments"])
        proposal = DispatchProposal(
            proposal_id=generate_id("DSP", ts),
            generated_by=self.agent_name,
            ts=ts,
            dispatch_cycle_seconds=60 if blocked_count == 0 else 120,
            proposals=items,
            expected_impact=DispatchExpectedImpact(
                throughput_delta_pct=round(max(-3.5, 1.8 - blocked_count * 1.5), 2),
                empty_distance_delta_pct=round(-4.0 - len(items) * 0.8, 2),
                queue_time_delta_pct=round(-10.0 - blocked_count * 3.0, 2),
            ),
            requires_human_confirmation=True,
            evidence=[
                *(alarm["alarm_id"] for alarm in snapshot["alarms"]),
                *doc_evidence,
                f"STATE-SUMMARY-{snapshot['window_minutes']}min",
            ],
        )
        self.state_store.remember_suggestion(proposal)
        self._audit(
            proposal.model_dump(mode="json"),
            proposal.evidence,
            trace_id=self._trace_id(input_data),
            snapshot_version=snapshot["snapshot_version"],
            meta={**self._rag_meta(), "engine": "ortools"},
        )
        return proposal
