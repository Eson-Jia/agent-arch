# 思路文档


# 当前架构现状

我司当前调度管理平台的架构是微服务工程集群基于 java8 的 spring boot 框架，基本按照领域拆分成多个 dubbo 服务，例如 device-center,user-center 等。服务之间通过 dubbo 相互调用。
dubbo 服务之上，有类似于 dubbo-to-http 的网关服务对外提供 http 服务。

# 需求：智能调度 Agent

- 矿山智能调度 Agent,基于 https://github.com/alibaba/spring-ai-alibaba.
- 拥有多个 subAgent 且可以扩展 Skills
- 接入知识库且支持 memory

# 思路 && spark

- 操作要有权限，独立一个服务 operator-mcp
  - 对上使用 mcp 协议与 LLM 交互
  - 对下使用 dubbo 调用各领域的服务
  - operator-mcp 是有状态服务
- 主要模块 main chat agent + subagent
- 有结构化的知识库和接口文档
- 有完整审计日志和调用链路
- 如果答案不对用户可以补充新的答案
- 支持 skills 和 python 代码执行
- 有安全门 subagent 做最后安全兜底
- 将压车检测，实现检测算法，这个算法执行不需要 AI 参与，处理结果有异常会推送给AI 让其生成操作提案。
- 后台有定期任务，定期执行压车检测等算法，将输出推送给 异常 agent 让其生成方案，第一阶段可以先不实现，但是要保留扩展性
- 可以利用 hooks 等机制，对执行某些任务时候进行相关权限检测 token 获取等操作，当前实现使用 mock 占位。
- 除了只读请求以外，其他影响调度平台的操作都需要安全门评估通过，最后由用户确认以后才能执行。
  - 生成操作提案以后，需要用户同意，同意以后在共享缓存中写入临时 token 有 expiration。
  - operator-mcp 执行相关操作时，读取当亲用户对应的 token 没有或者过期就打回。
  - 提案内容和处理都要持久化可追溯。
  - 利用 alibaba-ai 框架在处理流程中添加 hooks 
- {待补充}

## operator-cmp 

### 思路

- 用户的 token 作为执行钥匙，被记录且对其负责。
- {待完善}

# 架构{待完善优化}

- agents
  - multiple-agents
  - subagents
- 知识库、向量数据库
- 操作中心-MCP
- LLM proxy(router)
- LLM
- {待完善补充}

# 设计原则

## 安全域

# 实现

## assistant agent 主 agent

- 用户助手 agent, 用户交互式触发，针对对话识别用户意图，生成操作。 

## watchdog agent

- 后台巡视 agent,巡视矿卡的运行情况，按需生成操作

## 异常  subAgent
 
## 调度 subAgent

## xx subAgent{待完善补充}

