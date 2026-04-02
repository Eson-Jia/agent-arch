# Mine LLM Dispatch Demo

一个可本地运行的矿山自动驾驶调度室多 Agent MVP。当前实现采用 `FastAPI + OR-Tools + ChromaDB + 可切换 LLM Provider`，演示六类能力：

- 遥测与告警接入
- 告警分诊
- 调度建议（建议态，不直接控车）
- 安全守门校验
- 异常诊断、趋势预测与审计留痕
- Anthropic Claude Opus / mock 双模式推理

## 项目结构

```text
mine-llm-dispatch-demo/
├── app/
│   ├── agents/         # 多 Agent 逻辑
│   ├── llm/            # mock / anthropic provider 抽象
│   ├── optim/          # OR-Tools 调度求解
│   ├── embeddings/     # hash / http embedding provider 抽象
│   ├── eval/           # 离线评测逻辑
│   ├── rag/            # 知识库入库与检索
│   ├── rules/          # 确定性规则守门
│   ├── storage/        # state / audit / vector store
│   └── workflows/      # 多 Agent 编排入口
├── docs/
│   ├── knowledge_base/
│   ├── production_execution_plan.md
│   └── project_concepts.md
├── scripts/
│   ├── evaluate_quality.py
│   ├── seed_demo_data.py
│   └── smoke_test.py
├── tests/
├── .env.example
├── pyproject.toml
└── README.md
```

补充阅读：

- `docs/project_concepts.md`：面向工程理解的概念说明，解释状态快照、RAG、求解器、规则引擎、LLM 边界和审计设计。
- `docs/production_execution_plan.md`：从 demo 到 production 的分阶段改造计划和当前执行状态。

## 最新架构

当前代码不是最初的纯 mock MVP，而是已经落成下面这条运行架构：

```text
HTTP API (FastAPI)
  -> IncidentResponseOrchestrator / Agent APIs
  -> StateStore(versioned) / AuditStore / VectorStore(ChromaDB)
  -> Agent Layer
     -> Triage / Diagnose / Forecast
        -> RAG 检索
        -> LLM Client (mock 或 anthropic)
        -> Pydantic 结构化校验
     -> Dispatch
        -> OR-Tools 求解器
     -> Gatekeeper
        -> RuleEngine 硬校验
  -> Audit JSONL
```

### 运行分层

- `API 层`：`app/main.py` 负责 FastAPI 路由、依赖装配、知识库启动入库和服务生命周期管理。
- `状态层`：`StateStore` 保存最近态势、车辆遥测和告警；`AuditStore` 记录每次 Agent 输出；`VectorStore` 用 ChromaDB 持久化知识库检索。
- `编排层`：`IncidentResponseOrchestrator` 提供 `/workflows/incident-response`，把分诊、调度和守门串成统一工作流，并固定到同一 `snapshot_version`。
- `决策层`：`dispatch_agent` 走 OR-Tools 可行解，`gatekeeper_agent` 只做规则硬校验，`triage/diagnose/forecast` 允许用 LLM 做解释增强。
- `模型层`：`app/llm/client.py` 统一封装 provider；当前支持 `mock` 和 `anthropic`，并带 prompt 注册表、失败阈值和熔断冷却时间。
- `知识层`：`app/embeddings/` 负责 embedding provider 抽象；默认 `hash`，可切到兼容 `POST /embeddings` 的 HTTP provider。
- `回退层`：真实 LLM 不可用、网关报错或返回 JSON 不合法时，自动回退到本地确定性逻辑，不影响接口可用性。

### Agent 边界

- `triage`：先做告警去重、RAG 检索和本地草稿生成，再可选调用 Claude 优化工单与动作建议。
- `diagnose`：先基于遥测、告警和规则构造 RCA 假设树，再可选调用 Claude 优化诊断表述。
- `forecast`：先由本地启发式给出 30/60 分钟预测，再可选调用 Claude 做结构化润色。
- `dispatch`：始终由 OR-Tools 给出任务分配，不把可行性判断交给 LLM。
- `gatekeeper`：始终由规则引擎执行禁行、封路、权限等 hard-check。

### LLM Provider 架构

- `LLM_PROVIDER=mock`：完全离线运行，用于本地演示、测试和无外部依赖场景。
- `LLM_PROVIDER=anthropic`：通过 Anthropic SDK 调 `messages.create`，支持官方 Anthropic 端点，也支持通过 `ANTHROPIC_BASE_URL` 接入兼容的三方供应商网关。
- `凭证解析顺序`：`ANTHROPIC_API_KEY -> ANTHROPIC_AUTH_TOKEN -> LLM_API_KEY`。
- `安全策略`：`.env` 已加入 `.gitignore`，密钥只通过环境变量读取，不写入代码和审计日志。

## 运行要求

- Python `3.11+`
- `uv` `0.11+`

## 快速启动

1. 复制环境变量模板：

```bash
cp .env.example .env
```

2. 用 `uv` 创建并同步环境：

```bash
uv sync --extra dev
```

3. 启动服务：

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

4. 查看 OpenAPI：

```text
http://127.0.0.1:8000/docs
```

5. 可选：注入演示数据

```bash
uv run python scripts/seed_demo_data.py
```

6. 一次性执行完整冒烟脚本：

```bash
uv run python scripts/smoke_test.py
```

## 默认配置

`.env.example` 关键配置：

```env
APP_ENV=dev
VECTOR_STORE=chroma
STATE_STORE_PATH=data/state/state_store.json
WORKFLOW_STORE_PATH=data/state/workflows.json
LLM_PROVIDER=mock
LLM_STRATEGY=prefer_live
EMBEDDING_PROVIDER=hash
AUDIT_LOG_PATH=data/audit/audit.jsonl
```

说明：

- 当前 MVP 使用 `mock` 推理模板，不依赖外部 LLM 即可运行。
- 支持将 `LLM_PROVIDER` 切到 `anthropic`，用 Claude Opus 原生 API 做分诊、诊断和预测增强。
- 支持将 `EMBEDDING_PROVIDER` 切到 `http`，接兼容 `POST /embeddings` 的第三方 embedding 服务。
- 所有密钥都通过环境变量传入，代码和日志不会写死密钥。
- 原始视频、个人定位等敏感数据不进入知识库，只保留结构化事件引用。

## 切换到 Claude Opus

如需接入 Claude Opus，可在 `.env` 中设置：

```env
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=your-api-key
# or:
ANTHROPIC_AUTH_TOKEN=your-api-key
ANTHROPIC_MODEL=claude-opus-4-6
ANTHROPIC_BASE_URL=
```

说明：

- `ANTHROPIC_BASE_URL` 可选，用于接入 Anthropic 兼容的三方供应商网关。
- `ANTHROPIC_API_KEY` 和 `ANTHROPIC_AUTH_TOKEN` 二选一即可，代码会优先读取 Anthropic 专用变量。
- 当前 demo 中，`triage`、`diagnose`、`forecast` 会优先调用 Claude；`dispatch` 和 `gatekeeper` 仍保持确定性规则/求解器路径。
- 如果 `anthropic` 配置不完整、接口报错或返回非法 JSON，系统会自动回退到本地 `mock + rules + solver` 逻辑，不会把接口直接打挂。

## 主要 API

- `POST /ingest/telemetry`
- `POST /ingest/alarm`
- `GET /state/snapshot`
- `GET /audit/events`
- `GET /metrics/summary`
- `POST /agents/triage`
- `POST /agents/dispatch`
- `POST /agents/gatekeeper`
- `POST /agents/diagnose`
- `POST /agents/forecast`
- `POST /workflows/incident-response`
- `GET /workflows/{workflow_id}`
- `POST /workflows/{workflow_id}/approval`
- `POST /workflows/{workflow_id}/resubmit`

## Smoke Test

服务启动后，也可以直接运行：

```bash
uv run python scripts/smoke_test.py
```

离线质量评测：

```bash
uv run python scripts/evaluate_quality.py
```

脚本会依次执行 `telemetry -> alarm -> triage -> dispatch -> gatekeeper -> incident workflow -> approval/reject -> resubmit -> metrics -> audit`，并在关键结果不符合预期时直接退出报错。

1. 写入遥测：

```bash
curl -X POST http://127.0.0.1:8000/ingest/telemetry \
  -H 'Content-Type: application/json' \
  -d '{
    "ts": "2026-04-02T10:15:23+08:00",
    "truck_id": "T12",
    "pos": {"x": 1023.4, "y": 884.2, "z": 56.7, "map_ver": "map_2026_04_01"},
    "motion": {"speed_mps": 8.2, "heading_deg": 172.3, "mode": "AUTO"},
    "load": {"state": "EMPTY", "payload_t": 0},
    "health": {"fault_code": null, "soc_pct": 63, "engine_temp_c": 72.1},
    "comms": {"rssi_dbm": -82, "uplink_kbps": 3200, "loss_pct_5s": 0.8}
  }'
```

2. 再写入一辆车，便于求解器分配：

```bash
curl -X POST http://127.0.0.1:8000/ingest/telemetry \
  -H 'Content-Type: application/json' \
  -d '{
    "ts": "2026-04-02T10:15:30+08:00",
    "truck_id": "T18",
    "pos": {"x": 1004.0, "y": 846.0, "z": 59.4, "map_ver": "map_2026_04_01"},
    "motion": {"speed_mps": 6.8, "heading_deg": 148.0, "mode": "AUTO"},
    "load": {"state": "EMPTY", "payload_t": 0},
    "health": {"fault_code": null, "soc_pct": 71, "engine_temp_c": 69.2},
    "comms": {"rssi_dbm": -85, "uplink_kbps": 3000, "loss_pct_5s": 1.4}
  }'
```

3. 写入道路告警：

```bash
curl -X POST http://127.0.0.1:8000/ingest/alarm \
  -H 'Content-Type: application/json' \
  -d '{
    "alarm_id": "ALM-20260402-000872",
    "ts": "2026-04-02T10:16:01+08:00",
    "level": "ORANGE",
    "category": "ROAD_OBSTACLE",
    "location": {"road_segment": "R7", "bbox": [1000, 860, 1060, 910]},
    "impact_zone": {"blocked": true, "detour_routes": ["R9", "R11"]},
    "evidence": [{"type": "cv_event", "id": "CV-77821", "confidence": 0.91}]
  }'
```

4. 执行告警分诊：

```bash
curl -X POST http://127.0.0.1:8000/agents/triage \
  -H 'Content-Type: application/json' \
  -d '{}'
```

5. 生成调度建议：

```bash
curl -X POST http://127.0.0.1:8000/agents/dispatch \
  -H 'Content-Type: application/json' \
  -d '{}'
```

6. 将上一步返回的 JSON 作为 `proposal` 提交给安全守门：

```bash
curl -X POST http://127.0.0.1:8000/agents/gatekeeper \
  -H 'Content-Type: application/json' \
  -d '{
    "operator_role": "dispatcher",
    "proposal": {
      "proposal_id": "DSP-20260402-0012",
      "generated_by": "dispatch_agent_v1",
      "ts": "2026-04-02T10:16:05+08:00",
      "dispatch_cycle_seconds": 120,
      "proposals": [
        {
          "truck_id": "T12",
          "next_task": {"load": "L3", "dump": "D2", "route": "R9"},
          "constraints_checked": ["NO_GO_ZONE_OK", "ALARM_IMPACT_OK", "MAP_VERSION_OK"],
          "expected": {"eta_min": 6.5, "queue_wait_min": 1.2},
          "risk_notes": []
        }
      ],
      "expected_impact": {
        "throughput_delta_pct": -1.2,
        "empty_distance_delta_pct": -6.8,
        "queue_time_delta_pct": -18.0
      },
      "requires_human_confirmation": true,
      "evidence": ["ALM-20260402-000872", "DOC-map_rules.md#chunk-0", "STATE-SUMMARY-30min"]
    }
  }'
```

7. 查看审计事件：

```bash
curl http://127.0.0.1:8000/audit/events
```

## 测试

```bash
uv run pytest
```

`tests/test_smoke.py` 会覆盖：

- `ingest/telemetry`
- `ingest/alarm`
- `agents/triage`
- `agents/dispatch`
- `agents/gatekeeper`
- `audit/events`

## 安全与回退说明

- 每个关键 Agent 输出都带 `evidence` 字段，并写入 `audit.jsonl`
- Gatekeeper 只做 hard-check，不负责优化
- 即使没有外部 LLM，仍可通过规则 + 求解器 + mock 模板输出建议
- Claude Opus 只参与建议与解释生成，不直接下发控制指令
- 若未来接入外部 LLM，建议保持“建议态 + 人工确认 + 审计留痕”边界不变
