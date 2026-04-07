# now


## 当前架构

微服务工程集群基于 java8 的 spring boot 框架，基本按照领域拆分成多个 dubbo 服务，例如 device-center,user-center 等。服务之间通过 dubbo 相互调用。
dubbo 服务之上，有类似于 dubbo-to-http 的网关服务对外提供 http 服务。

# 思路 && spark

- 操作要有权限，独立一个服务 operator-mcp
  - 对上使用 mcp 协议与 LLM 交互
  - 对下使用 dubbo 调用各领域的服务
- 主要模块 monitor agent + user assistant agent
- 有结构化的知识库和接口文档
- 有完整审计日志和调用链路
- {待补充}

## operator

- 用户的 token 作为执行钥匙，被记录且对其负责。
- 
- {待完善}

# 架构{待完善优化}

- agents
- operator、knowledge base
- LLM

# 设计原则

## 安全域

# 实现

## watchdog agent

- 后台巡视 agent,巡视矿卡的运行情况，按需生成操作

## assistant agent

- 用户助手 agent, 用户交互式触发，针对对话识别用户意图，生成操作。 

