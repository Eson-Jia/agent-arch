你现在要扮演一个资深 Java / Spring AI Alibaba 工程师。请阅读下面的业务背景和目标，然后在本地 `examples` 工程中为我生成一个“新的演示工程”。你输出的不是方案说明，而是一个可以直接指导 Claude Code 在本地仓库落地代码的执行型 prompt。

这个 prompt 的目标非常明确：

1. 在 `spring-ai-alibaba/examples` 本地工程里新建一个独立 demo。
2. 这个 demo 不是为了严格遵守整个仓库已有 README 的设定，而是为了贴合我当前产品方向，做一个更合理的演示工程。
3. 基本原则是优先探索和使用 `com.alibaba.cloud.ai` 以及 `org.springframework.ai` / Spring AI Alibaba 已有能力。
4. 尽量避免自己造轮子，尤其不要优先手写一套 agent 编排、memory、tool 注册、MCP 协议适配、RAG 流程框架；除非现有能力确实无法满足，才允许少量业务层封装。
5. 业务逻辑可以大量 mock，重点是演示框架能力、模块组织方式、扩展点设计，以及后续如何接入真实系统。

你生成给 Claude Code 的 prompt，必须让它直接在本地代码库里完成工程创建、代码编写、配置、README、以及最基本的验证，而不是只停留在分析层。

---

# 业务背景

我司当前调度管理平台的架构是：

- 多个基于 Java 8 / Spring Boot 的微服务
- 服务按照领域拆分，例如 `device-center`、`user-center`
- 服务之间通过 Dubbo 相互调用
- 在 Dubbo 服务之上，还有一个类似 `dubbo-to-http` 的网关对外提供 HTTP 服务

现在希望围绕这个背景，探索“矿山智能调度 Agent”如何基于 Spring AI Alibaba 落地。

---

# 演示工程目标

请生成一个新的示例工程，用于演示以下能力：

1. 基于 Spring AI Alibaba 构建矿山智能调度 Agent
2. 支持主 Agent + 多个可扩展 subAgent / skills
3. 支持知识库 / RAG
4. 支持 memory
5. 支持操作权限控制
6. 支持审计日志与调用链路
7. 支持用户纠错反馈
8. 对“可执行操作”保留安全控制
9. 为未来接入 watchdog / 定时巡视 / 异常处置预留扩展点

注意：

- 这是演示工程，不要求真实打通生产系统
- 可以 mock Dubbo、权限、token、执行下发、知识源
- 但整体结构要像未来可以逐步替换为真实实现的工程，而不是一次性 demo 脚本

---

# 最重要的设计原则

请在生成的工程中严格遵守以下原则：

## 1. 优先使用 Spring AI Alibaba / Spring AI 的现成能力

优先考虑直接使用这些能力来搭建 demo：

- `com.alibaba.cloud.ai` 相关 starter、agent framework、dashscope、memory、rag、tool calling、mcp 等能力
- `org.springframework.ai` 的 `ChatClient`、advisor、memory、vector store、tool calling、MCP、document loader、embedding 等能力

目标是“演示如何用框架”，不是“演示如何自己从零实现一套 agent 平台”。

## 2. 尽量避免自己造轮子

以下内容如果框架已有现成做法，优先用框架，不要手搓：

- agent 编排主流程
- subAgent / tool 接入方式
- memory 管理
- 向量检索流程
- tool calling
- MCP server / client 接入
- prompt 上下文拼装基础设施
- 审计链路中的 AI 调用包装

可以自己写的部分主要应当是：

- 领域 mock 数据
- 面向矿山场景的 skill / tool 逻辑
- 安全规则
- 与现有系统对接的 gateway / adapter 接口
- 业务 README 和扩展说明

## 3. 新工程是“面向我当前产品方向”的，不要被旧示例束缚

你可以参考仓库里的已有 example，但不要强行继承它们的设计。

尤其是：

- 不要求完全沿用已有 `README` 的架构假设
- 不要求为了演示而自己发明一套框架外的 agent 分层
- 不要求必须保留某个旧示例里的模块拆法

如果你认为某个已有示例“框架使用不够深入”“过度手写编排”“没有真正体现 Spring AI Alibaba 能力”，那就不要照抄。

## 4. 生成的是“演示工程”，重在框架价值和扩展性

工程需要体现：

- 如何快速启动
- 哪些能力来自 Spring AI Alibaba
- 哪些地方是业务 mock
- 将来如何替换成真实 Dubbo / 权限 / token / 调度执行 / 知识库

---

# 建议演示的目标架构

请优先朝下面这个方向设计，但如果你发现更贴合 Spring AI Alibaba 的方式，可以调整，只要理由充分：

## 工程应至少包含以下角色

### 1. main chat agent

- 对外提供 REST 接口
- 负责用户对话入口
- 依靠框架能力完成对话、记忆、工具调用、知识问答和执行建议

### 2. operator MCP / tool center

- 独立模块，演示“操作中心”
- 对 LLM / Agent 层暴露工具能力
- 对下通过 mock gateway 模拟调用 Dubbo 领域服务
- 覆盖：
  - 权限检查
  - token 获取
  - 查询设备/车辆/调度上下文
  - 生成或提交调度动作

注意：

- 如果 Spring AI Alibaba 现成能力更适合通过 tool calling 直接接入，而不是刻意独立出远程 MCP server，也可以调整
- 但你必须在 README 中明确说明为什么这样设计更贴合当前产品演示目标

### 3. knowledge / rag 模块

- 使用框架已有的 RAG / vector store 能力
- 提供一批 mock 的矿山规范、调度规则、接口说明文档
- 演示知识检索如何参与回答或辅助决策

### 4. memory

- 优先使用框架已有 memory 能力
- 先用最轻量的可运行方案
- 允许为 Redis / JDBC 等保留替换点，但不要第一版就自己造复杂 memory 实现

### 5. 安全控制

- 对可执行操作设置安全门
- 确保“风险评估 / 权限检查 / token 获取 / confirm 二次确认”这些流程顺序合理
- 安全门不能只是返回文案，必须体现在执行前的控制链路上

### 6. watchdog 扩展点

- 第一阶段可以不真正实现后台任务闭环
- 但要明确预留：
  - 周期巡视
  - 压车检测
  - 异常上报
  - 方案生成

---

# 业务能力建议

请在 demo 中尽量覆盖这些场景：

1. 用户问“当前矿卡状态如何”
2. 用户问“是否存在压车风险”
3. 用户问“给出调度建议”
4. 用户发起“执行某个调度动作”
5. 用户问“红线规则/规范是什么”
6. 用户对错误回答进行纠错反馈

如果你认为某些场景更适合通过 tool calling / MCP / RAG 的组合来体现，请按更合理的方式实现。

---

# 对 Claude Code 的硬性要求

你输出的 prompt 必须明确要求 Claude Code：

1. 先阅读本地仓库中与 Spring AI Alibaba 相关的 examples，吸收可复用写法
2. 但不要机械复制已有 example 的架构
3. 在 `examples` 目录下创建一个新的独立 demo 工程
4. 工程命名要清晰体现“矿山调度 + agent + spring ai alibaba”
5. 代码要能编译
6. README 要说明：
   - 模块结构
   - 用到了哪些 Spring AI Alibaba / Spring AI 能力
   - 哪些是 mock
   - 如何启动
   - 如何验证
   - 后续如何接 Dubbo / 权限 / token / 真实知识库
7. 如果某些地方存在框架能力选择，请在 README 中解释取舍
8. 不要只给我代码骨架；要给最小可运行实现
9. 尽量补基本测试，至少覆盖关键业务路径或关键 Spring Bean 装配
10. 修改完成后，执行最小必要的构建 / 测试验证

---

# 对实现风格的要求

请在 prompt 中要求 Claude Code：

- 以“框架能力优先”为第一原则
- 先找 `com.alibaba.cloud.ai` / `org.springframework.ai` 的直接用法
- 能用现成 starter / 配置装配的，就不要自己再抽象一层
- 能通过 tool / advisor / memory / rag 组合完成的，就不要写一个纯手工 if/else 的 agent 编排核心
- 不要为了“看起来有多个 agent”而手写很多空壳类
- 优先让演示工程体现：
  - 真实使用框架
  - 结构清晰
  - 后续可替换
  - 便于我继续演化成产品 PoC

---

# 你最终要输出给我的内容

请直接输出“一整段给 Claude Code 使用的高质量 prompt”，不要输出分析过程，不要输出多套备选，不要解释你自己为什么这么写。

这个 prompt 必须：

- 足够具体，可直接驱动 Claude Code 开工
- 明确工程目标、边界、优先级、实现原则
- 明确要求它真的在本地 examples 代码库中创建和修改文件
- 明确要求它避免过度自研、优先探索 `com.alibaba.cloud.ai` 的使用方式

只输出最终 prompt 正文。
