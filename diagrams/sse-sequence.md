# Server-Sent Events (SSE) Sequence

This sequence diagram illustrates the asynchronous execution and event-push lifecycle of Anviksha. To minimize user-perceived latency, findings are progressively rendered in the Next.js UI as their respective nodes finish, rather than blocking the screen until the entire pipeline terminates.

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
