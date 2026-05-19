# Database Design

Anviksha relies on a relational **PostgreSQL** database, mapped via **SQLAlchemy 2.0 Declarative Async Mapping**. 

This document details our table structures, column constraints, indexing strategies, and design decisions.

---

## 1. Schema Diagram

Below is the database ERD showing relations and key properties:

![Database ERD](../diagrams/database-erd.md)

---

## 2. Table-by-Table Specifications

### `users`
Tracks registered developers and authenticating accounts.
- `id` (`UUID`, Primary Key): Generated using `uuid.uuid4`.
- `email` (`Text`, Unique, Indexed): User email address.
- `created_at` (`DateTime(timezone=True)`): Registration timestamp.

### `user_api_keys`
Stores developers' provider API keys encrypted with AES-256-GCM.
- `id` (`UUID`, Primary Key)
- `user_id` (`UUID`, Foreign Key pointing to `users.id` with `ondelete="CASCADE"`): Cascade delete ensures keys are purged if an account is deleted.
- `provider` (`String(20)`): The LLM provider (e.g., `groq`, `anthropic`).
- `encrypted_key` (`Text`): AES-256 encrypted ciphertext.
- `created_at` (`DateTime(timezone=True)`)
- `updated_at` (`DateTime(timezone=True)`)

### `sessions`
Houses active analysis lifecycles and temporarily saved API keys.
- `id` (`UUID`, Primary Key)
- `user_id` (`UUID`, Indexed): Shared secret identifier mapping to AuthShield.
- `created_at` (`DateTime(timezone=True)`)
- `last_active` (`DateTime(timezone=True)`)
- `api_key_encrypted` (`Text`, Nullable): Temporarily saved key for unauthenticated BYOK scans.
- `provider` (`String(20)`): The default LLM provider.

### `runs`
Represents an individual analysis execution pipeline.
- `id` (`UUID`, Primary Key)
- `session_id` (`UUID`, Foreign Key pointing to `sessions.id` with `ondelete="CASCADE"`, Indexed)
- `user_id` (`UUID`, Foreign Key pointing to `users.id` with `ondelete="SET NULL"`, Nullable, Indexed)
- `created_at` (`DateTime(timezone=True)`, Indexed): Optimized for query history sorting.
- `completed_at` (`DateTime(timezone=True)`, Nullable)
- `status` (`String(20)`): Status of the run (`running`, `completed`, `failed`).
- `input_type` (`String(20)`): The input format (`snippet`, `text`, `file`).
- `input_summary` (`Text`, Nullable): Statistics on the analyzed code (size, lines) rather than the raw code string, protecting user privacy.
- `duration_ms` (`Integer`, Nullable): Cumulative execution runtime.
- `conflict_count` (`Integer`): Number of logical conflicts identified.
- `model_used` (`String(100)`): Model used for analysis.

### `findings`
Stores individual agent findings and their evaluation metrics.
- `id` (`UUID`, Primary Key)
- `run_id` (`UUID`, Foreign Key pointing to `runs.id` with `ondelete="CASCADE"`, Indexed)
- `agent` (`String(30)`): Generating agent (`security`, `performance`, `architecture`).
- `severity` (`String(20)`, Indexed): Assigned severity (`critical`, `warning`, `suggestion`).
- `finding` (`Text`): Title/description of the issue.
- `location` (`Text`, Nullable): Line range or function identifier.
- `fix_prose` (`Text`): Explanation of the fix.
- `fix_code` (`Text`, Nullable): Code snippet demonstrating the fix.
- `has_conflict` (`Boolean`): Set to `true` if this finding is involved in a logical conflict.
- `relevance_score` (`Float`, Nullable)
- `accuracy_score` (`Float`, Nullable)
- `actionability_score` (`Float`, Nullable)
- `severity_calibration_score` (`Float`, Nullable)
- `confidence_score` (`Float`, Nullable): Composite average score.
- `is_low_confidence` (`Boolean`, Indexed): Flag for fast frontend warnings.

---

## 3. Key Design Decisions

### Why `input_summary` Over Full Source Code Storage?
Storing large code repositories or code snippets directly in the database poses a security risk and increases storage costs. Anviksha protects user privacy by only saving an `input_summary` (number of lines, character size, and file type). The raw code is kept entirely in memory during graph execution and is never written to disk.

### Why Flat Scoring Columns on `findings`?
Instead of separating evaluation scores into an `evaluations` table, we store relevance, accuracy, and confidence metrics directly on the `findings` table. This flat layout eliminates expensive multi-table joins when loading user dashboards, allowing us to load run history with a simple query:

```sql
SELECT * FROM findings WHERE run_id = :run_id;
```

### Async Database Session Pool Recycle
Because Neon serverless PostgreSQL databases spin down compute nodes during inactivity, stale connections can cause transient application errors. We configure our engine with:
- `pool_recycle=300`: Automatically recycle connections older than 5 minutes.
- `pool_pre_ping=True`: Silently ping the database before executing any query, automatically reconnecting if Neon was asleep.
