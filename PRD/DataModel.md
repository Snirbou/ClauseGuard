# ClauseGuard — Data Model

**Version:** 1.0  
**Database:** PostgreSQL  
**Last Updated:** March 2026

---

This document describes the PostgreSQL database schema for ClauseGuard, including tables, relationships, indexes, and constraints. The model supports users, contracts, parsed clauses, annotations, risk scores, and audit trails.

---

## 1. Entity Relationship Overview

```
users
  │
  ├── contracts (1:N)
  │     │
  │     ├── parsed_clauses (1:N)
  │     │     │
  │     │     ├── clause_annotations (1:N)
  │     │     └── risk_scores (1:1)
  │     │
  │     └── analysis_runs (1:N)
  │
  ├── disclaimer_logs (1:N)
  └── ml_model_versions (system-wide, referenced by risk_scores)
```

---

## 2. Table Definitions

### 2.1 `users`

Stores registered user accounts for authentication and contract ownership.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() | Unique user identifier |
| `email` | VARCHAR(255) | NOT NULL, UNIQUE | User email (login) |
| `password_hash` | VARCHAR(255) | NOT NULL | Bcrypt/Argon2 hash |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Account creation time |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Last profile update |

**Indexes:**
- `idx_users_email` ON `email`

---

### 2.2 `contracts`

Stores uploaded contract documents and metadata.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() | Unique contract identifier |
| `user_id` | UUID | NOT NULL, FK → users(id) ON DELETE CASCADE | Owner of the contract |
| `original_filename` | VARCHAR(512) | NOT NULL | Original PDF filename |
| `file_size_bytes` | INTEGER | NOT NULL | File size in bytes |
| `file_storage_path` | VARCHAR(1024) | NOT NULL | Path/key in object storage or filesystem |
| `contract_type` | VARCHAR(64) | NOT NULL, DEFAULT 'freelance_service' | Contract domain (MVP: freelance_service) |
| `status` | VARCHAR(32) | NOT NULL, DEFAULT 'pending' | pending, processing, completed, failed |
| `error_message` | TEXT | NULL | Error details if status = failed |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Upload time |
| `processed_at` | TIMESTAMPTZ | NULL | When analysis completed |

**Indexes:**
- `idx_contracts_user_id` ON `user_id`
- `idx_contracts_status` ON `status`
- `idx_contracts_created_at` ON `created_at` DESC

---

### 2.3 `parsed_clauses`

Stores individual clauses extracted from a contract.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() | Unique clause identifier |
| `contract_id` | UUID | NOT NULL, FK → contracts(id) ON DELETE CASCADE | Parent contract |
| `clause_index` | INTEGER | NOT NULL | Order within contract (1-based) |
| `raw_text` | TEXT | NOT NULL | Original clause text |
| `clause_type` | VARCHAR(128) | NULL | ML-predicted type (payment, termination, ip, liability, scope, confidentiality, etc.) |
| `clause_type_confidence` | DECIMAL(5,4) | NULL | ML confidence score (0–1) |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Extraction time |

**Indexes:**
- `idx_parsed_clauses_contract_id` ON `contract_id`
- `idx_parsed_clauses_clause_type` ON `clause_type`

---

### 2.4 `clause_annotations`

Stores NLP-extracted entities and metadata per clause (NER results, etc.).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() | Unique annotation identifier |
| `parsed_clause_id` | UUID | NOT NULL, FK → parsed_clauses(id) ON DELETE CASCADE | Parent clause |
| `annotation_type` | VARCHAR(64) | NOT NULL | e.g., date, amount, party, legal_entity |
| `value` | TEXT | NULL | Extracted value |
| `start_offset` | INTEGER | NULL | Start character offset in clause text |
| `end_offset` | INTEGER | NULL | End character offset |
| `metadata` | JSONB | NULL | Additional structured data |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Extraction time |

**Indexes:**
- `idx_clause_annotations_parsed_clause_id` ON `parsed_clause_id`
- `idx_clause_annotations_type` ON `annotation_type`

---

### 2.5 `risk_scores`

Stores the final hybrid risk score and associated outputs per clause.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() | Unique risk score identifier |
| `parsed_clause_id` | UUID | NOT NULL, UNIQUE, FK → parsed_clauses(id) ON DELETE CASCADE | One-to-one with clause |
| `risk_level` | VARCHAR(16) | NOT NULL | low, medium, high |
| `risk_score` | DECIMAL(5,4) | NOT NULL | Normalized score (0–1) |
| `risk_percentile` | INTEGER | NULL | Comparative percentile (0–100) |
| `risk_factors` | JSONB | NULL | Array of identified risk factors from DSPy |
| `plain_language_summary` | TEXT | NULL | DSPy-generated plain-language explanation |
| `ml_model_version_id` | UUID | NULL, FK → ml_model_versions(id) | Version of ML classifier used |
| `dspy_program_version` | VARCHAR(128) | NULL | DSPy compiled program version |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Computation time |

**Indexes:**
- `idx_risk_scores_parsed_clause_id` ON `parsed_clause_id`
- `idx_risk_scores_risk_level` ON `risk_level`

---

### 2.6 `analysis_runs`

Tracks each analysis execution for a contract (supports re-runs and versioning).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() | Unique run identifier |
| `contract_id` | UUID | NOT NULL, FK → contracts(id) ON DELETE CASCADE | Contract analyzed |
| `status` | VARCHAR(32) | NOT NULL | pending, running, completed, failed |
| `started_at` | TIMESTAMPTZ | NOT NULL | Run start time |
| `completed_at` | TIMESTAMPTZ | NULL | Run end time |
| `processing_time_ms` | INTEGER | NULL | Total processing duration |
| `clause_count` | INTEGER | NULL | Number of clauses processed |
| `error_message` | TEXT | NULL | Error details if failed |
| `metadata` | JSONB | NULL | Pipeline config, model versions, etc. |

**Indexes:**
- `idx_analysis_runs_contract_id` ON `contract_id`
- `idx_analysis_runs_status` ON `status`

---

### 2.7 `disclaimer_logs`

Audit trail for UPL compliance: logs when disclaimers are shown to users.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() | Unique log identifier |
| `user_id` | UUID | NULL, FK → users(id) | User who saw disclaimer (null if anonymous) |
| `session_id` | VARCHAR(128) | NULL | Session identifier for anonymous users |
| `disclaimer_type` | VARCHAR(64) | NOT NULL | e.g., main_banner, clause_expansion |
| `contract_id` | UUID | NULL, FK → contracts(id) | Contract context if applicable |
| `parsed_clause_id` | UUID | NULL, FK → parsed_clauses(id) | Clause context if applicable |
| `displayed_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | When disclaimer was shown |

**Indexes:**
- `idx_disclaimer_logs_user_id` ON `user_id`
- `idx_disclaimer_logs_displayed_at` ON `displayed_at` DESC

---

### 2.8 `ml_model_versions`

Tracks deployed ML model versions for reproducibility and evaluation.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() | Unique version identifier |
| `model_type` | VARCHAR(64) | NOT NULL | e.g., clause_classifier, hybrid_scorer |
| `version_tag` | VARCHAR(128) | NOT NULL | Human-readable version (e.g., v1.2.0) |
| `storage_path` | VARCHAR(1024) | NULL | Path to serialized model file |
| `training_metrics` | JSONB | NULL | F1, precision, recall per class |
| `deployed_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | When version became active |
| `is_active` | BOOLEAN | NOT NULL, DEFAULT true | Whether this version is currently used |

**Indexes:**
- `idx_ml_model_versions_model_type` ON `model_type`
- `idx_ml_model_versions_is_active` ON `is_active` WHERE is_active = true

---

### 2.9 `dspy_optimizer_logs` (Optional, for Admin)

Stores DSPy optimizer traces for debugging and portfolio showcase.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() | Unique log identifier |
| `optimizer_run_id` | VARCHAR(128) | NOT NULL | DSPy optimizer run identifier |
| `prompt_variant` | TEXT | NULL | Instruction or prompt tried |
| `metric_score` | DECIMAL(10,6) | NULL | Score achieved |
| `trial_index` | INTEGER | NULL | Trial number in optimization |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | When trial was run |

**Indexes:**
- `idx_dspy_optimizer_logs_run_id` ON `optimizer_run_id`

---

## 3. Enumerations (Application-Level)

These are not database enums but should be enforced in application code:

| Entity | Values |
|--------|--------|
| `contracts.status` | pending, processing, completed, failed |
| `contracts.contract_type` | freelance_service (MVP); future: nda, consulting |
| `risk_scores.risk_level` | low, medium, high |
| `analysis_runs.status` | pending, running, completed, failed |

---

## 4. Sample Queries

### Get full analysis for a contract

```sql
SELECT 
  c.original_filename,
  pc.clause_index,
  pc.raw_text,
  pc.clause_type,
  pc.clause_type_confidence,
  rs.risk_level,
  rs.risk_score,
  rs.risk_factors,
  rs.plain_language_summary
FROM contracts c
JOIN parsed_clauses pc ON pc.contract_id = c.id
LEFT JOIN risk_scores rs ON rs.parsed_clause_id = pc.id
WHERE c.id = :contract_id
ORDER BY pc.clause_index;
```

### Get high-risk clauses for a contract

```sql
SELECT pc.clause_index, pc.raw_text, rs.risk_factors, rs.plain_language_summary
FROM parsed_clauses pc
JOIN risk_scores rs ON rs.parsed_clause_id = pc.id
WHERE pc.contract_id = :contract_id AND rs.risk_level = 'high'
ORDER BY pc.clause_index;
```

### Disclaimer audit trail for a user

```sql
SELECT disclaimer_type, displayed_at, contract_id
FROM disclaimer_logs
WHERE user_id = :user_id
ORDER BY displayed_at DESC
LIMIT 100;
```

---

## 5. Migration Notes

- Use UUIDs for all primary keys to support distributed systems and avoid enumeration attacks.
- `ON DELETE CASCADE` ensures orphaned records are cleaned when parents are deleted.
- `JSONB` is used for flexible metadata; consider indexing specific keys if query patterns emerge.
- Add `updated_at` triggers where applicable for audit purposes.
- Consider partitioning `disclaimer_logs` and `analysis_runs` by time for large-scale deployments.

---

*Schema changes should be versioned (e.g., Alembic migrations) and documented in this file.*
