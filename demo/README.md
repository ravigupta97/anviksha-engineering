# Deliberately Flawed Demo Inputs

To show off Anviksha's multi-agent capabilities, this directory contains curated, realistic Python scripts containing common engineering vulnerabilities. 

Paste these inputs into the UI to demonstrate domain-specific analysis, blind confidence assessment, and conflict arbitration.

---

## What Each Input Triggers

| Sample Input File | Core concern targeted | Expected Pipeline Behavior |
|---|---|---|
| **[sql-injection.py](sample-inputs/sql-injection.py)** | SQL injection vulnerability & missing index. | **Security:** Critical vulnerability (raw string interpolation).<br/>**Performance:** Warning (missing query index on lookup).<br/>**Result:** Triggers a **logical conflict** because the Security fix (use parameterized bindings) and the Performance fix (indexing raw lookup query) must be balanced to maintain safety and speed. |
| **[n-plus-one.py](sample-inputs/n-plus-one.py)** | Classic N+1 database access pattern. | **Performance:** Critical bottleneck (executing subqueries inside loops).<br/>**Architecture:** Suggestion (missing database repository pattern).<br/>**Result:** Surfacings multiple concerns with zero logical conflicts. |
| **[tight-coupling.py](sample-inputs/tight-coupling.py)** | High coupling (God Class) & Synchronous I/O blocks. | **Architecture:** Critical flaw (violations of Single Responsibility Principle).<br/>**Performance:** Warning (executing synchronous database calls inside async endpoints).<br/>**Security:** Warning (missing input validation).<br/>**Result:** Cross-cutting concerns flagged across all three specialist agents, demonstrating extensive multi-agent capability. |

---

## Interpreting Your Results

When reviewing results:
1. **Severity Badges:**
   - **Critical (Red):** Severe issues that must be addressed immediately (e.g., security vulnerabilities or fatal performance bottlenecks).
   - **Warning (Yellow):** Flaws that can degrade system performance or complicate code maintenance over time.
   - **Suggestion (Blue):** Trivial style, cleanup, or refactoring enhancements.
2. **Confidence Evaluator Badges:** Look for confidence ratings. Low-confidence findings (average score below $0.6$) are kept but flagged with a warning icon, helping developers filter out minor LLM suggestions.
3. **Arbitration Card:** If a logical conflict is flagged, view the conflicting recommendations side-by-side and click "Ask Judge" to trigger the arbitrator, resolving the tradeoff with explicit reasoning.
