# Evaluator Design

In any multi-agent code analysis system, agents will produce findings of varying quality. Without a validation layer, the user is overwhelmed with a mix of high-confidence bugs and low-value style comments, eroding trust.

Anviksha introduces the **Evaluator Agent** — an independent, post-analysis node that calibrates finding quality and flags low-value critiques.

---

## 1. Why Evaluation Matters

Large language models are inherently prone to generating false positives, repeating generic style guides, or miscalibrating the severity of an issue (e.g., flagging a minor style issue as "critical"). 

If every finding is presented with equal weight, the developer experiences alert fatigue. However, silently filtering out low-scoring findings is also dangerous, as it can hide helpful context. Anviksha's Evaluator provides a compromise: it **rates and flags** findings. If a finding scores low, it is kept in the output stream but marked with a distinct warning badge.

---

## 2. The Four Dimensions of Calibration

The Evaluator Agent reviews each finding across **four quantitative dimensions** on a scale from $0.0$ to $1.0$:

| Dimension | Target Evaluation Metric |
|---|---|
| **Relevance** | Is this finding strictly in the generating agent's domain? (e.g., does a security agent's finding focus purely on security issues?) |
| **Accuracy** | Is this a legitimate code flaw, or is the agent misinterpreting the language, syntax, or context? |
| **Actionability** | Does the finding include a concrete, practical fix suggestion and correct code snippet? |
| **Severity Calibration** | Does the assigned severity tier (Critical, Warning, Suggestion) accurately reflect its business impact? |

### Composite Confidence Score:
A composite `confidence_score` is computed by calculating the arithmetic mean of these four dimensions:

$$\text{Confidence Score} = \frac{\text{Relevance} + \text{Accuracy} + \text{Actionability} + \text{Severity}}{4}$$

Findings scoring **below $0.6$** are automatically flagged as `is_low_confidence = true`.

---

## 3. Mitigating Self-Evaluation Bias

A primary challenge in LLM-driven evaluation is **self-evaluation bias**: models are notoriously lenient when grading their own outputs or outputs from the same model family. 

To mitigate this, Anviksha enforces **Blind Evaluation**:
1. All specialist outputs are compiled into a flat list of findings.
2. The agent names and source origins are stripped from the evaluator's input stream.
3. Each finding is assigned a generic reference index (e.g., `Index: 0`, `Index: 1`).
4. The Evaluator Agent reviews the flat index, grading each finding strictly on its content without knowing which agent generated it.

This blind evaluation prevents the model from showing favoritism and ensures a uniform, objective standard.

---

## 4. UI Decision: Transparency over Censorship

When a finding is marked as `is_low_confidence`, Anviksha **does not hide it**. 

Censoring low-confidence findings can prevent the user from seeing helpful edge-case suggestions. Instead, the UI displays these findings with a subtle gray warning badge and an explanatory note (e.g., *"Low Confidence: Actionability score is low"*). This empowers the developer to decide whether the suggestion is worth acting on.

---

## 5. Blind Key Mapping Algorithm

Because the Evaluator operates blindly, the backend must map evaluations back to their original generating agents. We implement a three-tiered lookup strategy:
1. **Index-Based Key matching:** Match `finding_ref` strictly by index key parsing (e.g., `performance:2` -> `AgentOutput.findings[2]`).
2. **Substring Containment matching:** Fall back to string containment lookups using finding prefixes.
3. **Word-Overlap Containment matching:** A fuzzy set-based overlap fallback to ensure that every evaluation is mapped correctly even if the model slightly alters the finding description.
