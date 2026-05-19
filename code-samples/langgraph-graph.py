# code-samples/langgraph-graph.py
# Pattern Demonstrated: Stateful Graph Orchestration
# Pipeline Position: The central orchestration framework compiling all nodes and driving state execution.

from typing import Any, Dict, List
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END

# --- SECTION 1: Graph State Definition ---

class GraphState(TypedDict):
    """The central state schema for the Anviksha analysis pipeline.
    
    DESIGN RATIONALE:
    Instead of passing complex variables across deep, nested function parameters,
    the StateGraph maintains a single, thread-safe, serializable state dictionary.
    Each node receives a read-only snapshot of this state and returns a dictionary
    containing only the keys it wants to update. LangGraph automatically applies
    these updates, ensuring clean data isolation.
    """
    raw_input: str
    input_type: str
    provider: str
    model: str
    api_key: Optional[str]
    run_id: str
    
    # Context frames produced by the Orchestrator
    orchestrator_context: Optional[Any]
    security_context: Optional[str]
    performance_context: Optional[str]
    architecture_context: Optional[str]
    
    # Outputs collected from specialist agents
    security_output: Optional[Any]
    performance_output: Optional[Any]
    architecture_output: Optional[Any]
    
    # Processed and validated metrics
    evaluation_results: List[Any]
    conflicts: List[Any]
    aggregated_report: Optional[Any]


# --- SECTION 2: Graph Node Functions ---

async def preprocess_node(state: GraphState) -> Dict[str, Any]:
    """Sanitizes raw inputs and removes metadata."""
    from app.utils.sanitize import sanitize_input
    sanitized = sanitize_input(state["raw_input"])
    return {"raw_input": sanitized}

async def orchestrator_node(state: GraphState) -> Dict[str, Any]:
    """Runs structural language and domain identification, generating context frames."""
    from app.agents.orchestrator import OrchestratorAgent
    agent = OrchestratorAgent(
        provider=state.get("provider", "groq"),
        model=state["model"],
        api_key=state.get("api_key"),
    )
    result = await agent.run(state["raw_input"])
    return {
        "orchestrator_context": result,
        "security_context": result.security_context,
        "performance_context": result.performance_context,
        "architecture_context": result.architecture_context,
    }

async def security_node(state: GraphState) -> Dict[str, Any]:
    """Executes the security agent, prepending its context frame if available.
    
    DESIGN DECISION: Isolation & Fallbacks.
    If the Orchestrator fails or isn't run, we pass the raw code directly to the
    specialist instead of crashing the pipeline. If the agent itself fails,
    we catch the exception locally, write the error to the state, and return
    an empty findings list, preventing a single failure from blocking other agents.
    """
    from app.agents.security import SecurityAgent
    agent = SecurityAgent(
        provider=state.get("provider", "groq"),
        model=state["model"],
        api_key=state.get("api_key"),
    )
    context = state.get("security_context")
    input_code = f"{context}\n\n---\n\n{state['raw_input']}" if context else state["raw_input"]

    try:
        result = await agent.run(input_code)
        return {"security_output": result}
    except Exception as e:
        return {"security_output": AgentOutput(agent="security", findings=[], error=str(e))}

# (performance_node and architecture_node implement this identical isolated try/catch pattern)


# --- SECTION 3: Stateful Graph Compilation ---

def build_analysis_graph() -> Any:
    """Builds and compiles the stateful LangGraph mapping.
    
    DESIGN RATIONALE:
    By declaring multiple edges pointing from a single node, LangGraph automatically
    handles parallel fan-outs (running Security, Performance, and Architecture
    specialists in parallel). By directing all three agent nodes into the sequential
    Evaluator, it enforces a clean synchronization join, executing the Evaluator
    only after all parallel agents have finished.
    """
    builder = StateGraph(GraphState)

    # 1. Register Graph Nodes
    builder.add_node("preprocess", preprocess_node)
    builder.add_node("orchestrator", orchestrator_node)
    builder.add_node("security", security_node)
    builder.add_node("performance", performance_node)
    builder.add_node("architecture", architecture_node)
    builder.add_node("evaluator", evaluator_node)
    builder.add_node("conflict_detection", conflict_detection_node)
    builder.add_node("aggregator", aggregator_node)

    # 2. Build Pipeline Connections (Edges)
    builder.add_edge(START, "preprocess")
    builder.add_edge("preprocess", "orchestrator")

    # Parallel Fan-Out
    builder.add_edge("orchestrator", "security")
    builder.add_edge("orchestrator", "performance")
    builder.add_edge("orchestrator", "architecture")

    # Parallel Fan-In / Join Boundary
    builder.add_edge("security", "evaluator")
    builder.add_edge("performance", "evaluator")
    builder.add_edge("architecture", "evaluator")

    # Sequential Post-Processing Path
    builder.add_edge("evaluator", "conflict_detection")
    builder.add_edge("conflict_detection", "aggregator")
    builder.add_edge("aggregator", END)

    # Compile the graph
    return builder.compile()

# Compile the graph once on startup
compiled_graph = build_analysis_graph()
