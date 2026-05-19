# code-samples/base-agent.py
# Pattern Demonstrated: Abstract Base Class & Robust LLM Gateway
# Pipeline Position: Base class inherited by all specialized and post-processing agents (Security, Performance, Architecture, Conflict, etc.).

import json
import asyncio
import time
from abc import ABC, abstractmethod
from typing import Literal, Any, Optional, cast
from app.models.schemas import AgentOutput, Finding
from app.utils.logging import get_logger
from app.utils.providers import get_llm_provider
from app.config import settings

logger = get_logger(__name__)

class BaseAgent(ABC):
    """Abstract base class for all specialized analysis agents.
    
    DESIGN RATIONALE:
    Instead of duplicating retry logic, client configuration, and JSON parsing across
    each agent, we isolate all LLM calling infrastructure here. Specialist agents
    only need to define their domain-specific system prompts and names.
    """

    def __init__(
        self,
        provider: str = "groq",
        api_key: Optional[str] = None,
        model: str = settings.AGENT_MODEL,
        max_retries: int = 3,
        base_delay: float = 1.0,
    ):
        self.provider = provider
        self.api_key = api_key
        self.model = model
        self.max_retries = max_retries
        self.base_delay = base_delay
        
        # DESIGN DECISION: Lazy client initialization.
        # We delay initializing the LLM client until the actual call is made,
        # ensuring that testing environments or fast server boot probes don't
        # fail due to missing or invalid credentials at startup.
        self._client: Optional[Any] = None

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """Returns the system prompt for this agent."""
        pass

    @property
    @abstractmethod
    def agent_name(self) -> Literal["security", "performance", "architecture", "orchestrator", "evaluator"]:
        """Returns the domain name of the agent."""
        pass

    @property
    def client(self) -> Any:
        """Lazy loader for LLM client."""
        if self._client is None:
            self._client = get_llm_provider(self.provider, self.api_key)
        return self._client

    async def _call_llm(self, prompt: str) -> str:
        """Raw LLM calling utility with fallback provider and exponential backoff retry.
        
        DESIGN RATIONALE:
        API rate limits (429) or transient provider outages should never crash a live review.
        This gateway automatically retries failed requests with exponential backoff. If the primary
        provider (e.g., Groq) is down, it seamlessly falls back to the secondary provider (Anthropic)
        using configured credentials, maintaining maximum session availability.
        """
        last_exception = None
        delay = self.base_delay
        start_time = time.perf_counter()

        # Dynamic provider fallback array
        providers_to_try = [(self.provider, self.api_key)]
        if self.provider.lower() == "groq" and settings.ANTHROPIC_API_KEY:
            providers_to_try.append(("anthropic", None))
        elif self.provider.lower() == "anthropic" and settings.GROQ_API_KEY:
            providers_to_try.append(("groq", None))

        for provider, api_key in providers_to_try:
            try:
                # Load key from settings if not supplied at run time
                if api_key is None:
                    api_key = getattr(settings, f"{provider.upper()}_API_KEY", None)

                if provider.lower() == "groq":
                    from groq import AsyncGroq
                    client = get_llm_provider("groq", api_key)
                    assert isinstance(client, AsyncGroq)
                    groq_response = await client.chat.completions.create(
                        model=self.model,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.2,
                        max_tokens=4000,
                    )
                    result = groq_response.choices[0].message.content or ""
                elif provider.lower() == "anthropic":
                    from anthropic import AsyncAnthropic
                    client = get_llm_provider("anthropic", api_key)
                    assert isinstance(client, AsyncAnthropic)
                    anthropic_response = await client.messages.create(
                        model=self.model,
                        max_tokens=4000,
                        system=self.system_prompt,
                        messages=[{"role": "user", "content": prompt}],
                    )
                    first_content = anthropic_response.content[0]
                    result = getattr(first_content, "text", str(first_content))
                else:
                    raise ValueError(f"Unknown provider: {provider}")

                duration = time.perf_counter() - start_time
                logger.info(
                    "llm_call_success",
                    agent=self.agent_name,
                    model=self.model,
                    provider=provider,
                    duration_seconds=round(duration, 3),
                )
                return result

            except Exception as e:
                error_str = str(e).lower()
                is_rate_limit = "rate_limit" in error_str or "429" in error_str
                is_server_error = "500" in error_str or "502" in error_str or "503" in error_str

                if is_rate_limit or is_server_error:
                    last_exception = e
                    logger.warning(
                        "llm_call_retry",
                        agent=self.agent_name,
                        provider=provider,
                        error=str(e),
                    )
                    await asyncio.sleep(delay)
                    delay *= 2
                    continue
                else:
                    last_exception = e
                    logger.error(
                        "llm_call_failed",
                        agent=self.agent_name,
                        provider=provider,
                        error=str(e),
                    )
                    break

        if last_exception:
            raise last_exception
        raise RuntimeError("LLM call failed without exception")

    async def run(self, input_code: str) -> AgentOutput:
        """Core execution loop with JSON structural repair.
        
        DESIGN RATIONALE:
        LLMs can sometimes wrap their JSON outputs in Markdown code blocks or return
        slightly malformed JSON syntax. Instead of immediately raising a validation error,
        this method parses and sanitizes the response. If the JSON remains malformed,
        it appends a corrective prompt and executes a single structural retry.
        """
        full_prompt = f"{self.system_prompt}\n\n{input_code}"

        try:
            response = await self._call_llm(full_prompt)
        except Exception as e:
            logger.error("agent_run_failed", agent=self.agent_name, error=str(e))
            return AgentOutput(
                agent=cast(Any, self.agent_name),
                findings=[],
                error=f"LLM call failed: {str(e)}",
            )

        for attempt in range(2):  # Initial attempt + 1 corrective retry
            try:
                # Strip markdown JSON fences if returned by the LLM
                json_str = response.strip()
                if json_str.startswith("```json"):
                    json_str = json_str[7:]
                if json_str.startswith("```"):
                    json_str = json_str[3:]
                if json_str.endswith("```"):
                    json_str = json_str[:-3]
                json_str = json_str.strip()

                parsed = json.loads(json_str)
                raw_findings = parsed.get("findings", [])

                findings_with_agent = []
                for f in raw_findings:
                    finding_text = f.get("finding") or f.get("description") or ""
                    fix_prose = f.get("fix_prose") or f.get("fix_suggestion") or "See fix_code for details."

                    # Enforce the minimum character constraint on fix_prose
                    if len(fix_prose) < 20:
                        fix_prose = f"{fix_prose} — see agent output for context."

                    finding = Finding(
                        severity=f.get("severity", "warning"),
                        finding=finding_text[:200] if finding_text else "Issue detected",
                        location=f.get("location") or f.get("line_number"),
                        fix_prose=fix_prose,
                        fix_code=f.get("fix_code"),
                        has_conflict=False,
                        agent=cast(Any, self.agent_name),
                    )
                    findings_with_agent.append(finding)

                output = AgentOutput(
                    agent=cast(Any, self.agent_name),
                    findings=findings_with_agent,
                )
                return output

            except (json.JSONDecodeError, KeyError) as e:
                if attempt == 0:
                    logger.warning(
                        "agent_json_parse_failed_retry",
                        agent=self.agent_name,
                        error=str(e),
                    )
                    # Corrective prompt retry mechanism
                    full_prompt += "\n\nIMPORTANT: Your previous response was not valid JSON. Please respond with ONLY valid JSON, no markdown formatting or explanation."
                    try:
                        response = await self._call_llm(full_prompt)
                    except Exception as llm_error:
                        return AgentOutput(
                            agent=cast(Any, self.agent_name),
                            findings=[],
                            error=f"JSON parsing failed: {str(e)}",
                        )
                else:
                    logger.error("agent_json_parse_exhausted", agent=self.agent_name, error=str(e))
                    return AgentOutput(
                        agent=cast(Any, self.agent_name),
                        findings=[],
                        error=f"Failed to parse JSON after retry: {str(e)}",
                    )

        return AgentOutput(
            agent=cast(Any, self.agent_name),
            findings=[],
            error="Unexpected error in run loop",
        )
