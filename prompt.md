你现在进入“强制交付模式”。

你不是在做建议、评审、方案草稿，也不是在给我示例片段。  
你要完成的是：**直接交付一个可下载、可运行、可编译、可扩展的完整 Java 17+ Maven 工程压缩包（zip 附件）**。

你的身份固定为：
- 首席 Java 架构师
- Spring Boot / Spring AI / Spring AI Alibaba 专家
- Redis Stack / RAG / Multi-Agent 系统工程师
- 资深交付负责人

你的任务只有一个：

**基于 Spring AI Alibaba，生成一个拥有多个 subagent 的矿山调度系统 Agent 服务完整工程，仓库名固定为 `eacon-smart-mine-dispatch-agent-service`，公司名固定为 `eacon`，模型供应商固定为 `qwen`，初版所有 memory / context / knowledge / vector 等状态数据全部存 Redis。**

--------------------------------
一、绝对不可违反的交付规则
--------------------------------

1. **最终必须产出 zip 附件供我下载。**
    - zip 文件名固定为：`eacon-smart-mine-dispatch-agent-service.zip`
    - 你必须真正生成完整工程文件并打包为 zip
    - 不允许只说“我可以为你生成”
    - 不允许只给目录树
    - 不允许只给关键代码
    - 不允许只给若干核心类
    - 不允许只给 README
    - 不允许只给伪代码
    - 不允许只给架构图
    - 不允许只给 patch
    - 不允许把完整源码省略为“略”
    - 不允许说“由于篇幅限制”
    - 不允许说“下面仅展示核心部分”
    - 不允许把剩余文件留给我手工补齐

2. **你必须先深度研究，再定版本，再生成代码。**
    - 必须先核对截至当前的官方兼容版本、官方 API、官方推荐模式
    - 然后再生成完整工程
    - 绝不允许凭过时记忆胡写依赖与 API

3. **必须优先使用一手官方资料，严禁使用二手博客作为主依据。**
   优先来源仅限：
    - `alibaba/spring-ai-alibaba` 官方 GitHub 仓库
    - Spring AI Alibaba / Spring Cloud Alibaba AI 官方文档
    - Spring AI 官方文档
    - Redis 官方文档
    - 必要时补充官方 starter / 官方模块文档

4. **若当前环境支持创建文件与附件，你必须直接创建 zip 附件。**
    - 这不是可选项，是硬要求
    - 你必须使用可用的文件/代码/工件能力，把所有源码写入文件系统并打包
    - 交付物必须是一个真实可下载 zip 文件，而不是文本模拟的“压缩包内容”

5. **若当前环境客观上真的不支持生成附件，也不能偷懒。**
    - 你必须立即退化为“逐文件输出完整源码”的模式
    - 按文件路径逐个输出完整内容
    - 自动连续输出，直到全部文件结束
    - 不要等待我说“继续”
    - 不要在输出到一半时停下
    - 即使需要多条消息，也必须自己继续完成

6. **你必须把“是否成功交付”的标准定义为：**
    - 已完成研究结论
    - 已给出版本选型说明
    - 已产出完整工程全部文件
    - 已生成 zip 附件，或在附件能力不可用时完整逐文件输出
    - 已给出运行步骤
    - 已给出测试步骤
    - 已给出示例调用
    - 已保证项目在配置 API Key 与 Redis 后可启动

7. **不得把任何关键实现留给我。**
    - 你要像真正交付项目给我一样，把工程补完整
    - 我不是来和你共创骨架的，我是来拿完整项目的

--------------------------------
二、研究阶段必须完成的任务
--------------------------------

你必须先完成深度研究，并基于研究结果做最终技术定版。

必须核对并确认以下内容的“当前官方兼容稳定方案”：
1. Spring Boot 版本
2. Spring AI 版本
3. Spring AI Alibaba 版本
4. Spring AI Alibaba Agent / Multi-Agent / Subagent 相关模块与 API
5. Qwen / DashScope 接入方式
6. Redis Vector Store 的官方支持方式
7. Redis Stack 所需能力（如 RediSearch / RedisJSON / 向量检索）
8. RAG 当前官方推荐写法
9. 适合当前版本的测试方案（如 Testcontainers）
10. 当前官方是否有 subagent/multi-agent pattern 示例与推荐落地方式

研究规则：
- 不允许“我记得”
- 不允许“通常可以”
- 不允许模糊版本
- 不允许使用已弃用 API
- 不允许版本随意拼装
- 若文档冲突，必须选择“当前稳定且兼容”的官方方案，并说明原因

--------------------------------
三、目标工程定义
--------------------------------

请交付一个完整 Maven 工程：

- 仓库名：`eacon-smart-mine-dispatch-agent-service`
- groupId：`com.eacon`
- artifactId：`eacon-smart-mine-dispatch-agent-service`
- Java：17+
- 技术核心：Spring Boot + Spring AI + Spring AI Alibaba + Redis Stack
- 模型供应商：Qwen
- 初版矿山外部接口：全部 mock 实现
- 工程定位：矿山调度系统 Agent 服务

工程必须体现这是一个“可扩展的生产雏形”，不是 demo 拼凑。

--------------------------------
四、业务目标与场景
--------------------------------

系统面向矿山调度场景，支持以下典型任务：
- 车辆与铲装设备调度建议
- 班次交接总结
- 设备状态分析
- 安全风险识别
- 异常事件应急建议
- 基于知识库的制度 / 预案 / SOP / 设备手册问答
- 多轮会话中的上下文记忆与连续决策支持

--------------------------------
五、必须实现的 Multi-Agent / Subagent 体系
--------------------------------

至少实现以下 Agent，由一个主 orchestrator 统一调度：

1. `orchestrator-agent`
    - 总入口
    - 意图识别
    - 任务拆解
    - 调度 subagent
    - 汇总结果
    - 管理跨 agent 上下文协作

2. `production-planning-agent`
    - 产量目标分析
    - 班次任务拆解
    - 作业面负载分析
    - 生产调度建议

3. `haulage-dispatch-agent`
    - 卡车、铲车、破碎机、运输路线、排队分析
    - 运输与装载调度建议

4. `equipment-health-agent`
    - 设备状态分析
    - 故障风险评估
    - 保养建议

5. `safety-compliance-agent`
    - 安全规则分析
    - 风险识别
    - 告警解读
    - 结合知识库检索制度与预案

6. `knowledge-rag-agent`
    - 知识库召回
    - 检索结果整合
    - 来源引用整合
    - 支持 RAG

7. `shift-handover-summary-agent`
    - 对班次信息、告警、异常、调度结果做交接总结

8. `emergency-response-agent`
    - 处理道路中断、设备停机、天气影响、人员异常等突发事件
    - 输出应急建议

硬要求：
- 每个 agent 都必须有清晰职责边界
- 每个 agent 都必须有 system prompt
- 每个 agent 都必须有 description
- 每个 agent 都必须有 tools 设计
- 每个 agent 都必须有输入/输出边界
- orchestrator 必须体现真正的 subagent 协作，不接受简单 if-else 伪装成多 agent
- 若官方当前版本有 subagent pattern，优先按官方 pattern 落地
- 若官方 pattern 有局限，必须做工程化补强，并解释理由

--------------------------------
六、上下文系统必须完整落地
--------------------------------

你必须设计并实现一个完整的 Context System，所有状态数据初版统一存 Redis。

至少包括：

1. 会话上下文
    - sessionId
    - userId
    - userRole
    - currentShift
    - currentMineSite
    - currentPit
    - recentConversationHistory
    - recentAgentCollaborationTrace

2. 短期记忆
    - current turn messages
    - recent tool outputs
    - recent dispatch suggestions
    - recent task decomposition result

3. 长期记忆
    - 用户偏好
    - 历史查询主题
    - 历史关键事件摘要
    - 历史调度偏好
    - 轻量语义记忆设计（初版仍落 Redis）

4. 共享协作上下文
    - taskId
    - parentTaskId
    - objective
    - constraints
    - facts
    - partialResults
    - todoItems
    - subagentStatus
    - finalSynthesis

5. 上下文压缩与摘要
    - 长会话自动摘要
    - 控制 token 开销
    - 保留关键业务事实

6. 生命周期与 TTL
    - 短期记忆需要合理 TTL
    - 长期记忆采用长 TTL 或无 TTL
    - README 中必须解释策略原因

必须交付：
- Redis key 设计
- Redis 数据结构选型
- 序列化方案
- 上下文读写代码
- 上下文压缩代码
- 清理与过期策略代码

--------------------------------
七、知识库系统与 RAG 必须完整落地
--------------------------------

必须实现 Knowledge Base / RAG 系统，初版所有数据统一存 Redis / Redis Stack。

至少支持：
1. 文档导入
    - txt / md / json / csv
    - 预留 pdf / docx 扩展点

2. 分块
    - 合理 chunking 策略
    - chunk metadata

3. 向量化
    - 使用当前官方兼容 embedding 方案
    - 向量写入 Redis
    - metadata 写入 Redis

4. 检索
    - topK
    - similarity threshold（若当前 API 支持）
    - metadata filter
    - 支持按矿区、主题标签、设备类型、文档类型过滤

5. 知识库维护
    - 导入
    - 删除
    - 重建
    - 文档级删除
    - 重新索引
    - chunk 级维护（合理时）

6. RAG 问答
    - knowledge-rag-agent 基于召回内容回答
    - 尽量提供来源与元数据
    - 体现真实 RAG 过程，而不是让模型裸答

7. 示例知识文档
   至少内置两组矿山知识样例，例如：
    - 班次交接 SOP
    - 设备停机应急预案
    - 运输道路安全规范
    - 铲装与运输协同规则

--------------------------------
八、矿山领域模型要求
--------------------------------

至少设计并实现以下模型：

- MineSite
- Pit
- Workface
- Shift
- Operator
- Truck
- Shovel
- Crusher
- ConveyorBelt
- HaulRoute
- DispatchOrder
- EquipmentStatus
- AlarmEvent
- SafetyIncident
- ProductionTarget
- ShiftReport
- KnowledgeDocument
- KnowledgeChunk

要求：
- 清晰区分实体、DTO、VO、Command、Query
- 合理的枚举与状态流转
- 合理使用 Java 17 特性（record / sealed / switch 等）
- 不要过度设计
- 不要为了炫技牺牲可维护性

--------------------------------
九、外部工具层与 mock 能力必须可运行
--------------------------------

因为现阶段没有真实矿山外部系统，所有外部接口先用 mock，但必须做成真实可调用的工具层。

至少实现这些工具或等价服务：

- `queryEquipmentStatus(...)`
- `queryTruckQueue(...)`
- `queryWorkfaceLoad(...)`
- `queryRouteAvailability(...)`
- `createDispatchPlan(...)`
- `evaluateSafetyRisk(...)`
- `retrieveKnowledge(...)`
- `summarizeShift(...)`
- `createEmergencySuggestion(...)`

要求：
- 使用 Redis seed 数据模拟业务状态
- Agent 的建议必须真正建立在这些工具调用结果之上
- 必须提供数据初始化逻辑
- 至少提供一套完整的矿山班次 / 车辆 / 设备 / 路线 / 告警模拟数据

--------------------------------
十、技术硬性要求
--------------------------------

必须满足全部要求：

1. Java 17+
2. Maven 工程
3. Spring Boot 当前兼容稳定版
4. Spring AI 当前兼容稳定版
5. Spring AI Alibaba 当前兼容稳定版
6. Qwen 模型接入
7. Redis Stack 作为初版唯一持久化与状态存储
8. REST API
9. 增加 SSE 或 streaming 接口
10. OpenAPI / Swagger
11. Spring Validation
12. 全局异常处理
13. 结构化日志
14. Actuator
15. 清晰配置管理
16. `docker-compose.yml`
17. `.env.example`
18. `README.md`（中文）
19. 单元测试
20. 至少关键链路集成测试
21. 本地一键可跑（配置 API Key 前提下）

明确禁止：
- MySQL
- MongoDB
- Elasticsearch
- Kafka
- 任何不是刚需的基础设施
- 伪代码
- 只声明接口不实现
- TODO / FIXME / placeholder / omitted / 略

--------------------------------
十一、Redis 设计必须足够细
--------------------------------

必须提供明确的 Redis key 规范，并在代码中贯彻，至少包含：

- `mine:session:{sessionId}`
- `mine:memory:short:{sessionId}`
- `mine:memory:long:{userId}`
- `mine:agent:context:{sessionId}`
- `mine:agent:task:{taskId}`
- `mine:dispatch:order:{orderId}`
- `mine:equipment:status:{equipmentId}`
- `mine:shift:{shiftId}`
- `mine:kb:doc:{docId}`
- `mine:kb:chunk:{chunkId}`
- `mine:kb:index:{collection}`
- `mine:event:stream:{sessionId}`

你必须说明并实现：
- 每类 key 用什么 Redis 数据结构
- 哪些 key 设置 TTL，哪些不设置
- RedisJSON / Hash / String / List / Set / ZSet / Stream / Vector Index 的取舍
- 元数据字段设计
- Redis Vector Search 的落地方式
- 为什么这样设计
- 如何兼顾可读性、查询效率、扩展性

--------------------------------
十二、推荐包结构
--------------------------------

请生成清晰、可维护、工程化的项目结构。至少包含但不限于：

- `config`
- `controller`
- `application`
- `domain`
- `repository`
- `infra`
- `infra.redis`
- `agent`
- `agent.subagents`
- `context`
- `knowledgebase`
- `memory`
- `rag`
- `tools`
- `prompt`
- `common`
- `exception`
- `test`

可以微调，但必须清晰。

--------------------------------
十三、API 要求
--------------------------------

至少交付这些接口：

1. `POST /api/agent/chat`
2. `POST /api/agent/chat/stream`
3. `POST /api/context/sessions`
4. `GET /api/context/sessions/{id}`
5. `DELETE /api/context/sessions/{id}`
6. `POST /api/memory/summary/rebuild`
7. `POST /api/kb/documents/import`
8. `DELETE /api/kb/documents/{id}`
9. `POST /api/kb/search`
10. `POST /api/dispatch/plan`
11. `GET /api/equipment/status`
12. `POST /api/shift/summary`
13. `POST /api/emergency/analyze`
14. `GET /actuator/health`

要求：
- 每个 API 都必须有 controller / request / response / service
- 统一响应结构
- 完整参数校验
- 合理异常处理
- 给出 curl 示例
- 文件上传场景要完整实现

--------------------------------
十四、测试与可运行性
--------------------------------

至少提供以下测试：

1. context 读写测试
2. kb 导入与检索测试
3. orchestrator -> subagent 调度链路测试
4. 一个端到端 API 测试
5. Redis 集成测试（优先使用 Testcontainers 或当前合理方案）

还必须提供：
- `docker-compose.yml`
- Redis Stack 本地启动方式
- API Key 配置说明
- 本地运行命令
- 测试命令
- 示例调用流程

--------------------------------
十五、Qwen 接入要求
--------------------------------

模型供应商固定为 `qwen`。你必须先研究当前官方推荐接入方式，再决定最终实现。

要求：
- 优先采用当前官方兼容稳定的 Spring AI Alibaba + Qwen 接入方式
- 在研究结论中说明选型原因
- 在配置文件中明确预留模型名、API Key、超参数配置
- 给出本地环境变量示例
- 必须说明当前实现依赖的官方能力

--------------------------------
十六、输出格式是硬约束
--------------------------------

你必须严格按下面顺序交付，不允许跳步，不允许偷工减料。

### 第 1 部分：研究结论与版本选型
必须包含：
- 核心依赖及最终版本
- 为什么选这些版本
- subagent 方案依据
- Qwen 接入方案依据
- Redis Vector Store / Redis Stack 方案依据
- 官方来源引用

### 第 2 部分：总体架构设计
必须包含：
- 中文架构说明
- Mermaid 架构图
- 模块职责
- Agent 协作时序说明
- 上下文系统与知识库系统说明

### 第 3 部分：完整项目目录树
必须用 tree 风格列出完整目录。

### 第 4 部分：生成完整源码文件
这是最重要部分，必须真正生成完整文件。

优先执行方式：
- 直接在当前环境创建所有源码文件
- 创建完整工程目录
- 生成 zip
- 把 zip 作为附件交付给我下载

若环境支持文件生成，你必须：
- 真正落盘每一个文件
- 打包 zip
- 提供 zip 附件
- 同时给出关键文件列表
- 不要只在消息里贴源码而不生成附件

若环境不支持文件附件：
- 则立即自动切换为“逐文件完整输出”
- 逐个文件输出完整内容
- 文件必须完整，不可截断，不可省略
- 自动连续输出到全部完成
- 不要等待我回复“继续”

### 第 5 部分：运行说明与验证步骤
必须包含：
- `docker compose` 命令
- `mvn` 命令
- 启动命令
- 环境变量配置
- curl 示例
- 多轮对话示例
- 知识库导入示例
- 调度建议示例
- 测试执行方式

--------------------------------
十七、文件清单要求
--------------------------------

你必须至少生成以下文件，且内容完整：

- `pom.xml`
- `docker-compose.yml`
- `.env.example`
- `README.md`
- `.gitignore`
- `src/main/resources/application.yml`
- `src/main/resources/application-local.yml`
- `src/main/resources/prompts/...`
- `src/main/resources/agents/...`
- `src/main/resources/data/...`
- 所有 `src/main/java/...` 代码文件
- 所有关键 `src/test/java/...` 测试文件

你不能漏掉任何为了“可运行”所必需的文件。

--------------------------------
十八、代码质量硬约束
--------------------------------

必须满足：

- 所有源码完整可复制
- 构造器注入
- 合理分层
- 包名、类名、方法名专业
- 关键处有必要注释
- 绝不允许 TODO / FIXME / placeholder
- 绝不允许“此处省略”
- 绝不允许伪实现冒充真实实现
- 绝不允许生成无法编译的依赖组合
- 绝不允许生成明显无法运行的配置

--------------------------------
十九、失败判定标准
--------------------------------

以下任一情况都视为你没有完成任务：

- 没有 zip 附件
- 没有完整源码
- 只输出骨架
- 只输出片段
- 漏掉测试
- 漏掉 README
- 漏掉 docker-compose
- 漏掉配置文件
- 漏掉 prompt/agent 配置
- 漏掉 seed 数据
- 用 TODO 代替实现
- 用“略”代替文件
- 让我自己补代码
- 让我自己补配置
- 让我自己补依赖版本
- 让我自己补 Redis 设计
- 让我自己补 mock 数据

--------------------------------
二十、你的执行策略
--------------------------------

执行时你必须像真正交付项目的高级工程师一样工作：

1. 先研究
2. 再定版本
3. 再做架构
4. 再生成完整工程
5. 再打包 zip
6. 再交付运行说明

你必须主动推进，不要来回试探我，不要把工作推回给我。

--------------------------------
二十一、你现在就开始执行
--------------------------------

从研究开始。  
不要输出空话，不要输出道歉，不要输出“我将会”。  
直接进入正式交付流程。  
优先目标：**生成并附上 `eacon-smart-mine-dispatch-agent-service.zip` 下载附件。**