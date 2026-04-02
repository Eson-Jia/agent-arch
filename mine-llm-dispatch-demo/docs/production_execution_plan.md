# Demo 到 Production 的开发计划

这份计划不是泛泛路线图，而是基于当前仓库代码做的可执行拆分。目标是把现有多 Agent demo 演进成具备生产骨架的决策系统。

## 目标原则

1. 安全相关判断保持确定性边界
2. 多 Agent 必须共享同一版本快照
3. 所有关键输出必须可追踪、可回放、可降级

## Phase 1：基础骨架

### 目标

- 让多 Agent 基于同一版本状态工作
- 从并列 API 走向标准编排入口
- 让实时状态具备最小持久化能力

### 任务

- 为 `StateStore` 增加持久化文件和 `snapshot_version`
- 为审计事件增加 `trace_id` 和 `snapshot_version`
- 新增 `IncidentResponseOrchestrator`
- 暴露 `/workflows/incident-response` 统一入口
- 补主链测试，验证工作流与重启后状态恢复

### 验收标准

- 工作流接口一次调用即可完成 `triage -> dispatch -> gatekeeper`
- 工作流内部各 Agent 使用同一 `snapshot_version`
- 服务重启后仍能恢复最近遥测、告警和上次建议路线

### 当前状态

- 已完成

## Phase 2：运行治理

### 目标

- 让系统从“能跑”变成“可管”

### 任务

- 引入 `incident_id` / `approval_id` / `proposal_revision`
- 给 ingest 层加幂等键和重复事件处理
- 给 workflow 增加审批状态机
- 补耗时、回退原因、拒绝原因等观测指标
- 把 `gatekeeper` 失败后的二次求解或人工改派流程串起来

### 验收标准

- 每次事件和每次建议都有稳定关联 ID
- 审批、驳回、重提有明确状态转移
- 可以按时间窗口统计 LLM 回退率和 gatekeeper 拒绝率

### 当前状态

- 已完成
- 当前已落地 `incident_id / approval_id / proposal_revision`
- 当前已支持 ingest 幂等、审批、驳回后重提和 `/metrics/summary`

## Phase 3：模型与知识治理

### 目标

- 让 LLM 从“能调用”变成“可运营”

### 任务

- 管理 prompt 版本和 provider 策略
- 为 triage / diagnose / forecast 建离线评测集
- 引入真实 embedding provider 替换 `MockEmbedding`
- 增加 RAG 命中质量与证据覆盖率评估
- 增加模型超时、熔断、限流和降级策略

### 验收标准

- 不同 provider 和 prompt 版本可对比
- RAG 与 LLM 质量可离线评估
- 外部模型故障时系统仍能维持确定性主链

### 当前状态

- 已完成
- 当前已落地 prompt 注册表、provider/strategy 配置、LLM 熔断降级和 embedding provider 抽象
- 当前已支持 `/metrics/summary` 聚合 prompt 使用、LLM 回退和 RAG 命中质量
- 当前已补 `scripts/evaluate_quality.py` 和固定离线评测集

## Phase 4：生产接入

### 目标

- 真正接近矿区现场联动

### 任务

- 将内存态升级到数据库或事件存储
- 对接上游真实遥测/告警总线
- 对接审批、工单、执行下发系统
- 增加历史回放和仿真验证能力

### 验收标准

- 多实例运行状态一致
- 历史事件可重放
- 外部系统可围绕 workflow 接口完成联动

### 当前状态

- 已完成当前仓库内可落地的接入骨架
- 当前已支持 mock 执行适配器、执行日志、`/workflows/{workflow_id}/execute`
- 当前已支持基于审计日志的 `/replay/audit` 历史回放与重演
- 多实例一致性和真实外部总线接入仍需结合目标基础设施继续实现

## 实施顺序建议

1. 先做 Phase 1，把“共享版本状态 + 编排入口 + 持久化骨架”打牢
2. 再做 Phase 2，把审批、幂等、可观测性补起来
3. 然后做 Phase 3，降低模型和知识库不稳定风险
4. 最后做 Phase 4，接入真实生产系统
