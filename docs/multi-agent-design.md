# Multi-Agent Design

The architectural core of Anviksha is a highly specialized, multi-agent cooperative system. Instead of asking a single massive language model to analyze a script for all flaws simultaneously, we break the review process down into isolated, specialized agents. 

This document details the engineering principles, prompt steering strategies, and adversarial mechanics behind the multi-agent design.

---

## 1. The Problem with Single-Agent Reviews

A single LLM code reviewer suffers from three structural flaws in production systems:
1. **Domain Bleed:** When asked to review a script for security, performance, and formatting simultaneously, the model's attention is split. It often focuses heavily on trivial style improvements (such as naming conventions or formatting) while missing critical architectural anti-patterns or deep, subtle security vulnerabilities.
2. **Untraceable Priority:** It is highly difficult to programmaticly extract which concern (security, speed, or structure) drove which recommendation.
3. **No Support for Trade-offs:** Single models cannot easily model conflicting choices. For example, if a model recommends caching user data for performance, it often misses that this directly introduces a security leak of sensitive PII.

---

## 2. Scope Isolation (Specialist Agents)

Anviksha solves this by executing three completely isolated specialist agents in parallel:

- **Security Agent:** Instructed strictly to scan for OWASP Top 10 vulnerabilities, API credential leaks, injection targets, insecure cryptographic algorithms, and authorization bypasses.
- **Performance Agent:** Focused entirely on memory overhead, database N+1 loop structures, sync I/O blocking inside async loops, caching opportunities, and CPU bottlenecks.
- **Architecture Agent:** Critiques the design patterns, SOLID principles, God class divisions, tight coupling, and structural clean code formatting.

Each specialist's system prompt enforces a **strict boundary**: they are told exactly what concerns are *out-of-scope* for their role. For example, the Security agent is explicitly instructed to ignore slow queries or structural code layouts. This boundary prevents duplicate findings and ensures clean input signals for conflict detection.

---

## 3. Orchestrator Contextualization

Passing raw code directly to specialist agents often leads to superficial reviews. The **Orchestrator Agent** acts as an initial structural analyzer. It processes the raw input code and produces a **Context Frame**:

```
[Orchestrator Context Frame]
Target Language: Python
Framework Identified: FastAPI + SQLAlchemy Async
Domain Categorization: Financial Ledger / Transaction System
```

This context frame is prepended directly to the specialist inputs. By steering the Security agent with the domain target (e.g., *"This is a financial ledger using asynchronous SQLAlchemy"*), it knows to look specifically for transaction isolation bugs rather than generic script vulnerabilities. This contextualization tightens findings and aligns specialist priorities.

---

## 4. Parallel Execution Lifecycle

The specialists run concurrently in LangGraph:

```
[Orchestrator Node completes]
           |
     +-----+-----+
     |     |     |
  [Sec]  [Perf] [Arch]
     |     |     |
     +-----+-----+
           |
    [Evaluator Node starts]
```

To prevent one agent's slow API call from blocking the others, uvicorn coordinates parallel tasks using standard async/await coroutines. If an agent crashes or returns invalid JSON schema layouts, the parent node intercepts the error, writes a traceback string to `GraphState`, and continues the graph cleanly, maintaining high application uptime.

---

## 5. Adversarial Design Philosophy

By decoupling agents into specialized silos, we deliberately set them up to have conflicting goals. This creates an **adversarial balance** that mirrors real-world engineering debates:
- The **Performance Agent** wants to cache response payloads aggressively.
- The **Security Agent** forbids caching response payloads containing PII.
- The **Architecture Agent** wants to introduce structured layer patterns.
- The **Performance Agent** worries about extra functional call stack overhead.

By exposing these contradictions (rather than muting them into a single, generic voice), Anviksha maps out the actual trade-offs of a codebase, helping engineers make informed, high-quality decisions.

---

## 6. The Post-Hoc Judge Mechanism

In V1, conflict resolution is designed as a **post-hoc, on-demand Judge**. 

Instead of letting agents debate in a loop in-flight (which blocks client response streams for up to 30-40 seconds and wastes thousands of tokens), the system generates the report immediately. If the user views a logical conflict, they can click "Ask Judge" to trigger a separate `POST /api/v1/judge` request. 

The **Judge Agent** acts as a post-hoc arbitrator. It reviews both conflicting arguments, prioritizes critical requirements (e.g., Security trumps Performance unless a secure workaround is found), and delivers a clear verdict and comprehensive, logic-based technical reasoning.
