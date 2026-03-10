# ClauseGuard — Acceptance Criteria & Success Metrics

**Version:** 1.0  
**Last Updated:** March 2026

---

This document defines measurable acceptance criteria, KPIs, and success metrics for the ClauseGuard MVP. Each criterion is traceable to PRD features and user stories.

---

## 1. Acceptance Criteria by Feature

### 1.1 Contract Upload

| ID | Criterion | Measurement | Pass/Fail |
|----|-----------|-------------|-----------|
| AC-U01 | A valid PDF (≤10MB) uploads and triggers processing | User receives success confirmation; contract appears in processing state | Pass if 100% of valid uploads succeed |
| AC-U02 | Processing completes within 60 seconds for typical contracts (5–20 pages) | Time from upload to "completed" status | Pass if p95 ≤ 60 seconds |
| AC-U03 | Invalid or corrupted files display a clear error message | User sees actionable error (e.g., "Invalid PDF. Please ensure the file is not corrupted.") | Pass if error message is displayed and non-technical |
| AC-U04 | Files >10MB are rejected before upload completes | Upload rejected with size limit message | Pass if rejection occurs |
| AC-U05 | Only PDF format is accepted | Non-PDF files rejected with format message | Pass if only PDFs are processed |

---

### 1.2 Clause Segmentation

| ID | Criterion | Measurement | Pass/Fail |
|----|-----------|-------------|-----------|
| AC-S01 | Contract text is split into discrete clauses | Each clause has unique clause_index and raw_text | Pass if segmentation produces ≥1 clause per contract |
| AC-S02 | Clause order is preserved | clause_index reflects document order | Pass if indices are sequential and match document structure |
| AC-S03 | No clause text is lost | Sum of clause lengths ≈ original document length (within 5%) | Pass if text coverage ≥95% |

---

### 1.3 Clause Classification

| ID | Criterion | Measurement | Pass/Fail |
|----|-----------|-------------|-----------|
| AC-C01 | Each clause receives a clause_type label | All parsed_clauses have non-null clause_type (or "unknown" for low-confidence) | Pass if 100% of clauses have a label |
| AC-C02 | Classification F1 score ≥ 0.85 on top 20 clause types | Evaluation on held-out test set | Pass if macro F1 ≥ 0.85 |
| AC-C03 | Classification confidence is stored | clause_type_confidence populated for each clause | Pass if confidence in [0,1] for all clauses |
| AC-C04 | At least 5 clause types supported in MVP | payment, termination, ip, liability, scope (minimum) | Pass if ≥5 types in classifier output |

---

### 1.4 Plain-Language Summary

| ID | Criterion | Measurement | Pass/Fail |
|----|-----------|-------------|-----------|
| AC-P01 | Each clause has a plain-language summary | risk_scores.plain_language_summary non-null for each clause | Pass if 100% of clauses have summary |
| AC-P02 | Summary avoids prescriptive language | No instances of "you should," "we recommend," "we advise" | Pass if automated check finds 0 violations |
| AC-P03 | Summary is faithful to clause content | Manual review of 20 random clauses; no hallucinated facts | Pass if ≥95% faithful in sample |
| AC-P04 | Summary uses accessible language | Readability score (e.g., Flesch-Kincaid) ≤ grade 12 | Pass if average grade level ≤ 12 |

---

### 1.5 Risk Assessment

| ID | Criterion | Measurement | Pass/Fail |
|----|-----------|-------------|-----------|
| AC-R01 | Each clause receives a risk_level (low/medium/high) | risk_scores.risk_level populated | Pass if 100% of clauses have risk_level |
| AC-R02 | Risk is framed comparatively | risk_percentile or equivalent comparative metric present | Pass if comparative framing in UI |
| AC-R03 | Risk factors are identified for high-risk clauses | risk_factors JSONB contains ≥1 factor for high-risk clauses | Pass if ≥80% of high-risk clauses have factors |
| AC-R04 | All 5 pain points are detectable | Scope creep, payment traps, IP assignment, termination asymmetry, liability gaps | Pass if each pain point has at least one detection rule or DSPy signal |
| AC-R05 | Risk assessment precision/recall documented | Evaluation against CUAD/UNFAIR-ToS labeled data | Pass if metrics documented in evaluation dashboard |

---

### 1.6 UPL Safeguards & UX

| ID | Criterion | Measurement | Pass/Fail |
|----|-----------|-------------|-----------|
| AC-X01 | Persistent disclaimer displayed on every analysis page | Non-dismissable banner visible | Pass if banner present and not closable |
| AC-X02 | Disclaimer text includes "informational purposes only" and "not legal advice" | Exact or equivalent phrasing | Pass if key phrases present |
| AC-X03 | "Consult a Lawyer" CTA visible for high-risk clauses | Button/link present next to high-risk clause details | Pass if CTA present for risk_level = high |
| AC-X04 | Risk details require explicit expansion (progressive disclosure) | Risk factors and full explanation behind expand/collapse | Pass if default view shows summary only |
| AC-X05 | Disclaimer displays are logged | disclaimer_logs has entries for each display | Pass if 100% of displays logged |
| AC-X06 | No alternative clause text is generated | System never outputs suggested replacement language | Pass if no such output exists |

---

### 1.7 User Authentication & History

| ID | Criterion | Measurement | Pass/Fail |
|----|-----------|-------------|-----------|
| AC-A01 | User can register with email and password | Account created; user can log in | Pass if registration and login work |
| AC-A02 | User can view list of past contracts | Contract list shows user's contracts only | Pass if list is filtered by user_id |
| AC-A03 | User can re-open a past analysis | Same results displayed as at creation | Pass if results are reproducible |
| AC-A04 | Passwords are hashed (not stored in plain text) | password_hash uses bcrypt/Argon2 | Pass if hashing verified |

---

### 1.8 API & Performance

| ID | Criterion | Measurement | Pass/Fail |
|----|-----------|-------------|-----------|
| AC-API01 | Upload endpoint returns within 5 seconds (excluding processing) | Response time for POST /contracts/upload | Pass if p95 ≤ 5s |
| AC-API02 | Analysis results endpoint returns within 2 seconds | Response time for GET /contracts/:id/analysis | Pass if p95 ≤ 2s |
| AC-API03 | API returns appropriate HTTP status codes | 200, 400, 401, 404, 500 as applicable | Pass if status codes follow REST conventions |
| AC-API04 | Invalid requests return 400 with error details | Request validation | Pass if validation errors are descriptive |

---

## 2. Key Performance Indicators (KPIs)

| KPI | Target | Measurement Method |
|-----|-------|-------------------|
| **Processing Success Rate** | ≥95% | (Contracts completed / Contracts uploaded) × 100 |
| **Clause Classification F1** | ≥0.85 | Macro F1 on held-out test set (top 20 types) |
| **End-to-End Latency (p95)** | ≤60 seconds | Time from upload to analysis ready |
| **API Availability** | ≥99% | Uptime over 30-day window |
| **Disclaimer Log Coverage** | 100% | All disclaimer displays logged |
| **UPL Compliance** | 0 violations | No prescriptive language in outputs |

---

## 3. Success Metrics for Initial Release

### 3.1 Technical Metrics

| Metric | Target | Rationale |
|--------|--------|------------|
| Clause classification F1 (macro) | ≥0.85 | Demonstrates ML competence; achievable per LEDGAR benchmarks |
| Risk assessment precision (high-risk) | ≥0.75 | Balance between flagging true risks and avoiding false alarms |
| Risk assessment recall (high-risk) | ≥0.70 | Ensure most high-risk clauses are surfaced |
| Average processing time per contract | ≤45 seconds | User expectation for "quick" analysis |
| API response time (analysis fetch) | ≤2 seconds | Responsive UX |

### 3.2 User Experience Metrics

| Metric | Target | Rationale |
|--------|--------|-----------|
| Upload-to-result time (p95) | ≤60 seconds | Core value proposition |
| Error message clarity | User can resolve without support | Self-service UX |
| Mobile responsiveness | Usable on 375px width | Accessibility |

### 3.3 Compliance Metrics

| Metric | Target | Rationale |
|--------|--------|-----------|
| Prescriptive language in outputs | 0 instances | UPL avoidance |
| Disclaimer display rate | 100% of analysis views | Audit trail |
| "Consult a Lawyer" CTA visibility | Present for all high-risk clauses | User empowerment |

---

## 4. Evaluation Dashboard Requirements

The application shall include an evaluation dashboard (admin or public) displaying:

| Element | Description |
|---------|-------------|
| Clause classification metrics | Precision, recall, F1 per class; confusion matrix |
| Risk assessment metrics | Precision/recall for high-risk detection |
| Processing time distribution | p50, p95, p99 latency |
| Model version | Active ML and DSPy program versions |
| DSPy optimizer history | Trial scores and prompt variants (if available) |

---

## 5. Definition of Done

A feature is considered **Done** when:

1. All acceptance criteria for that feature are met
2. Unit and integration tests cover the feature
3. Documentation (README, API docs) is updated
4. UPL safety review is passed (for any user-facing text)
5. Code is reviewed and merged to main

---

## 6. Traceability

| PRD Section | Acceptance Criteria |
|-------------|---------------------|
| Contract Upload | AC-U01–AC-U05 |
| Clause Segmentation | AC-S01–AC-S03 |
| Clause Classification | AC-C01–AC-C04 |
| Plain-Language Summary | AC-P01–AC-P04 |
| Risk Assessment | AC-R01–AC-R05 |
| UPL Safeguards | AC-X01–AC-X06 |
| Auth & History | AC-A01–AC-A04 |
| API & Performance | AC-API01–AC-API04 |

---

*Acceptance criteria should be refined during sprint planning. New criteria require PRD alignment and UPL safety review where applicable.*
