# code-samples/conflict-detection-agent.py
# Pattern Demonstrated: Adversarial Logical Scanning
# Pipeline Position: Post-processing node executing sequentially after the Evaluator Agent.

import json
from typing import Dict, Any, Literal
from app.agents.base import BaseAgent
from app.models.schemas import AgentOutput

class ConflictDetectionAgent(BaseAgent):
    """Conflict detection agent - identifies contradictions between agent findings.
    
    DESIGN RATIONALE:
    This specialist acts as an adversarial filter. By analyzing the flat list of findings,
    it identifies cases where agents recommend mutually exclusive or contradictory actions on the same
    component (e.g., Security says "do not cache" and Performance says "cache").
    """

    @property
    def system_prompt(self) -> str:
        return """You are a conflict detection agent. You receive the outputs of three code review agents (security, performance, architecture) and identify genuine contradictions — cases where two agents recommend opposite or mutually exclusive actions on the same component.

WHAT COUNTS AS A CONFLICT:
- Agent A says "cache this data" and Agent B says "never cache this data"
- Agent A says "add an index here" and Agent B says "remove this table entirely"
- Agent A says "use synchronous processing" and Agent B says "this must be async"
- Agent A says "encrypt this field" and Agent B says "this field must be plaintext for performance"

WHAT DOES NOT COUNT AS A CONFLICT:
- Two agents flagging different problems in the same function (they are not contradicting each other)
- One agent recommending an improvement and another agent not mentioning it
- Agents using different severity levels for unrelated issues

SEVERITY OF CONFLICT: Only flag contradictions where acting on one finding would violate the other.

OUTPUT RULES:
- Return ONLY a valid JSON object. No text before or after the JSON.
- If no genuine conflicts exist, return: {"conflicts": []}
- conflict_description must clearly state WHAT they disagree on, not just that they disagree.

JSON SCHEMA:
{
  "conflicts": [
    {
      "agent_a": "security" | "performance" | "architecture",
      "agent_b": "security" | "performance" | "architecture",
      "finding_a": { <finding object from agent_a> },
      "finding_b": { <finding object from agent_b> },
      "conflict_description": "<plain English: what action does agent_a recommend vs agent_b on what component>"
    }
  ]
}"""

    @property
    def agent_name(self) -> Literal["security"]:
        # We reuse the security client configuration for routing purposes
        return "security"

    async def run(  # type: ignore[override]
        self,
        security_output: AgentOutput,
        performance_output: AgentOutput,
        architecture_output: AgentOutput,
    ) -> Dict[str, Any]:
        """Runs the semantic conflict analysis over the three agent output findings.
        
        DESIGN DECISION: State Consolidation.
        We format and dump findings into a single structured payload. This isolates the
        detection analysis to a single context call, maximizing inference efficiency.
        """
        input_data = {
            "security": {
                "agent": "security",
                "findings": [f.model_dump() for f in security_output.findings],
            },
            "performance": {
                "agent": "performance",
                "findings": [f.model_dump() for f in performance_output.findings],
            },
            "architecture": {
                "agent": "architecture",
                "findings": [f.model_dump() for f in architecture_output.findings],
            },
        }

        user_prompt = f"""Analyze the following three agent outputs for conflicts:

{json.dumps(input_data, indent=2)}

Identify any genuine contradictions where the recommendations are mutually exclusive."""

        full_prompt = f"{self.system_prompt}\n\n{user_prompt}"

        try:
            # call_llm handles fallback pathways, retries, and API management
            response = await self._call_llm(full_prompt)
        except Exception as e:
            return {"conflicts": [], "error": str(e)}

        # Parse and sanitize response JSON
        for attempt in range(2):
            try:
                json_str = response.strip()
                if json_str.startswith("```json"):
                    json_str = json_str[7:]
                if json_str.startswith("```"):
                    json_str = json_str[3:]
                if json_str.endswith("```"):
                    json_str = json_str[:-3]
                json_str = json_str.strip()

                parsed = json.loads(json_str)
                return parsed

            except json.JSONDecodeError:
                if attempt == 0:
                    full_prompt += "\n\nReturn ONLY valid JSON, no markdown."
                    try:
                        response = await self._call_llm(full_prompt)
                    except Exception:
                        return {"conflicts": []}

        return {"conflicts": []}
