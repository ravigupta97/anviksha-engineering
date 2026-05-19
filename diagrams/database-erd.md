# Database Entity-Relationship Diagram (ERD)

This document contains the entity-relationship diagram for the Anviksha relational schema. Built upon **SQLAlchemy Async mapped_columns**, the system uses standard PostgreSQL relational mappings with strict indexing and cascading constraints.

### Schema Design Decisions

1. **UUID Primary Keys:** All tables use secure, randomly generated UUIDs (`uuid.uuid4`) as primary keys instead of auto-incrementing integers, preventing account enumeration vulnerabilities and ensuring smooth scaling.
2. **Confidence Scores on Findings:** Confidence and validation metrics (accuracy, relevance, actionability, calibration, and average score) are kept directly on the `findings` table. This flat layout avoids expensive table joins when loading analysis dashboards.
3. **Encrypted Key Storage:** Encrypted provider API keys are stored in `user_api_keys` and `sessions` using strict AES-256 formatting. They are never kept in plaintext.
4. **Input Summarization:** Instead of saving full multiline user code repositories in the database (which creates massive memory overhead and security exposure), the `runs` table holds an `input_summary` (statistics on lines analyzed, language type, and character size).

```mermaid
erDiagram
    USERS {
        uuid id PK
        text email UK
        timestamp created_at
    }

    USER_API_KEYS {
        uuid id PK
        uuid user_id FK
        varchar provider
        text encrypted_key
        timestamp created_at
        timestamp updated_at
    }

    SESSIONS {
        uuid id PK
        uuid user_id INDEX
        timestamp created_at
        timestamp last_active
        text api_key_encrypted
        varchar provider
    }

    RUNS {
        uuid id PK
        uuid session_id FK
        uuid user_id FK
        timestamp created_at INDEX
        timestamp completed_at
        varchar status
        varchar input_type
        text input_summary
        integer duration_ms
        integer conflict_count
        varchar model_used
    }

    FINDINGS {
        uuid id PK
        uuid run_id FK
        varchar agent
        varchar severity INDEX
        text finding
        text location
        text fix_prose
        text fix_code
        boolean has_conflict
        float relevance_score
        float accuracy_score
        float actionability_score
        float severity_calibration_score
        float confidence_score
        boolean is_low_confidence
    }

    USERS ||--o{ RUNS : "owns"
    USERS ||--o{ USER_API_KEYS : "has"
    SESSIONS ||--o{ RUNS : "houses"
    RUNS ||--o{ FINDINGS : "contains"
```
