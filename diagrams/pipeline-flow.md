# System Pipeline Flow

This diagram illustrates the end-to-end execution flow of an Anviksha code analysis session. It maps out how a raw code submission traverses input parsing, orchestrator steering, parallel specialist evaluation, conflict detection, real-time SSE push, and the separate, on-demand Judge path.

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
