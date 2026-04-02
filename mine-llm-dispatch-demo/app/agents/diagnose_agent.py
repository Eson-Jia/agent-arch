from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent
from app.models.proposal import DiagnoseResponse, RcaHypothesis
from app.utils.time import now_ts


class DiagnoseAgent(BaseAgent):
    agent_name = "diagnose_agent_v1"

    def run(self, input_data: dict[str, Any] | None = None) -> DiagnoseResponse:
        snapshot = self._snapshot()
        _doc_hits, doc_evidence = self._retrieve("异常 诊断 通信 地图 预警 回退")
        hypotheses: list[RcaHypothesis] = []
        evidence: list[str] = []
        if snapshot["alarms"]:
            alarm = snapshot["alarms"][0]
            evidence.append(alarm["alarm_id"])
            hypotheses.append(
                RcaHypothesis(
                    hypothesis=f"{alarm['category']} 导致路段 {alarm['location']['road_segment']} 运输能力下降",
                    supporting_evidence=[alarm["alarm_id"]],
                    missing_evidence=["现场复核结果", "处置完成时间"],
                    next_check="确认障碍清除时间并同步地图封控状态",
                )
            )
        high_loss = [
            vehicle for vehicle in snapshot["vehicles"] if vehicle["comms"]["loss_pct_5s"] > 3 or vehicle["comms"]["rssi_dbm"] < -90
        ]
        if high_loss:
            evidence.extend(vehicle["truck_id"] for vehicle in high_loss)
            hypotheses.append(
                RcaHypothesis(
                    hypothesis="通信抖动放大了队列判断误差",
                    supporting_evidence=[vehicle["truck_id"] for vehicle in high_loss],
                    missing_evidence=["边缘网络链路质量", "基站切换日志"],
                    next_check="拉取最近 10 分钟网络链路日志并比对调度时间点",
                )
            )
        map_versions = {vehicle["pos"]["map_ver"] for vehicle in snapshot["vehicles"]}
        if len(map_versions) > 1:
            hypotheses.append(
                RcaHypothesis(
                    hypothesis="地图版本不一致影响了路权判断",
                    supporting_evidence=list(map_versions),
                    missing_evidence=["地图发布记录", "车端地图同步日志"],
                    next_check="核对地图发布记录并强制同步最新版本",
                )
            )
        if not hypotheses:
            hypotheses.append(
                RcaHypothesis(
                    hypothesis="未发现明确异常，当前以常规波动处理",
                    supporting_evidence=[],
                    missing_evidence=["更多班次级生产数据"],
                    next_check="继续观测 30 分钟并采样排队变化",
                )
            )
        response = DiagnoseResponse(
            ts=now_ts(self.timezone_name),
            rca_tree=hypotheses,
            workaround=[
                "优先切换到绕行路线并保持建议态输出",
                "若通信异常持续，降级为规则+人工确认模式",
            ],
            rollback_plan=[
                "停止使用最新调度建议",
                "回退到既有 FMS 基线策略",
                "保留审计记录和输入快照以便复盘",
            ],
            confidence=0.78 if snapshot["alarms"] else 0.65,
            evidence=[*evidence, *doc_evidence],
        )
        self._audit(response.model_dump(mode="json"), response.evidence)
        return response
