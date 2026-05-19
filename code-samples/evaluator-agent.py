# code-samples/evaluator-agent.py
# Pattern Demonstrated: Blind LLM-as-a-Judge Evaluation
# Pipeline Position: Post-processing join node running sequentially after all parallel specialist agents complete.

import json
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from app.models.schemas import EvaluationResult, EvaluationOutput, AgentOutput, Finding
from app.utils.logging import get_logger
from app.config import settings

logger = get_logger(__name__)

class EvaluatorAgent:
    """Evaluator agent that scores each finding on four dimensions and flags low-confidence ones.
    
    DESIGN RATIONALE:
    To protect code reviews from large model halluncinations or minor, non-actionable
    style suggestions, the Evaluator validates findings blindly, scoring each along
    four strict quality dimensions.
    """

    SYSTEM_PROMPT = """You are an evaluator agent that scores code review findings.

Rate each finding on four scales (0.0 to 1.0):
- relevance_score: Is this in the agent's domain?
- accuracy_score: Is this a real issue?
- actionability_score: Is the fix concrete?
- severity_calibration_score: Does severity match impact?

If average < 0.6, set is_low_confidence: true

CRITICAL RULE for finding_ref:
- Each finding block shows "Index: N" and "Agent: <name>".
- Set finding_ref to "<name>:<N>" — replace <name> with the ACTUAL agent name from the finding (security, performance, or architecture) and <N> with the EXACT integer index.
- Example: if Agent is "performance" and Index is 2, finding_ref must be "performance:2".
- DO NOT use the word "agent" literally. The word "agent" in the format is a placeholder — always replace it with the real agent name.

Return ONLY this JSON format:
{"evaluations": [{"finding_ref": "<agentname>:<index>", "agent": "security|performance|architecture", "relevance_score": 0.0, "accuracy_score": 0.0, "actionability_score": 0.0, "severity_calibration_score": 0.0, "confidence_score": 0.0, "is_low_confidence": false, "evaluator_note": null}]}"""

    def __init__(self, provider: str = "groq", api_key: Optional[str] = None):
        self.provider = provider
        self.api_key = api_key
        self.model = settings.AGENT_MODEL
        
    def _build_evaluator_input(self, all_findings: List[Finding], all_agents: List[AgentOutput]) -> str:
        """Compiles all findings into a generic flat index to enforce blind evaluation.
        
        DESIGN DECISION: Blind evaluation (Mitigates Self-Evaluation Bias).
        We strip the actual model markers or generating agent identities, presenting
        a flat list of items keyed by a generic index. The Evaluator scores each item
        objectively without developer-bias or model-lenience skewing the results.
        """
        findings_text = []
        idx = 0
        for agent_output in all_agents:
            for finding in agent_output.findings:
                findings_text.append(
                    f"Index: {idx}\n"
                    f"Agent: {agent_output.agent}\n"
                    f"Finding: {finding.finding[:150]}\n"
                    f"Location: {finding.location or 'N/A'}\n"
                    f"Severity: {finding.severity}"
                )
                idx += 1
        return "\n\n---\n\n".join(findings_text)

    def _normalize_evaluation(self, ev: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Validates and normalizes the parsed JSON output from the LLM.
        
        DESIGN DECISION: Fault Tolerance.
        Since LLMs can sometimes alter field names or return variations of camelCase/snake_case,
        this utility uses dynamic field-mappings to translate properties back to our exact
        Pydantic v2 schemas.
        """
        normalized = {}
        
        # Field mapping definitions for elastic key matching
        field_mappings = {
            "finding_ref": ["finding_ref", "findingRef"],
            "agent": ["agent", "Agent"],
            "relevance_score": ["relevance_score", "relevance", "RelevanceScore"],
            "accuracy_score": ["accuracy_score", "accuracy", "AccuracyScore"],
            "actionability_score": ["actionability_score", "actionability", "ActionabilityScore"],
            "severity_calibration_score": ["severity_calibration_score", "severity_calibration", "SeverityCalibrationScore"],
            "confidence_score": ["confidence_score", "confidence", "ConfidenceScore"],
            "is_low_confidence": ["is_low_confidence", "isLowConfidence", "low_confidence"],
            "evaluator_note": ["evaluator_note", "note", "evaluatorNote"]
        }

        for target_field, possible_names in field_mappings.items():
            for name in possible_names:
                if name in ev:
                    value = ev[name]
                    if target_field == "is_low_confidence":
                        normalized[target_field] = bool(value)
                    elif "score" in target_field:
                        normalized[target_field] = float(value) if value is not None else 0.5
                    else:
                        normalized[target_field] = value
                    break

        # Calculate confidence score if missing
        if "confidence_score" not in normalized:
            scores = [
                normalized.get("relevance_score", 0.5),
                normalized.get("accuracy_score", 0.5),
                normalized.get("actionability_score", 0.5),
                normalized.get("severity_calibration_score", 0.5)
            ]
            normalized["confidence_score"] = sum(scores) / len(scores) if scores else 0.5

        # Enforce threshold boundary
        if "is_low_confidence" not in normalized:
            normalized["is_low_confidence"] = normalized.get("confidence_score", 0.5) < 0.6

        return normalized
