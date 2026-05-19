# Conflict Detection & Arbitration

Anviksha is designed to surface multi-dimensional engineering tradeoffs. Instead of muting conflicting priorities, the system exposes logical contradictions between security, performance, and architecture concerns and provides a post-hoc arbitration workflow.

This document details how logical conflicts are defined, detected in-flight, displayed to the user, and resolved by the Judge Agent.

---

## 1. What Counts as a Conflict?

A **logical conflict** occurs when two agents recommend mutually exclusive or contradictory actions on the same codebase component, meaning that acting on one recommendation physically violates the other.

### True Contradiction Examples (Will be Flagged):
- **Data Caching:** The Performance agent says: *"Cache this response payload aggressively for 10 minutes to reduce database queries."* The Security agent says: *"This payload contains sensitive user PII. Under compliance guidelines, this endpoint response must never be cached."*
- **Async Concurrency:** The Architecture agent says: *"Refactor this synchronous database access query to use non-blocking async query syntax."* The Performance agent says: *"The underlying driver lacks async compatibility. Refactoring this to async will create thread deadlock — keep this query synchronous and isolate it in a separate threadpool thread."*
- **Query Optimization:** The Performance agent says: *"Remove the join block and select columns individually to speed up execution."* The Security agent says: *"A structural column select bypasses row-level encryption. Keep the full structured join to enforce access filters."*

### Not a Conflict (Will NOT be Flagged):
- Two agents flagging different, unrelated issues inside the same function.
- One agent suggesting a refactoring fix while another agent does not comment on the component.
- Minor differences in assigned severity tiers for unrelated issues.

---

## 2. In-Flight Detection Strategy

The **Conflict Detection Agent** executes sequentially after the Evaluator. By analyzing the flat list of evaluated findings, it can skip low-confidence noise and focus strictly on legitimate, high-confidence issues.

The agent receives the findings from all three specialists in a structured JSON payload:

```json
{
  "security": { "findings": [...] },
  "performance": { "findings": [...] },
  "architecture": { "findings": [...] }
}
```

The system prompt explicitly defines what qualifies as a conflict and lists edge-cases to ignore, forcing the LLM to output a clean, structural JSON array containing the conflicting pairs and a clear description of the contradiction.

---

## 3. Side-by-Side UI Visualization

In the Next.js UI, conflicts are rendered as an intuitive **Side-by-Side Conflict Card**:

```
+-------------------------------------------------------------+
|                     CONTRADICTION DETECTED                  |
| "Cache policy disagreement on endpoint GET /api/v1/ledger"  |
+------------------------------+------------------------------+
|       SECURITY ADVICE        |       PERFORMANCE ADVICE     |
| Never cache response data    | Cache ledger query response  |
| because it contains PII.     | to avoid database latency.   |
| [Severity: Critical]         | [Severity: Warning]          |
+------------------------------+------------------------------+
|                     [ ASK JUDGE TO ARBITRATE ]              |
+-------------------------------------------------------------+
```

This visualization highlights the tradeoff clearly without forcing a premature decision, letting the developer understand both perspectives.

---

## 4. The Judge Agent Arbitration Workflow

If the developer is unsure which path to take, they can click "Ask Judge". This makes a fast POST request to `/api/v1/judge` containing the conflicting findings.

The **Judge Agent** arbitrates using a prioritized evaluation framework:
1. **Compliance and Security First:** Security trumps Performance unless a secure workaround is found.
2. **Workaround Identification:** The Judge searches for a solution that satisfies both goals (e.g., *"Filter out PII columns first, then cache the generic lookup data to protect privacy while improving performance"*).
3. **Actionable Implementation:** The Judge delivers a concrete code snippet demonstrating the compromise.

### Concrete Worked Example:

#### Input Security Finding:
- **Severity:** Critical
- **Finding:** *"Never cache this endpoint response — it contains user credit card credentials and PII."*
- **Location:** `app/routers/ledger.py:L142`

#### Input Performance Finding:
- **Severity:** Warning
- **Finding:** *"Cache this response aggressively to prevent N+1 database queries on ledger lookups."*
- **Location:** `app/routers/ledger.py:L140`

#### Judge Verdict & Reasoning:
- **Verdict Choice:** Security
- **Reasoning:** *"Compliance frameworks strictly forbid caching unencrypted PII on client gateways. However, the database bottleneck can be resolved by rewriting the ledger query to eagerly load relations before serialization, eliminating the N+1 loop without caching the endpoint response."*
- **Fix Code:**
```python
# Resolved Ledger Query
async def get_ledger(db: AsyncSession, user_id: UUID):
    # Eagerly load accounts and transactions in a single join query
    result = await db.execute(
        select(Ledger)
        .options(selectinload(Ledger.transactions))
        .where(Ledger.user_id == user_id)
    )
    return result.scalar_one_or_none()
```
This arbitration provides a clear, secure compromise, allowing developers to ship high-quality code safely.
