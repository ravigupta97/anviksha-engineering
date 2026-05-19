# System Architecture

Anviksha is built on a modern, decoupled **async Python FastAPI backend** and a responsive **Next.js 15 App Router frontend**. The core execution logic is modeled as a stateful, compiled graph using **LangGraph**, persisting run states and findings to a relational **PostgreSQL** database. 

This document details the engineering patterns, service separations, and performance strategies used to construct Anviksha.

---

## 1. Service Separation

The architecture is strictly split into three isolated services communicating over standard APIs:

1. **Next.js Frontend:** A client-facing Next.js 15 application deployed to Vercel. It implements responsive UI primitives (using Tailwind CSS and shadcn/ui), handles stateful progressive rendering of findings streamed via Server-Sent Events (SSE), and delegates user registration and sign-in requests directly to the AuthShield endpoint.
2. **FastAPI Engine:** An asynchronous Python REST service deployed to Render. It validates incoming review requests, drives stateful LangGraph execution steps, interacts with the PostgreSQL storage layer via async SQLAlchemy sessions, and performs in-flight validation of structured JSON outputs.
3. **AuthShield Microservice:** A centralized, independent authorization server. The Anviksha backend delegates token validation and user registration entirely to this microservice, using a shared JWT cryptographic key. The FastAPI application verifies token signatures and extracts the `user_id` without maintaining local password hashes or session stores.

---

## 2. Full Pipeline Flow

The execution cycle begins when the client submits code for review. The diagram below illustrates how raw inputs traverse the backend system:

```mermaid
flowchart TD
    subgraph Inputs [Input Channels]
        Snippet[Snippet Submission]
        Text[Text Area Input]
        File[File Upload Input]
    end

    subgraph Interface [FastAPI Layer]
        API_Analyze[POST /api/v1/analyze]
        API_Judge[POST /api/v1/judge]
    end

    subgraph Graph [LangGraph Orchestration Pipeline]
        Preprocess[preprocess_node<br/>Sanitizes input]
        Orchestrator[orchestrator_node<br/>Generates Context Frames]
        
        Security[security_node<br/>SecurityAgent Specialist]
        Performance[performance_node<br/>PerformanceAgent Specialist]
        Architecture[architecture_node<br/>ArchitectureAgent Specialist]
        
        Evaluator[evaluator_node<br/>Blind confidence scoring]
        Conflict[conflict_detection_node<br/>Mutual exclusivity scan]
        Aggregator[aggregator_node<br/>Deduplicates & Packages]
    end

    subgraph ClientPush [Progressive SSE Client Stream]
        SSE[SSE Stream Generator]
    end

    subgraph Persistence [Storage Layer]
        DB[(PostgreSQL Run History)]
    end

    subgraph Arbitrator [On-Demand Resolution]
        Judge[JudgeAgent Specialist]
    end

    %% Input paths
    Snippet --> API_Analyze
    Text --> API_Analyze
    File --> API_Analyze

    %% Core graph execution sequence
    API_Analyze --> Preprocess
    Preprocess -->|Sanitized Input| Orchestrator
    
    %% Parallel fan-out with context frames
    Orchestrator -->|Security Context Frame| Security
    Orchestrator -->|Performance Context Frame| Performance
    Orchestrator -->|Architecture Context Frame| Architecture

    %% Parallel fan-in to sequential nodes
    Security -->|Findings List| Evaluator
    Performance -->|Findings List| Evaluator
    Architecture -->|Findings List| Evaluator

    %% Sequential evaluation & post-processing
    Evaluator -->|Confidence Evaluated Findings| Conflict
    Conflict -->|Contradictions & Findings| Aggregator

    %% Real-time Server-Sent Events push
    Preprocess -.->|preprocess_complete| SSE
    Orchestrator -.->|orchestrator_context| SSE
    Security -.->|agent_result security| SSE
    Performance -.->|agent_result performance| SSE
    Architecture -.->|agent_result architecture| SSE
    Evaluator -.->|evaluation_complete| SSE
    Conflict -.->|conflict_detected| SSE
    Aggregator -.->|run_complete| SSE
    
    %% DB Persistence
    Aggregator -->|Store run, findings & conflicts| DB

    %% Separate On-Demand Judge Execution path
    API_Judge -->|Submit conflicting findings| Judge
    Judge -->|Arbitrate & return verdict| API_Judge
```

---

## 3. LangGraph Orchestration & Parallel Execution

Rather than chaining LLM calls in simple, sequential scripts (which increases overall request duration and lacks clear step tracking), Anviksha models its pipeline as a compiled **StateGraph**.

```mermaid
flowchart TD
    START([START])
    Preprocess[preprocess_node]
    Orchestrator[orchestrator_node]
    
    Security[security_node]
    Performance[performance_node]
    Architecture[architecture_node]
    
    Evaluator[evaluator_node]
    Conflict[conflict_detection_node]
    Aggregator[aggregator_node]
    END([END])

    %% Entry nodes
    START --> Preprocess
    Preprocess --> Orchestrator

    %% Parallel fan-out
    Orchestrator --> Security
    Orchestrator --> Performance
    Orchestrator --> Architecture

    %% Parallel fan-in (Join edge)
    Security --> Evaluator
    Performance --> Evaluator
    Architecture --> Evaluator

    %% Sequential post-processing
    Evaluator --> Conflict
    Conflict --> Aggregator
    Aggregator --> END

    %% On-demand Judge (runs outside graph lifespan)
    subgraph OnDemand [POST /api/v1/judge]
        JudgeNode[judge_agent_inference]
    end
```

### Performance Advantages:
- **Asynchronous Concurrency:** The Security, Performance, and Architecture nodes execute concurrently on non-blocking graph edges.
- **State Isolation:** Each node receives a read-only snapshot of the shared `GraphState` TypedDict and returns only the keys it modifies. This prevents in-place mutation side-effects and simplifies debug tracing.
- **Robust Exception Barriers:** A failure or structural schema breakdown inside one agent is captured by local try/except blocks in its respective node. The error is written to the state, and the graph safely proceeds with the remaining agents, preventing a single rate-limit error or formatting issue from crashing the entire user session.

---

## 4. Server-Sent Events (SSE) Streaming Strategy

Because multi-agent analysis involves running multiple large LLM queries, waiting for all nodes to complete before showing any results creates a blocking, slow user experience. 

Anviksha uses **Server-Sent Events (SSE)** via `sse-starlette` to stream findings progressively. As soon as the Security agent completes, its findings are serialized to JSON and pushed to the client immediately. The Next.js application catches these events and appends them to a stateful UI list in real time, making the application feel responsive and alive.

```mermaid
sequenceDiagram
    autonumber
    actor User as Engineer (UI)
    participant Client as Next.js App
    participant API as FastAPI Router
    participant Graph as LangGraph Core
    participant Agent as Specialist Agents
    participant Eval as EvaluatorAgent
    participant Conf as ConflictDetectionAgent

    User->>Client: Pastes code + clicks "Analyze"
    Client->>API: HTTP POST /api/v1/analyze
    activate API
    API-->>Client: HTTP 200 OK (EventSource connection established)
    
    API->>Graph: Invoke StateGraph(GraphState)
    activate Graph
    
    Graph-->>API: preprocess_node completes
    API-->>Client: SSE Event: preprocess_complete {"input_length": N}

    Graph-->>API: orchestrator_node completes
    API-->>Client: SSE Event: orchestrator_context {"language": "...", "framework": "...", "domain": "..."}

    Note over Graph, Agent: Fan-out: Parallel execution of 3 specialists starts
    
    par Security Agent
        Graph->>Agent: Run SecurityAgent with Security Context Frame
        Agent-->>Graph: Return findings
        Graph-->>API: security_node completes
        API-->>Client: SSE Event: agent_result {"agent": "security", "findings": [...]}
    and Performance Agent
        Graph->>Agent: Run PerformanceAgent with Performance Context Frame
        Agent-->>Graph: Return findings
        Graph-->>API: performance_node completes
        API-->>Client: SSE Event: agent_result {"agent": "performance", "findings": [...]}
    and Architecture Agent
        Graph->>Agent: Run ArchitectureAgent with Architecture Context Frame
        Agent-->>Graph: Return findings
        Graph-->>API: architecture_node completes
        API-->>Client: SSE Event: agent_result {"agent": "architecture", "findings": [...]}
    end

    Note over Graph, Eval: Fan-in: Combine findings for evaluation

    Graph->>Eval: Run EvaluatorAgent (blind confidence scoring)
    Eval-->>Graph: Return evaluations
    Graph-->>API: evaluator_node completes
    API-->>Client: SSE Event: evaluation_complete {"total_evaluated": X, "low_confidence_count": Y}

    Graph->>Conf: Run ConflictDetectionAgent (mutual exclusivity scan)
    Conf-->>Graph: Return contradictions
    Graph-->>API: conflict_detection_node completes
    API-->>Client: SSE Event: conflict_detected {"conflict_count": Z}

    Graph-->>API: aggregator_node completes (Persists to DB)
    deactivate Graph
    API-->>Client: SSE Event: run_complete {"report": {...}}
    deactivate API

    Note over User, Client: Optional: User views side-by-side conflict and clicks "Ask Judge"
    Client->>API: POST /api/v1/judge {"conflict": {...}}
    activate API
    API->>API: Execute JudgeAgent (arbitrate contradictions)
    API-->>Client: Return JudgeVerdict {"verdict": "...", "reasoning": "..."}
    deactivate API
    Client->>User: Renders Judge Verdict & reasoning card
```


---

## 5. Persistent Storage Layer

To support run history dashboards and allow manual Judge arbitration, all run metadata, structured findings, and logical conflicts are persisted in a PostgreSQL relational schema. 

We use **SQLAlchemy 2.0 Async Session** mapping with a non-blocking `asyncpg` driver to execute database I/O. This ensures that slow database queries or concurrent user writes never block FastAPI's primary single-threaded event loop.

---

## 6. Cold Start and Deployment Details

The system is deployed across three environments:
1. **Frontend (Vercel):** Hot-reloaded React codebases directly talking to the Render API endpoints.
2. **Backend (Render):** Deployed on a free-tier instance. The free tier automatically sleeps after 15 minutes of inactivity. When a slept server receives its first request, a ~30-second "cold start" latency is expected as Render rebuilds and starts the uvicorn process. To mitigate db connection drops after waking up, the SQLAlchemy engine is configured with `pool_pre_ping=True` to test connections in-flight.
3. **Database (Neon Postgres):** Deployed on Neon serverless PostgreSQL, configured with `pool_recycle=300` to recycle stale database connections safely.
