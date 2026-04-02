from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent
from app.llm.prompts import get_prompt
from app.models.proposal import (
    AssistantChatResponse,
    WorkflowBrief,
)
from app.observability.metrics import summarize_metrics
from app.storage.workflow_store import WorkflowStore
from app.utils.time import now_ts


class AssistantAgent(BaseAgent):
    agent_name = "assistant_agent_v1"

    def __init__(self, *args: Any, workflow_store: WorkflowStore, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.workflow_store = workflow_store

    def _intent(self, query: str, workflow_id: str | None) -> str:
        normalized = query.lower()
        if workflow_id or any(token in normalized for token in ["workflow", "审批", "工单", "执行", "approval", "工作流"]):
            return "workflow_status"
        if any(token in normalized for token in ["告警", "报警", "alarm", "路障", "封控", "异常"]):
            return "alarm_summary"
        if any(token in normalized for token in ["调度", "派车", "路线", "dispatch", "route", "绕行"]):
            return "dispatch_guidance"
        if any(token in normalized for token in ["指标", "质量", "评估", "metrics", "fallback", "rag", "回退"]):
            return "metrics_summary"
        return "general_support"

    def _workflow_briefs(self, workflow_id: str | None, limit: int) -> list[WorkflowBrief]:
        if workflow_id:
            record = self.workflow_store.get(workflow_id)
            if record is None:
                return []
            records = [record]
        else:
            records = self.workflow_store.list_records(limit=limit)
        return [
            WorkflowBrief(
                workflow_id=record.workflow_id,
                incident_id=record.incident_id,
                approval_status=record.approval_status,
                final_status=record.final_status,
                proposal_revision=record.proposal_revision,
            )
            for record in records
        ]

    def _default_actions(self, intent: str, workflows: list[WorkflowBrief]) -> list[str]:
        if intent == "workflow_status":
            if workflows:
                return [
                    f"查看工作流 {workflows[0].workflow_id} 的审批状态和 proposal_revision",
                    f"如已批准，可执行 /workflows/{workflows[0].workflow_id}/execute",
                ]
            return [
                "先运行 /workflows/incident-response 生成新的工作流",
                "再查看 /metrics/summary 评估当前治理状态",
            ]
        if intent == "alarm_summary":
            return [
                "优先核查最高等级告警和封控路段",
                "如需形成建议方案，运行 /workflows/incident-response",
            ]
        if intent == "dispatch_guidance":
            return [
                "先确认 blocked_segments 和待审批工作流",
                "如需新方案，重新运行 /workflows/incident-response",
            ]
        if intent == "metrics_summary":
            return [
                "查看 llm_fallback_rate、gatekeeper_reject_rate 和 duplicate ingest 统计",
                "结合离线评测脚本确认回归质量",
            ]
        return [
            "可以询问告警、调度、工作流审批或指标质量问题",
            "如需建议链路，直接运行 /workflows/incident-response",
        ]

    def _follow_up_questions(self, intent: str) -> list[str]:
        mapping = {
            "workflow_status": [
                "当前有哪些待审批工作流？",
                "某个 workflow 现在能不能执行？",
            ],
            "alarm_summary": [
                "当前最高优先级告警是什么？",
                "哪些路段被封控了？",
            ],
            "dispatch_guidance": [
                "当前调度最应该避免哪条路线？",
                "如果重新生成方案，会进入审批吗？",
            ],
            "metrics_summary": [
                "LLM 回退率现在是多少？",
                "RAG 命中质量最近怎么样？",
            ],
            "general_support": [
                "当前系统最需要处理的告警是什么？",
                "有哪些待审批工作流？",
            ],
        }
        return mapping[intent]

    def _draft_answer(
        self,
        *,
        intent: str,
        query: str,
        snapshot: dict[str, Any],
        workflows: list[WorkflowBrief],
        metrics: dict[str, Any],
        doc_hits: list[dict[str, Any]],
    ) -> tuple[str, float]:
        alarms = snapshot["alarms"]
        blocked_segments = snapshot["blocked_segments"]
        blocked_text = "、".join(blocked_segments) if blocked_segments else "无"
        if intent == "workflow_status":
            if workflows:
                top = workflows[0]
                answer = (
                    f"当前最相关的工作流是 {top.workflow_id}，incident_id 为 {top.incident_id}，"
                    f"审批状态是 {top.approval_status}，最终 gatekeeper 状态是 {top.final_status}，"
                    f"当前 proposal_revision 为 {top.proposal_revision}。"
                )
                return answer, 0.86
            return "当前没有可引用的工作流记录；如果需要正式建议链路，先运行 incident workflow。", 0.72
        if intent == "alarm_summary":
            if alarms:
                top_alarm = alarms[0]
                answer = (
                    f"当前窗口内有 {snapshot['summary']['active_alarm_count']} 条活跃告警，"
                    f"最高优先参考 {top_alarm['alarm_id']}，类别为 {top_alarm['category']}，"
                    f"影响路段 {top_alarm['location']['road_segment']}；当前封控路段有 {blocked_text}。"
                )
                return answer, 0.84
            return "当前窗口内没有活跃告警，系统更适合关注审批中的工作流和质量指标。", 0.76
        if intent == "dispatch_guidance":
            answer = (
                f"当前可用车辆 {snapshot['summary']['available_vehicle_count']} 台，"
                f"封控路段 {blocked_text}。"
                f"最近 gatekeeper 拒绝率为 {metrics['gatekeeper_reject_rate']:.2%}。"
                "如需形成正式调度建议，应通过 incident workflow 生成并进入审批。"
            )
            return answer, 0.8
        if intent == "metrics_summary":
            answer = (
                f"当前 LLM 回退率为 {metrics['llm_fallback_rate']:.2%}，"
                f"gatekeeper 拒绝率为 {metrics['gatekeeper_reject_rate']:.2%}，"
                f"RAG 平均 top score 为 {metrics['rag_avg_top_score']:.4f}，"
                f"最近 prompt 使用统计为 {metrics['prompt_usage_counts']}。"
            )
            return answer, 0.82
        doc_hint = doc_hits[0]["doc_id"] if doc_hits else "无"
        answer = (
            f"当前系统快照版本是 {snapshot['snapshot_version']}，"
            f"活跃告警 {snapshot['summary']['active_alarm_count']} 条，"
            f"待审批工作流 {metrics['workflow_pending_approval_count']} 个。"
            f"如果你想要更具体的帮助，可以继续询问告警、调度、审批或指标；当前最相关的知识文档是 {doc_hint}。"
        )
        return answer, 0.75

    def run(self, input_data: dict[str, Any] | None = None) -> AssistantChatResponse:
        payload = input_data or {}
        query = str(payload.get("query", "")).strip()
        workflow_id = payload.get("workflow_id")
        since_minutes = int(payload.get("since_minutes", 30))
        workflow_limit = int(payload.get("workflow_limit", 5))
        history = payload.get("history", [])

        snapshot = self._resolve_snapshot(payload, since_minutes=since_minutes)
        doc_hits, doc_evidence = self._retrieve(query or "系统 对话 助手 告警 工作流 调度 指标")
        workflows = self._workflow_briefs(workflow_id, workflow_limit)
        metrics = summarize_metrics(
            self.audit_store.list_events(limit=1000),
            self.workflow_store.list_records(limit=200),
        )
        intent = self._intent(query, workflow_id)
        answer, confidence = self._draft_answer(
            intent=intent,
            query=query,
            snapshot=snapshot,
            workflows=workflows,
            metrics=metrics,
            doc_hits=doc_hits,
        )
        draft_response = AssistantChatResponse(
            ts=now_ts(self.timezone_name),
            intent=intent,
            answer=answer,
            suggested_actions=self._default_actions(intent, workflows),
            follow_up_questions=self._follow_up_questions(intent),
            related_workflows=workflows,
            confidence=confidence,
            evidence=[
                f"STATE-{snapshot['snapshot_id']}",
                *(alarm["alarm_id"] for alarm in snapshot["alarms"][:3]),
                *(workflow.workflow_id for workflow in workflows),
                *doc_evidence,
            ],
        )

        prompt = get_prompt("assistant_chat")
        llm_response = self._llm_refine(
            AssistantChatResponse,
            system_prompt=prompt.system_prompt,
            prompt_context={
                "query": query,
                "history": history,
                "snapshot_summary": snapshot["summary"],
                "blocked_segments": snapshot["blocked_segments"],
                "workflows": [workflow.model_dump(mode="json") for workflow in workflows],
                "metrics": metrics,
                "sop_hits": doc_hits,
                "draft_response": draft_response.model_dump(mode="json"),
            },
        )
        response = llm_response or draft_response
        response.evidence = self._merge_evidence(response.evidence, draft_response.evidence)
        self._audit(
            response.model_dump(mode="json"),
            response.evidence,
            trace_id=self._trace_id(payload),
            snapshot_version=snapshot["snapshot_version"],
            meta={
                **self._rag_meta(),
                "intent": response.intent,
                "llm_status": self._last_llm_status,
                "llm_provider": self.llm_client.provider,
                "prompt_id": prompt.prompt_id,
                "prompt_version": prompt.version,
            },
        )
        return response
