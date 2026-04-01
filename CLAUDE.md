# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Purpose

This is a **documentation repository** for the mining autonomous driving production dispatch platform's intelligent Q&A Agent architecture. It contains no source code — only architecture design documents and analysis artifacts.

## Document Inventory

- `arch.md` — Primary architecture specification (~570 lines). Covers: project background, multi-Agent design (智能问答/异常处理/数据分析 Agent), four-layer architecture, Tool Gateway, SSE event model, permission system, session/Redis design, draft state machine, RAG strategy, and rollout plan.
- `arch-summary.md` — Condensed summary of arch.md, organized by section.
- `arch-concepts.md` — Glossary of all technical concepts (对象槽位, Tool Gateway, confirm_then_execute, SSE events, 三层权限, etc.) with plain-language explanations.
- `arch-qa.md` — Analysis of five hot-topic questions: Spring AI Alibaba fit, multi-Agent problems, intent recognition design, Milvus/Embedding role, and Embedding model switch risks.

## Key Domain Context

- **Domain**: Mining autonomous driving dispatch (矿山自动驾驶生产调度)
- **Core Agent**: 智能问答 Agent — single entry point handling intent recognition, query, execution, and dispatch to specialized Agents
- **Tech stack references**: Spring AI Alibaba, Redis, Nacos, PostgreSQL, Kafka, Milvus, SSE (Server-Sent Events), LLM Gateway, RAG
- **Language**: All documents are in Chinese (Simplified)

## Working with These Documents

- `arch.md` contains sections marked "暂时无法在易控智驾文档外展示此内容" — these are tables/diagrams that couldn't be exported from the internal doc platform. Treat them as intentional gaps, not missing content.
- When analyzing arch.md, use context-mode tools (`ctx_execute_file`, `ctx_search`) rather than reading the full file directly — it exceeds 14K tokens.
- The previous session indexed arch.md into the context-mode FTS5 knowledge base with 37 sections.
