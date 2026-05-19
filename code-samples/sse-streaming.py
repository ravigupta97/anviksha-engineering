# code-samples/sse-streaming.py
# Pattern Demonstrated: Asynchronous Generator Streaming
# Pipeline Position: API route controller starting analysis runs and streaming progressive graph state outputs to the client.

import json
import uuid
from typing import AsyncGenerator, Optional
from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse
from app.orchestrator.graph import graph
from app.orchestrator.state import GraphState
from app.models.schemas import AnalyzeRequest
from app.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1")

async def analyze_events(
    request: AnalyzeRequest,
    user_id: Optional[str],
    session_id: str,
) -> AsyncGenerator[str, None]:
    """Generates Server-Sent Events (SSE) from the compiled LangGraph.
    
    DESIGN RATIONALE:
    Instead of waiting for the entire multi-agent graph to terminate (which would take
    5-10 seconds and result in a boring UI loading state), this generator utilizes
    LangGraph's async stream (`astream`). As each node completes, it yields its output
    instantly. The generator serializes this data into formal Server-Sent Event formatting,
    allowing the client to render findings progressively.
    """
    run_id = str(uuid.uuid4())
    
    # Send start marker event
    yield json.dumps({"event": "run_start", "data": {"run_id": run_id}}) + "\n"

    # Initialize graph state
    initial_state: GraphState = {
        "input_type": request.input_type,
        "raw_input": request.code,
        "user_id": user_id or "demo",
        "session_id": session_id,
        "run_id": run_id,
        "orchestrator_context": None,
        "security_context": None,
        "performance_context": None,
        "architecture_context": None,
        "security_output": None,
        "performance_output": None,
        "architecture_output": None,
        "security_error": None,
        "performance_error": None,
        "architecture_error": None,
        "evaluation_results": [],
        "conflicts": [],
        "aggregated_report": None,
        "provider": request.provider,
        "model": request.model or "llama-3.3-70b-versatile",
        "api_key": request.api_key,
    }

    try:
        # Stream graph outputs asynchronously chunk-by-chunk
        async for chunk in graph.astream(initial_state):
            for node_name, node_output in chunk.items():
                # Apply node updates onto state snapshot in-flight
                initial_state.update(node_output)

                # Map executed graph nodes to distinct, structured SSE event names
                if node_name == "preprocess":
                    yield json.dumps({
                        "event": "preprocess_complete",
                        "data": {"input_length": len(node_output.get("raw_input", ""))}
                    }) + "\n"

                elif node_name == "orchestrator":
                    context = node_output.get("orchestrator_context")
                    if context:
                        yield json.dumps({
                            "event": "orchestrator_context",
                            "data": {
                                "language": context.language,
                                "framework": context.framework,
                                "domain": context.domain,
                            }
                        }) + "\n"

                elif node_name == "security":
                    output = node_output.get("security_output")
                    if output:
                        yield json.dumps({
                            "event": "agent_result",
                            "data": {
                                "agent": "security",
                                "findings": [f.model_dump() for f in output.findings],
                                "error": node_output.get("security_error"),
                            }
                        }) + "\n"

                elif node_name == "performance":
                    output = node_output.get("performance_output")
                    if output:
                        yield json.dumps({
                            "event": "agent_result",
                            "data": {
                                "agent": "performance",
                                "findings": [f.model_dump() for f in output.findings],
                                "error": node_output.get("performance_error"),
                            }
                        }) + "\n"

                elif node_name == "architecture":
                    output = node_output.get("architecture_output")
                    if output:
                        yield json.dumps({
                            "event": "agent_result",
                            "data": {
                                "agent": "architecture",
                                "findings": [f.model_dump() for f in output.findings],
                                "error": node_output.get("architecture_error"),
                            }
                        }) + "\n"

                elif node_name == "evaluator":
                    evaluations = node_output.get("evaluation_results", [])
                    low_count = sum(1 for e in evaluations if e.is_low_confidence)
                    yield json.dumps({
                        "event": "evaluation_complete",
                        "data": {"total_evaluated": len(evaluations), "low_confidence_count": low_count}
                    }) + "\n"

                elif node_name == "conflict_detection":
                    conflicts = node_output.get("conflicts", [])
                    yield json.dumps({
                        "event": "conflict_detected",
                        "data": {"conflict_count": len(conflicts)}
                    }) + "\n"

                elif node_name == "aggregator":
                    report = node_output.get("aggregated_report")
                    if report:
                        yield json.dumps({
                            "event": "run_complete",
                            "data": {"report": report.model_dump()}
                        }) + "\n"

    except Exception as e:
        logger.error("sse_generator_error", run_id=run_id, error=str(e))
        yield json.dumps({"event": "error", "data": {"message": f"Pipeline failed: {str(e)}"}}) + "\n"


@router.post("/analyze")
async def analyze_code(request: AnalyzeRequest):
    """Router endpoint initiating the Server-Sent Event stream.
    
    DESIGN RATIONALE:
    Instead of returning a standard JSON object, we wrap our async generator inside
    an EventSourceResponse. This keeps the HTTP connection open, allowing us to
    push chunked analysis events progressively using clean, standardized streaming.
    """
    event_generator = analyze_events(request, user_id=None, session_id="local_session")
    return EventSourceResponse(event_generator)
