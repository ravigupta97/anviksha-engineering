# Product & Engineering Roadmap

This document outlines the current feature set of Anviksha V1 and details the planning, implementation strategy, and architectural principles for V2.

---

## 1. V1 Deliverables (Completed)

V1 successfully establishes the stateful multi-agent execution pipeline, persistence models, and authenticated streaming interfaces:

- [x] **Orchestrator Input Contextualization:** Initial structural pass prepending tailored context frames to specialist inputs, preventing domain bleed.
- [x] **Parallel Specialist Analysis:** Concurrent execution of Security, Performance, and Architecture agents using non-blocking LangGraph paths.
- [x] **Blind Quality Evaluation:** Unbiased confidence assessment scoring findings across Relevance, Accuracy, Actionability, and Severity.
- [x] **Real-Time Event Streaming:** Progressive rendering of findings via unidirectional Server-Sent Events (SSE).
- [x] **Conflict Detection:** Automatic scanning for logical contradictions and mutually exclusive instructions.
- [x] **On-Demand Judge Arbitration:** Post-hoc, user-triggered resolution of contradictions with a detailed technical compromise.
- [x] **Secure User Authentication:** Decoupled developer registration, session token signing, and cryptographic JWT validation via the AuthShield microservice.
- [x] **Persistent Session Storage:** Secure storage for runs, historical findings, and AES-256 encrypted provider keys.

---

## 2. V2 Engineering Specification

The next phase transitions Anviksha from a static file scanner to an intelligent, automated CI/CD pipeline integrated directly into the developer workflow.

| Feature Target | Scope & Technical Implementation Notes |
|---|---|
| **Intelligent Agent Routing** | Upgrades the Orchestrator pass. Instead of executing all three agents on every file, the Orchestrator determines which specialist is relevant (e.g., skip the Performance agent on a pure README markdown file) and routes the input dynamically using **LangGraph conditional edges**. |
| **Multi-Agent Debate Mode** | If the conflict detector flags a contradiction in-flight, the generating agents exchange rebuttals. Each specialist sees the opposing advice and refines its stance. If the conflict remains unresolved after 2 rounds, it is escalated to the Judge. This is implemented using rebuttal loops in the graph, preserving the core pipeline layout. |
| **Additional Specialists** | Introduces a **Clean Code Agent** (flags dead code, unused imports, magic numbers, and complex conditional branches) and a **Reliability Agent** (scans for missing catch blocks, uncaught exceptions, and missing retry patterns). Both follow the identical `BaseAgent` pattern and plug into the existing parallel fan-out. |
| **Git CI/CD Integration** | Webhook listener deployed to Render. Triggers a review automatically on GitHub `pull_request` events. Parses files changed in the diff and posts findings as inline pull request comments via the **GitHub Checks API**. |
| **Report Trend Dashboards** | Aggregates findings over time (e.g., tracking whether critical security findings decreased month-over-month) and exports historical CSV trends. |
| **IDE Plugin Integration** | A VS Code extension that calls the Anviksha API on active files. Displays findings as inline editor squiggles, using the `location` field (line ranges) already stored in the PostgreSQL database. |

---

## 3. V2 Architectural Principles

To ensure clean execution as we scale, all V2 development must adhere to three core architectural principles:

1. **Strict API Backwards Compatibility:** The core `/api/v1/` contract must continue to support legacy streaming clients without breaking changes.
2. **Provider-Agnostic Model Swaps:** Model replacements or upgrades (such as swapping the default model or upgrading the Judge) must be managed entirely through configuration variables (`AGENT_MODEL`, `JUDGE_MODEL`) in `config.py` rather than altering agent prompts or logic in code files.
3. **Additive Abstractions:** New specialists or debate features must be added by introducing new nodes and routing edges to the LangGraph compiled state machine rather than refactoring or modifying existing execution paths.
