# 项目概念说明

这份文档不重复 README 的启动说明，而是专门解释这个工程里最值得先理解的概念。建议阅读顺序是：

1. 先看“整体链路”和“组合根”
2. 再看“状态快照”“确定性边界”“结构化输出”
3. 最后看“RAG”“求解器”“审计”“测试”

## 1. 整体链路

### 概念

这个项目不是“一个大模型接口”，而是一条由多个明确职责组件串起来的决策链：

```text
HTTP 请求
  -> FastAPI 路由
  -> StateStore / VectorStore / AuditStore
  -> Agent
     -> 规则 / 检索 / 求解 / 可选 LLM 润色
  -> Pydantic 校验
  -> 响应与审计落盘
```

### 为什么重要

理解整体链路后，你就不会把所有逻辑都归因到 LLM。这个工程真正稳定的部分主要来自状态管理、规则校验、求解器和结构化模型，而不是提示词。

### 代码落点

- `app/main.py`
- `app/agents/`
- `app/storage/`
- `app/models/proposal.py`

### 理解要点

- `ingest/*` 路由负责写状态，不负责做决策。
- `agents/*` 路由负责读取状态并生成建议或结论。
- 审计在每次 Agent 输出后落盘，方便追责和回放。

## 2. 组合根

### 概念

组合根可以理解为“所有依赖在什么地方被创建并连接起来”。本项目的组合根是 `build_services()`。

### 为什么重要

如果不知道依赖在哪里组装，就很难改 provider、换存储、替换规则文件，或者为测试注入假实现。

### 代码落点

- `app/main.py`

### 理解要点

- `build_services()` 创建 `StateStore`、`AuditStore`、`VectorStore`、`LLMClient`、`RuleEngine`、`DispatchSolver` 和所有 Agent。
- `lifespan()` 在服务启动时完成日志配置、知识库入库和 `app.state.services` 挂载。
- 这意味着大部分跨模块依赖关系，都应该先从 `app/main.py` 顺藤摸瓜。

## 3. 状态快照

### 概念

`snapshot` 是这个工程的核心中间层。它把零散的遥测、告警、路况和班次上下文聚合成一个“当前可决策视图”。

### 为什么重要

如果没有统一快照，每个 Agent 都会各自拼装输入，结果会不一致，也难以复现。现在的做法是先把“当前世界状态”标准化，再让不同 Agent 使用同一份上下文。

### 代码落点

- `app/storage/state_store.py`

### 理解要点

- `StateStore` 保存最近的车辆遥测、告警和上一次建议路线。
- `snapshot()` 会计算：
  - 活跃车辆和可用车辆
  - 最近窗口内告警
  - 封控路段
  - 排队估计
  - 任务目录
  - 调度摘要
- 调度、分诊、诊断、预测都是围绕这份快照展开，而不是各自直接读原始事件。

## 4. 存储分层

### 概念

项目里有三类存储，它们不是一回事：

- `StateStore`：保存当前运行态
- `VectorStore`：保存知识库向量索引
- `AuditStore`：保存可追溯输出记录

### 为什么重要

很多工程一开始容易把“当前状态”“知识检索”“历史记录”混在一起。这个项目故意把三类职责拆开，目的是让实时态、知识态、审计态分别演进。

### 代码落点

- `app/storage/state_store.py`
- `app/storage/vector_store.py`
- `app/storage/audit_store.py`

### 理解要点

- `StateStore` 是内存态，面向实时决策。
- `VectorStore` 是 Milvus 持久化索引，面向 SOP 检索。
- `AuditStore` 是 JSONL 事件流，面向追溯和回放。

## 5. 确定性核心与 LLM 增强边界

### 概念

这个工程不是“让 LLM 直接拍脑袋调度”，而是把 LLM 放在可控边界内，只做解释增强或结构化润色。

### 为什么重要

矿区调度是高约束场景。路线可走不可走、权限是否允许、方案是否可行，必须由确定性逻辑兜底。LLM 最适合补充表达、归纳和工单组织，不适合替代硬约束判断。

### 代码落点

- `app/agents/triage_agent.py`
- `app/agents/dispatch_agent.py`
- `app/agents/gatekeeper_agent.py`
- `app/llm/client.py`

### 理解要点

- `triage`、`diagnose`、`forecast`：先本地生成草稿，再可选让 LLM 润色。
- `dispatch`：始终由 `DispatchSolver` 给出可行方案。
- `gatekeeper`：始终由 `RuleEngine` 做硬校验。
- 如果真实模型不可用，系统自动回退到本地逻辑，不影响接口可用性。

## 6. 结构化输出

### 概念

LLM 在这里不是直接返回自由文本，而是必须返回能通过 Pydantic 校验的 JSON。

### 为什么重要

只有结构化输出，后面的接口、审计、校验、前端展示才有稳定契约。否则一旦模型改写措辞，整个系统就会变脆。

### 代码落点

- `app/agents/base.py`
- `app/models/proposal.py`

### 理解要点

- `BaseAgent._llm_refine()` 会把目标模型的 JSON Schema 发给 LLM。
- 返回值先走 `response_model.model_validate(...)`。
- 校验失败时直接丢弃模型结果，回退到本地草稿。
- `proposal.py` 里的 Pydantic 模型就是系统对外的数据契约。

## 7. Agent 基类

### 概念

`BaseAgent` 不是业务逻辑本身，而是把所有 Agent 共用的能力收口。

### 为什么重要

这样可以避免每个 Agent 重复写“取快照、检索知识、写审计、调用 LLM、合并证据”这些模板代码。

### 代码落点

- `app/agents/base.py`

### 理解要点

- `_snapshot()` 统一拿状态快照
- `_retrieve()` 统一做 RAG 检索
- `_audit()` 统一写审计事件
- `_llm_refine()` 统一做结构化模型调用
- `_merge_evidence()` 统一拼接证据链

你新增 Agent 时，通常应该先考虑能不能复用这几个基类能力，而不是单独再造一套流程。

## 8. RAG

### 概念

这里的 RAG 不是训练模型，而是把 SOP、调度策略、地图规则切块后入库，在推理时取回最相关片段作为证据。

### 为什么重要

分诊和诊断类任务需要引用作业规程、绕行策略和红色告警 SOP。如果完全靠模型记忆，不可控也不稳定。RAG 的价值是把“依据”显式拿回来。

### 代码落点

- `app/rag/ingest.py`
- `app/rag/retrieve.py`
- `app/storage/vector_store.py`
- `docs/knowledge_base/`

### 理解要点

- 启动时会把 `docs/knowledge_base/*.md` 切块入库。
- 当前向量化是本地哈希 embedding，目标是本地可跑，不依赖外部 embedding 服务。
- 检索结果不仅给 LLM 看，也会作为 `evidence` 留在响应和审计里。

## 9. 向量库与本地 Embedding

### 概念

当前向量库是 Milvus，但 embedding 不是外部模型，而是本地哈希 embedding。

### 为什么重要

这决定了项目的取舍：演示优先、可离线运行优先，而不是追求最强语义检索效果。

### 代码落点

- `app/storage/vector_store.py`

### 理解要点

- `VectorStore` 默认通过 `Milvus Lite` 本地文件模式持久化到磁盘，也可切远端 Milvus。
- `HashEmbeddingProvider` 用哈希生成固定维度向量，目的是“足够演示”。
- 真正接生产时，通常会把这里替换成真实 embedding provider，但检索接口可以基本不变。

## 10. 规则引擎

### 概念

规则引擎是硬约束执行器，用来表达“绝对不能违反”的业务规则。

### 为什么重要

调度系统必须区分“建议优化”和“强制禁止”。前者可以讨论，后者不允许越线。这个角色由 `RuleEngine` 承担。

### 代码落点

- `app/rules/rule_engine.py`
- `app/rules/sample_rules.yaml`

### 理解要点

- 规则文件里定义禁行段、路线映射、角色权限。
- `is_route_allowed()` 用于判断路线是否合法。
- `validate_proposal()` 用于对完整调度方案做最终放行或拒绝。
- `GatekeeperAgent` 本质上只是规则引擎的 API 包装层。

## 11. 调度求解器

### 概念

调度建议不是手写 if/else 拼出来的，而是由 CP-SAT 求解器在约束下解一个小型分配问题。

### 为什么重要

这能清楚地区分“业务偏好”和“数学求解”。当车辆、任务和约束继续增多时，这条路比纯规则堆叠更可扩展。

### 代码落点

- `app/optim/solver.py`

### 理解要点

- 决策变量是 `x[truck, task]`，表示某车是否分配到某任务。
- 约束包括：
  - 每辆车只能选一个任务
  - 每个任务受容量限制
  - 禁行或封路路线不能被选择
- 目标函数综合了：
  - 空驶距离
  - 排队等待
  - 路线切换惩罚

因此 `dispatch` 的本质是“带业务约束的分配优化”，不是文本生成。

## 12. 审计与证据链

### 概念

每个 Agent 输出都会记录 `payload + evidence`，形成一条能追溯“为什么这样建议”的证据链。

### 为什么重要

在真实生产系统里，输出是否合理不是只看结果，还要能解释依据来自哪里。这个工程虽然是 MVP，但已经保留了这种追责思路。

### 代码落点

- `app/agents/base.py`
- `app/models/audit.py`
- `app/storage/audit_store.py`

### 理解要点

- 审计事件类型目前主要是 `agent_output`。
- `evidence` 可能来自告警 ID、RAG 文档 ID、规则来源等。
- `GET /audit/events` 可以查看最近事件，冒烟测试也会校验它是否正常工作。

## 13. 配置系统

### 概念

这个项目把运行配置集中到 `Settings`，并通过环境变量驱动，而不是在业务代码里到处写常量。

### 为什么重要

只有这样才能在不改业务逻辑的前提下切换 provider、目录、规则文件、超时和审计路径。

### 代码落点

- `app/settings.py`
- `.env.example`

### 理解要点

- `BaseSettings` 自动从 `.env` 和环境变量读配置。
- 路径型配置会通过 `resolve_path()` 转成项目内绝对路径。
- LLM 凭证支持 `ANTHROPIC_API_KEY`、`ANTHROPIC_AUTH_TOKEN` 和 `LLM_API_KEY` 的顺序回退。

## 14. Provider 抽象

### 概念

`LLMClient` 是 provider 抽象层，它的目标不是封装所有模型能力，而是给当前项目提供一个稳定的“生成结构化 JSON”接口。

### 为什么重要

这样业务 Agent 不需要关心 Anthropic SDK 细节，也不会把厂商耦合到每个业务文件里。

### 代码落点

- `app/llm/client.py`

### 理解要点

- `build_llm_client()` 根据 `LLM_PROVIDER` 选择实现。
- 当前支持 `mock` 和 `anthropic`。
- `anthropic` 模式支持 `ANTHROPIC_BASE_URL`，因此可以挂兼容三方网关。
- 这里的抽象刻意很薄，只覆盖当前业务真正需要的能力。

## 15. 回退设计

### 概念

回退不是异常处理细节，而是架构的一部分。这个工程默认假设外部模型可能失败。

### 为什么重要

只要外部依赖一失败，接口就全挂，这种系统很难用于真实业务演示。这里采用的策略是“外部增强可失效，确定性主链不能失效”。

### 代码落点

- `app/llm/client.py`
- `app/agents/base.py`

### 理解要点

- Anthropic SDK 缺失时回退
- API key 缺失时回退
- 网关报错时回退
- 模型返回非 JSON 或 JSON 校验失败时回退

这套回退让系统在 `mock` 和 `anthropic` 之间切换时，行为仍然可预测。

## 16. 冒烟测试

### 概念

冒烟测试不是单元测试替代品，而是确认“主链是否活着”的最短闭环。

### 为什么重要

这个工程的价值在于整链路联动，所以只测单函数意义不够。冒烟测试覆盖的是从入库、分诊、调度到守门和审计的联通性。

### 代码落点

- `scripts/smoke_test.py`
- `tests/test_smoke.py`

### 理解要点

- `scripts/smoke_test.py` 面向手工执行，直接调用运行中的 HTTP 服务。
- `tests/test_smoke.py` 面向自动化回归，用 `TestClient` 跑应用内闭环。
- 测试里显式清空 Anthropic 相关环境变量，是为了避免本地真实密钥污染回归结果。

## 17. 这个工程最重要的设计取舍

如果你只记住几件事，建议记这五条：

1. 这是“确定性主链 + LLM 增强”，不是“LLM 全权决策”。
2. `snapshot` 是所有 Agent 的共同上下文中心。
3. Pydantic 模型是系统契约，比提示词更稳定。
4. RAG 提供的是显式依据，不只是模型上下文补充。
5. 审计和 gatekeeper 决定了这个工程具备向生产思路靠拢的骨架。

## 18. 建议的阅读路径

如果你要继续深入改这个项目，推荐按下面顺序读代码：

1. `app/main.py`
2. `app/storage/state_store.py`
3. `app/models/proposal.py`
4. `app/agents/base.py`
5. `app/agents/triage_agent.py`
6. `app/optim/solver.py`
7. `app/rules/rule_engine.py`
8. `app/llm/client.py`
9. `tests/test_smoke.py`

这样读下来，你会先建立系统骨架，再进入具体实现细节，不容易迷路。
