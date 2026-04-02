from __future__ import annotations

from datetime import datetime
from typing import Any

from app.agents.base import BaseAgent
from app.llm.prompts import get_prompt
from app.models.proposal import IncidentSummary, TriageAction, TriageResponse, WorkOrderDraft
from app.utils.time import now_ts


class TriageAgent(BaseAgent):
    agent_name = "triage_agent_v1"

    def _dedupe(self, alarms: list[dict[str, Any]]) -> list[dict[str, Any]]:
        deduped: list[dict[str, Any]] = []
        latest_by_key: dict[str, datetime] = {}
        for alarm in sorted(alarms, key=lambda item: item["ts"], reverse=True):
            key = f"{alarm['category']}::{alarm['location']['road_segment']}"
            ts = datetime.fromisoformat(alarm["ts"])
            if key not in latest_by_key:
                latest_by_key[key] = ts
                deduped.append(alarm)
                continue
            delta = latest_by_key[key] - ts
            if delta.total_seconds() > 120:
                deduped.append(alarm)
        return deduped[:5]

    def run(self, input_data: dict[str, Any] | None = None) -> TriageResponse:
        since_minutes = (input_data or {}).get("since_minutes", 10)
        snapshot = self._resolve_snapshot(input_data, since_minutes=since_minutes)
        alarms = self._dedupe(snapshot["alarms"])
        doc_hits, doc_evidence = self._retrieve("告警 分诊 红色 预警 绕行 证据链")
        incidents: list[IncidentSummary] = []
        actions: list[TriageAction] = []
        evidence = [alarm["alarm_id"] for alarm in alarms] + doc_evidence
        for alarm in alarms:
            blocked = "封控" if alarm["impact_zone"]["blocked"] else "监控"
            incidents.append(
                IncidentSummary(
                    alarm_id=alarm["alarm_id"],
                    level=alarm["level"],
                    why=f"{alarm['category']} on {alarm['location']['road_segment']}",
                    impact=f"{blocked}路段 {alarm['location']['road_segment']}，建议检查绕行",
                )
            )
            owner = "安全员" if alarm["level"] in {"RED", "ORANGE"} else "调度员"
            deadline = 5 if alarm["level"] == "RED" else 10 if alarm["level"] == "ORANGE" else 20
            actions.append(
                TriageAction(
                    action=f"核查 {alarm['location']['road_segment']} 并更新闭环状态",
                    owner=owner,
                    deadline_min=deadline,
                )
            )
        if not incidents:
            incidents.append(
                IncidentSummary(
                    alarm_id="NONE",
                    level="BLUE",
                    why="No active alarms in the selected window",
                    impact="继续监控当前班次态势",
                )
            )
            actions.append(TriageAction(action="保持当前调度节奏并持续观察", owner="调度员", deadline_min=30))
        work_order = WorkOrderDraft(
            incident_owner=actions[0].owner,
            response_steps=[
                "值班查看并确认告警来源",
                "根据预警等级更新处置动作",
                "补充证据并提交核查反馈",
            ],
            follow_up=[hit["doc_id"] for hit in doc_hits],
        )
        draft_response = TriageResponse(
            ts=now_ts(self.timezone_name),
            top_incidents=incidents,
            triage_actions=actions,
            work_order_draft=work_order,
            requires_human_confirmation=any(item.level in {"RED", "ORANGE"} for item in incidents),
            confidence=0.83 if alarms else 0.72,
            evidence=evidence or doc_evidence,
        )
        prompt = get_prompt("triage_refine")
        llm_response = self._llm_refine(
            TriageResponse,
            system_prompt=prompt.system_prompt,
            prompt_context={
                "snapshot_summary": snapshot["summary"],
                "alarms": alarms,
                "sop_hits": doc_hits,
                "draft_response": draft_response.model_dump(mode="json"),
            },
        )
        response = llm_response or draft_response
        response.evidence = self._merge_evidence(response.evidence, draft_response.evidence)
        self._audit(
            response.model_dump(mode="json"),
            response.evidence,
            trace_id=self._trace_id(input_data),
            snapshot_version=snapshot["snapshot_version"],
            meta={
                "llm_status": self._last_llm_status,
                "llm_provider": self.llm_client.provider,
                "prompt_id": prompt.prompt_id,
                "prompt_version": prompt.version,
            },
        )
        return response
