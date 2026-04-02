# Mine LLM Dispatch Demo

一个可本地运行的矿山自动驾驶调度室多 Agent MVP。它用 `FastAPI + OR-Tools + ChromaDB` 演示五类能力：

- 遥测与告警接入
- 告警分诊
- 调度建议（建议态，不直接控车）
- 安全守门校验
- 异常诊断、趋势预测与审计留痕

## 项目结构

```text
mine-llm-dispatch-demo/
├── app/
├── docs/knowledge_base/
├── scripts/
├── tests/
├── .env.example
├── pyproject.toml
└── README.md
```

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

## 默认配置

`.env.example` 关键配置：

```env
APP_ENV=dev
VECTOR_STORE=chroma
LLM_PROVIDER=mock
AUDIT_LOG_PATH=data/audit/audit.jsonl
```

说明：

- 当前 MVP 使用 `mock` 推理模板，不依赖外部 LLM 即可运行。
- 所有密钥都通过环境变量传入，代码和日志不会写死密钥。
- 原始视频、个人定位等敏感数据不进入知识库，只保留结构化事件引用。

## 主要 API

- `POST /ingest/telemetry`
- `POST /ingest/alarm`
- `GET /state/snapshot`
- `GET /audit/events`
- `POST /agents/triage`
- `POST /agents/dispatch`
- `POST /agents/gatekeeper`
- `POST /agents/diagnose`
- `POST /agents/forecast`

## Smoke Test

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
- 若未来接入外部 LLM，建议保持“建议态 + 人工确认 + 审计留痕”边界不变
