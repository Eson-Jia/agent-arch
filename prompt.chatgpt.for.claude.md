# Claude Code 执行 Prompt：在 spring-ai-alibaba/examples 下新建「矿山智能调度 Agent」演示工程

你是一名资深 Java / Spring AI Alibaba 工程师。请在当前本地仓库 `/home/ubuntu/Work/examples` 下，**真实地创建和修改文件**，完成一个新的独立演示工程。不要只给骨架，不要只写方案，必须落地可编译、可启动、有最小验证。

---

## 一、任务目标

在 `examples` 根目录下新建一个独立 Maven 子模块，命名为 `spring-ai-alibaba-mine-dispatch-agent-example`（清晰体现「矿山调度 + agent + Spring AI Alibaba」），并将其加入父 `pom.xml` 的 `<modules>` 列表。

该工程用于演示：如何基于 **Spring AI Alibaba / Spring AI 的现成能力** 构建一个矿山智能调度 Agent，而不是从零手写一套 agent 平台。

---

## 二、最高优先级原则（不可违背）

1. **框架能力优先**：所有能力先在 `com.alibaba.cloud.ai.*`（starter、agent、dashscope、memory、rag、tool-calling、mcp 等）和 `org.springframework.ai.*`（ChatClient、Advisor、ChatMemory、VectorStore、@Tool / ToolCallback、MCP、DocumentReader、Embedding 等）中寻找现成用法。
2. **严禁自造轮子**：不要手写 agent 编排主循环、不要自己实现 memory 存储抽象、不要自己造 tool 注册机制、不要自己实现 RAG pipeline、不要自己发明 MCP 协议适配。只允许极薄的业务胶水层。
3. **不机械复制旧 example**：先阅读仓库中相关 example（见第三步），吸收写法，但如果某个 example 过度手写编排、框架用得浅，就**不要抄**。以当前产品方向为准。
4. **业务全 mock，但结构像产品 PoC**：Dubbo / 权限 / token / 执行下发 / 知识文档全部 mock，但接口和分层要为未来替换真实实现留好扩展点。
5. **演示工程重在体现框架价值**：不要为了显得「有多个 agent」而堆空壳类。

---

## 三、开工前必做的调研（先读，再写）

在动手前，用 Grep/Glob 在本仓库中扫读以下内容，列出你打算复用的具体类和写法，再决定实现方案：

- `spring-ai-alibaba-agent-example/**`（主 agent 与 subAgent 的官方写法）
- `spring-ai-alibaba-rag-example/**`（RAG / VectorStore 的最小接入方式，优先用内存或 SimpleVectorStore）
- `spring-ai-alibaba-mcp-example/**`（MCP server/client 的标准接入）
- `spring-ai-alibaba-chat-example/**` 里的 dashscope 用法
- 根 `pom.xml` 的版本锁（Java 17、Spring Boot 3.5.7、Spring AI 1.1.0、Spring AI Alibaba 1.1.0.0-M5），以及 `.env.example`

重点确认：仓库中 `com.alibaba.cloud.ai` 提供的 agent/tool/memory/rag 的**标准装配方式**。你的实现必须直接使用它们，而不是绕开。

---

## 四、工程必须包含的角色与落地要求

### 1. Main Chat Agent（REST 入口）
- 使用 `ChatClient` + Spring AI Alibaba 的 agent/advisor 能力组装。
- 对外提供 `POST /api/agent/chat`（入参含 `sessionId`、`userId`、`message`）与 `POST /api/agent/feedback`（用户纠错反馈，写入审计并作为后续上下文 hint）。
- 记忆、知识检索、工具调用、审计全部通过**框架提供的 Advisor 链**装配，不要在 Controller 里手动拼 prompt。

### 2. Operator Tool Center（操作中心）
- 以 Spring AI 的 `@Tool` / `ToolCallback` 方式暴露工具，**默认走 in-process tool calling**（更贴合当前演示目标）。
- 至少实现以下 mock 工具：`queryTruckStatus`、`queryDispatchContext`、`detectTruckJam`（压车检测）、`suggestDispatchPlan`、`submitDispatchAction`。
- 工具内部通过一个 `DubboGatewayMock` 接口伪造「dubbo-to-http 网关 → device-center / user-center」的调用路径，接口形态要像未来可直接替换为真实 Dubbo 客户端。
- 额外提供一个最小 MCP server 子模块或配置入口（可选但推荐），用 Spring AI Alibaba 的 MCP starter 暴露上述工具，README 中解释「in-process vs MCP」的取舍。

### 3. Knowledge / RAG
- 使用框架 `VectorStore`（优先 `SimpleVectorStore` 或内存实现，零外部依赖即可跑）+ `DocumentReader` + `QuestionAnswerAdvisor`（或 Spring AI Alibaba 对应 advisor）。
- 在 `src/main/resources/knowledge/` 放置 3–5 份 mock 文档：矿山调度红线规则、压车处置规范、调度接口说明、车辆状态术语表。
- 启动时自动灌库，不需要用户手动操作。

### 4. Memory
- 直接使用 Spring AI 的 `ChatMemory` + `MessageChatMemoryAdvisor`（或 Spring AI Alibaba 的现成 memory 组件），默认 in-memory 实现。
- 在配置层预留 Redis/JDBC 替换说明，但**第一版不要真的写**。

### 5. 安全控制链（核心演示点）
- 以 Advisor 或 tool 前置拦截器形式实现，顺序为：**风险评级 → 权限校验（mock）→ token 获取（mock）→ 需要二次确认的动作返回 `requireConfirm`**。
- `submitDispatchAction` 必须真实受控于该链路，而不是只在回答文本里说「请确认」。
- 二次确认通过同一 `/chat` 接口带上 `confirmToken` 继续完成。

### 6. 审计与调用链
- 实现一个 `AuditAdvisor`（基于 Spring AI 的 Advisor 接口），记录：prompt、命中的工具、RAG 命中片段、安全决策、最终回答。
- 写入内存 + 打日志即可；提供 `GET /api/audit/{sessionId}` 查询。

### 7. Watchdog 扩展点
- 仅建立 `watchdog` 包与接口（`PeriodicInspector`、`AnomalyHandler`）与一个 `@Scheduled` 占位实现（打印日志即可），并在 README 中说明未来如何接「压车巡视 / 异常处置 / 方案生成」。**不要**在第一版写完整闭环。

### 8. 用户纠错反馈
- `/api/agent/feedback` 将反馈持久化到内存存储，并通过 Advisor 在后续对话中作为上下文提示注入（用框架机制，不要自己改 prompt 字符串拼接）。

---

## 五、场景必须跑通（README 中附 curl 示例）

1. 「当前矿卡状态如何」→ 命中 `queryTruckStatus` 工具。
2. 「是否存在压车风险」→ 命中 `detectTruckJam` + RAG 规范。
3. 「给出调度建议」→ `suggestDispatchPlan` + RAG。
4. 「执行调度动作 X」→ 触发安全链，返回 `requireConfirm`；第二次带 token 确认后才调用 `submitDispatchAction`。
5. 「红线规则是什么」→ 纯 RAG。
6. 「刚才回答错了，正确的是 …」→ feedback 写入并影响下一轮。

---

## 六、工程规范

- Java 17、Spring Boot 3.5.7、Spring AI 1.1.0、Spring AI Alibaba 1.1.0.0-M5，版本继承父 POM，不要自定义。
- 包名：`com.alibaba.cloud.ai.example.mine.dispatch.*`，按 `agent / tools / rag / memory / security / audit / watchdog / gateway / web / config` 分包。
- 配置使用 `application.yml`，DashScope API key 通过 `${AI_DASHSCOPE_API_KEY}` 读取，并更新/新增 `.env.example`。
- 至少包含以下测试：
    - 上下文装配测试（`@SpringBootTest` 验证关键 Bean 与 Advisor 链注册）。
    - 安全链单测（不需要真实调用 LLM，可 mock `ChatModel`）。
    - 一个 tool 的单元测试。
- 代码风格符合仓库 `spring-javaformat`。

---

## 七、README 必写内容

在模块根目录写 `README.md`，必须覆盖：

1. 模块结构与分包职责。
2. **明确列出**哪些能力直接来自 `com.alibaba.cloud.ai` / `org.springframework.ai`（逐条对应到具体类 / starter）。
3. 哪些是 mock（Dubbo 网关、权限、token、知识文档、执行下发）。
4. 如何启动（环境变量、一条 `mvn spring-boot:run`）。
5. 如何用 curl 验证上面 6 个场景。
6. 关键设计取舍：为什么用 in-process tool calling 而不是独立 MCP server（或反之）、为什么用 SimpleVectorStore、memory 为什么用内存版。
7. 未来演进路线：如何替换真实 Dubbo 客户端、如何接入企业权限 / token、如何切换到真实向量库、如何落地 watchdog 闭环。

---

## 八、收尾验证（必须执行）

1. `mvn -pl spring-ai-alibaba-mine-dispatch-agent-example -am -DskipTests package` 通过。
2. `mvn -pl spring-ai-alibaba-mine-dispatch-agent-example test` 通过（允许不依赖真实 DashScope 的测试）。
3. `make format-check` 通过；不过就 `make format-fix`。
4. 在回复中给出：新增/修改文件清单、关键设计取舍摘要、验证命令实际输出摘要（不要贴长日志）。

---

## 九、绝对不要做的事

- 不要为了「多 agent 感」手写一堆空 `SubAgent` 类。
- 不要自己定义 `Tool` 接口或 `Memory` 接口去「抽象」框架已有能力。
- 不要自己实现 MCP 协议帧。
- 不要手写一个 RAG 主循环（检索 → 拼 prompt → 调模型）；用 Advisor。
- 不要把安全控制做成「在回答文本里写请确认」。
- 不要照抄某个旧 example 的模块拆法如果它掩盖了框架能力。
- 不要引入 Redis / PG / Milvus 等外部依赖作为第一版默认实现。

现在开始：先调研，再列出你将复用的框架类与 Advisor 链设计，然后落地代码、补测试、写 README、跑验证。
