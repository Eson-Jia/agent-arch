from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent
from app.models.proposal import ForecastPoint, ForecastResponse, ScenarioCompare
from app.utils.time import now_ts


class ForecastAgent(BaseAgent):
    agent_name = "forecast_agent_v1"

    def run(self, input_data: dict[str, Any] | None = None) -> ForecastResponse:
        horizons = (input_data or {}).get("horizons", [30, 60])
        snapshot = self._snapshot()
        _doc_hits, doc_evidence = self._retrieve("预测 拥堵 调度 周期 绕行")
        blocked_count = len(snapshot["blocked_segments"])
        available = snapshot["summary"]["available_vehicle_count"]
        target_tph = snapshot["plan"]["target_throughput_tph"]
        forecast: list[ForecastPoint] = []
        for horizon in horizons:
            throughput = max(200.0, target_tph - blocked_count * 55 - horizon * 0.8 + available * 12)
            queue_wait = max(1.0, 2.0 + blocked_count * 0.9 + horizon / 60)
            congestion = min(1.0, 0.25 + blocked_count * 0.15 + queue_wait / 10)
            forecast.append(
                ForecastPoint(
                    horizon_min=horizon,
                    throughput_tph=round(throughput, 2),
                    queue_wait_min=round(queue_wait, 2),
                    congestion_index=round(congestion, 2),
                )
            )
        draft_response = ForecastResponse(
            ts=now_ts(self.timezone_name),
            forecast=forecast,
            what_if=[
                ScenarioCompare(
                    scenario="baseline_keep_cycle",
                    throughput_delta_pct=-2.1 if blocked_count else 0.8,
                    queue_time_delta_pct=3.5 if blocked_count else -1.0,
                    note="维持现有调度周期，对异常路段较保守",
                ),
                ScenarioCompare(
                    scenario="reroute_with_longer_cycle",
                    throughput_delta_pct=1.4 if blocked_count else 1.0,
                    queue_time_delta_pct=-8.3 if blocked_count else -4.2,
                    note="通过绕行和更长调度周期减少高频改派",
                ),
            ],
            confidence=0.74,
            evidence=[*doc_evidence, *(alarm["alarm_id"] for alarm in snapshot["alarms"])],
        )
        llm_response = self._llm_refine(
            ForecastResponse,
            system_prompt=(
                "You are a mine dispatch forecasting assistant. "
                "Refine the forecast draft using only the provided state snapshot and SOP evidence. "
                "Keep numeric projections plausible and preserve structured JSON output."
            ),
            prompt_context={
                "horizons": horizons,
                "snapshot_summary": snapshot["summary"],
                "blocked_segments": snapshot["blocked_segments"],
                "queue_estimates": snapshot["queue_estimates"],
                "draft_response": draft_response.model_dump(mode="json"),
            },
        )
        response = llm_response or draft_response
        response.evidence = self._merge_evidence(response.evidence, draft_response.evidence)
        self._audit(response.model_dump(mode="json"), response.evidence)
        return response
