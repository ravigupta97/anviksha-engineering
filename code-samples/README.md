# Curated Code Samples

This directory contains production-ready, highly annotated code samples extracted directly from the core **Anviksha FastAPI backend**. 

These samples demonstrate our architectural design patterns, AI integration practices, and streaming execution pipelines.

---

## Code Pattern Index

| Code Sample | Pattern Demonstrated | Description |
|---|---|---|
| **[base-agent.py](base-agent.py)** | Abstract Base Class & Robust LLM Gateway | The base agent inherited by all specialist agents. Demonstrates lazy-loading clients, multi-provider fallbacks (Groq -> Anthropic), exponential rate-limit backoff retries, and in-flight JSON schema repair. |
| **[langgraph-graph.py](langgraph-graph.py)** | Stateful Graph Orchestration | Compiles the stateful LangGraph mapping. Demonstrates parallel specialist nodes, sequential post-processing pipelines, join boundaries, and non-mutating state changes. |
| **[evaluator-agent.py](evaluator-agent.py)** | Blind LLM-as-a-Judge Evaluation | Implements blind confidence assessment. Gathers findings across agents, evaluates them across four quality scales (without knowing which agent generated what), and calculates a composite score. |
| **[conflict-detection-agent.py](conflict-detection-agent.py)** | Adversarial Logical Scanning | Semantic parsing of agent outputs. Compares findings to identify mutually exclusive instructions on the same components. |
| **[sse-streaming.py](sse-streaming.py)** | Asynchronous Generator Streaming | The Event Generator in the FastAPI router. Manages real-time, non-blocking Server-Sent Events (SSE) streaming state changes progressively as they complete. |

---

## Structural Guidelines Applied In These Samples:
1. **Strict Type Safety:** Fully typed signatures utilizing standard Python type-hint conventions.
2. **Robust Exception Handling:** Local catch-and-log blocks in every graph node to prevent a single agent failure from crashing the pipeline.
3. **Structured Logging:** Utilizes `structlog` to output clean, machine-readable runtime telemetry rather than generic console print statements.
