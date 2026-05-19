# API Reference

Anviksha is built on a clean, API-first architecture. The backend exposes endpoints for starting code analysis, arbitrating contradictions on-demand, fetching historical runs, and exporting reports.

---

## 1. Analysis Endpoint

### `POST /api/v1/analyze`
Starts the multi-agent code analysis pipeline and streams findings in real time via Server-Sent Events (SSE).

**Authentication:** Optional. If an `Authorization: Bearer <token>` header is present, the run is linked to the user's AuthShield account.

#### Request Body:
```json
{
  "input_type": "snippet",
  "code": "def process(user_input):\n    query = f\"SELECT * FROM users WHERE name = '{user_input}'\"\n    return db.execute(query)",
  "provider": "groq",
  "model": "llama-3.3-70b-versatile",
  "api_key": null
}
```

#### Response Stream Sequence (SSE):

##### Event 1: `run_start`
Fires immediately when the session is initialized.
```event
event: run_start
data: {"run_id": "b83ef31d-b8d9-482f-89c1-4c12ea8f12a8"}
```

##### Event 2: `preprocess_complete`
Fires after input validation and prompt sanitization.
```event
event: preprocess_complete
data: {"input_length": 112}
```

##### Event 3: `orchestrator_context`
Fires after the Orchestrator identifies the domain targets.
```event
event: orchestrator_context
data: {"language": "python", "framework": "none", "domain": "database query"}
```

##### Event 4: `agent_start`
Fires as each specialist agent begins execution.
```event
event: agent_start
data: {"agent": "security"}
```

##### Event 5: `agent_result`
Fires when an agent completes, delivering its findings.
```event
event: agent_result
data: {
  "agent": "security",
  "findings": [
    {
      "severity": "critical",
      "finding": "SQL Injection vulnerability via raw string format.",
      "location": "Line 2: f\"SELECT * FROM...\"",
      "fix_prose": "Use parameterized query parameters to prevent user injection.",
      "fix_code": "db.execute(\"SELECT * FROM users WHERE name = :name\", {\"name\": user_input})",
      "has_conflict": false
    }
  ],
  "error": null
}
```

##### Event 6: `evaluation_complete`
Fires after the blind confidence assessment finishes.
```event
event: evaluation_complete
data: {"total_evaluated": 1, "low_confidence_count": 0}
```

##### Event 7: `conflict_detected`
Fires after the logical conflict scanner runs.
```event
event: conflict_detected
data: {"conflict_count": 0}
```

##### Event 8: `run_complete`
Fires when the pipeline finishes, returning the final aggregated report.
```event
event: run_complete
data: {
  "report": {
    "run_id": "b83ef31d-b8d9-482f-89c1-4c12ea8f12a8",
    "status": "completed",
    "total_findings": 1,
    "critical": 1,
    "warnings": 0,
    "suggestions": 0,
    "conflict_count": 0,
    "findings": [...],
    "conflicts": []
  }
}
```

---

## 2. On-Demand Judge Endpoint

### `POST /api/v1/judge`
Arbitrates logical conflicts between two findings, returning a verdict and technical reasoning.

**Authentication:** Required.

#### Request Body:
```json
{
  "run_id": "b83ef31d-b8d9-482f-89c1-4c12ea8f12a8",
  "conflict": {
    "agent_a": "security",
    "agent_b": "performance",
    "finding_a": {
      "severity": "critical",
      "finding": "Do not cache response containing sensitive transaction PII."
    },
    "finding_b": {
      "severity": "warning",
      "finding": "Cache ledger query responses to reduce DB load."
    },
    "conflict_description": "Cache policy disagreement on transaction endpoints."
  }
}
```

#### Response Body:
```json
{
  "conflict_id": "d13ef31d-c8d9-482f-89c1-4c12ea8f12a8",
  "verdict": "security",
  "reasoning": "Compliance frameworks strictly forbid caching unencrypted PII. However, database latency can be resolved by optimizing query indexes and eager-loading relations, eliminating the N+1 loop without caching the endpoint response.",
  "actionable_compromise": "..."
}
```

---

## 3. History Endpoints

### `GET /api/v1/runs`
Fetches historical runs linked to the authenticated user.

**Authentication:** Required.

#### Query Parameters:
- `limit` (int, default: 20)
- `offset` (int, default: 0)

#### Response Body:
```json
[
  {
    "id": "b83ef31d-b8d9-482f-89c1-4c12ea8f12a8",
    "created_at": "2026-05-18T10:15:30Z",
    "status": "completed",
    "input_type": "snippet",
    "conflict_count": 0,
    "critical_count": 1,
    "warning_count": 0,
    "suggestion_count": 0
  }
]
```

### `GET /api/v1/runs/{run_id}`
Retrieves a complete aggregated report for a specific run.

**Authentication:** Required.

#### Response Body:
```json
{
  "run_id": "b83ef31d-b8d9-482f-89c1-4c12ea8f12a8",
  "status": "completed",
  "total_findings": 1,
  "findings": [...],
  "conflicts": []
}
```

---

## 4. Export & Utility Endpoints

### `GET /api/v1/export/{run_id}`
Exports an analysis report in standard Markdown or structural JSON.

**Authentication:** Required.

#### Query Parameters:
- `format` (string, default: `markdown` | options: `markdown`, `json`)

#### Response Body:
Returns a direct download payload (Markdown file or JSON object).

### `GET /health`
Liveness probe checking database connection status.

#### Response Body:
```json
{
  "status": "healthy",
  "database": "connected"
}
```

### `GET /ping`
Fast health check endpoint used to warm Render instances.

#### Response Body:
```json
"pong"
```
