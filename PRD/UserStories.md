# ClauseGuard — User Stories

**Version:** 1.0  
**Format:** As a [persona], I want to [action], so that [benefit]

---

This document contains user stories organized by persona. All stories adhere to the standard format and are traceable to PRD features and acceptance criteria.

---

## 1. Freelancer Persona

### Contract Upload & Analysis

| ID | User Story | Priority |
|----|------------|----------|
| F-01 | As a **freelancer**, I want to **upload a contract as a PDF file**, so that **I can receive a digital analysis of its contents**. | P0 |
| F-02 | As a **freelancer**, I want to **see a clear confirmation when my contract has been uploaded successfully**, so that **I know the system is processing my document**. | P0 |
| F-03 | As a **freelancer**, I want to **receive an error message if my file is invalid or corrupted**, so that **I understand what went wrong and can try again with a valid file**. | P0 |
| F-04 | As a **freelancer**, I want to **view the analysis results within 60 seconds of upload**, so that **I can quickly decide whether to proceed or seek legal advice**. | P0 |

### Understanding Clauses

| ID | User Story | Priority |
|----|------------|----------|
| F-05 | As a **freelancer**, I want to **see each clause summarized in plain language**, so that **I can understand what the contract says without legal jargon**. | P0 |
| F-06 | As a **freelancer**, I want to **see which clauses relate to payment terms**, so that **I can verify when and how I will be paid**. | P0 |
| F-07 | As a **freelancer**, I want to **see which clauses relate to intellectual property (IP)**, so that **I can understand if I am retaining or losing rights to my work**. | P0 |
| F-08 | As a **freelancer**, I want to **see which clauses relate to scope of work**, so that **I can identify vague deliverables that might lead to scope creep**. | P0 |
| F-09 | As a **freelancer**, I want to **see which clauses relate to termination**, so that **I can understand under what conditions the contract can end**. | P0 |
| F-10 | As a **freelancer**, I want to **see which clauses relate to liability**, so that **I can assess my exposure to legal claims**. | P0 |

### Risk Awareness

| ID | User Story | Priority |
|----|------------|----------|
| F-11 | As a **freelancer**, I want to **see pattern-based risk indicators for each clause**, so that **I can identify clauses that commonly warrant closer review**. | P0 |
| F-12 | As a **freelancer**, I want to **see a "Consult a Lawyer" option next to high-risk clauses**, so that **I know when professional advice may be appropriate**. | P0 |
| F-13 | As a **freelancer**, I want to **expand risk details only when I choose to**, so that **I am not overwhelmed and understand I am actively choosing to view pattern-based analysis**. | P0 |
| F-14 | As a **freelancer**, I want to **see risk framed as comparative (e.g., percentile) rather than absolute**, so that **I understand this is statistical pattern-matching, not legal judgment**. | P0 |

### History & Account

| ID | User Story | Priority |
|----|------------|----------|
| F-15 | As a **freelancer**, I want to **create an account and log in**, so that **I can securely access my contract history**. | P1 |
| F-16 | As a **freelancer**, I want to **view a list of my previously analyzed contracts**, so that **I can revisit past analyses without re-uploading**. | P1 |
| F-17 | As a **freelancer**, I want to **re-open a past analysis and see the same results**, so that **I can reference them during negotiations or before signing**. | P1 |

### Trust & Safety

| ID | User Story | Priority |
|----|------------|----------|
| F-18 | As a **freelancer**, I want to **always see a clear disclaimer that the system does not provide legal advice**, so that **I understand the tool's limitations**. | P0 |
| F-19 | As a **freelancer**, I want to **never see prescriptive language like "you should" or "we recommend"**, so that **I am not misled into thinking I received legal advice**. | P0 |

---

## 2. Small Business Owner Persona

| ID | User Story | Priority |
|----|------------|----------|
| S-01 | As a **small business owner**, I want to **upload an inbound service agreement**, so that **I can quickly assess whether its terms align with standard practices**. | P1 |
| S-02 | As a **small business owner**, I want to **see plain-language summaries of key clauses**, so that **I can understand the agreement without hiring a lawyer for initial review**. | P1 |
| S-03 | As a **small business owner**, I want to **identify non-standard or one-sided terms**, so that **I can decide whether to negotiate or seek legal counsel**. | P1 |

---

## 3. System / Administrator Persona

### Pipeline & Processing

| ID | User Story | Priority |
|----|------------|----------|
| A-01 | As a **system administrator**, I want to **automatically segment uploaded contracts into clauses**, so that **each provision can be classified and analyzed independently**. | P0 |
| A-02 | As a **system administrator**, I want to **classify clauses by type using the ML model**, so that **the correct risk logic and explanations can be applied per clause type**. | P0 |
| A-03 | As a **system administrator**, I want to **run the DSPy pipeline for risk assessment and explanation**, so that **users receive consistent, optimized outputs**. | P0 |
| A-04 | As a **system administrator**, I want to **combine ML and LLM signals in the hybrid scorer**, so that **the final risk score reflects both pattern-matching and reasoning**. | P0 |

### Monitoring & Compliance

| ID | User Story | Priority |
|----|------------|----------|
| A-05 | As a **system administrator**, I want to **view clause classification accuracy metrics**, so that **I can detect model drift and plan retraining**. | P1 |
| A-06 | As a **system administrator**, I want to **view risk assessment precision and recall**, so that **I can validate the DSPy pipeline performance**. | P1 |
| A-07 | As a **system administrator**, I want to **log all disclaimer displays with timestamps**, so that **I can maintain an audit trail for compliance**. | P0 |
| A-08 | As a **system administrator**, I want to **view DSPy optimizer history and prompt variants**, so that **I can understand and reproduce optimization results**. | P1 |
| A-09 | As a **system administrator**, I want to **version ML models with timestamps and accuracy scores**, so that **I can track model improvement over time**. | P1 |

### Data & Security

| ID | User Story | Priority |
|----|------------|----------|
| A-10 | As a **system administrator**, I want to **store contracts and analyses securely per user**, so that **data is isolated and access-controlled**. | P0 |
| A-11 | As a **system administrator**, I want to **process only valid PDF files up to 10MB**, so that **the system remains performant and secure**. | P0 |

---

## 4. Cross-Persona Stories

| ID | User Story | Priority |
|----|------------|----------|
| X-01 | As a **user**, I want to **access the application from a web browser**, so that **I do not need to install software**. | P0 |
| X-02 | As a **user**, I want to **see a responsive interface on desktop and mobile**, so that **I can use the tool from any device**. | P1 |
| X-03 | As a **user**, I want to **receive clear feedback during loading states**, so that **I know the system is working and not frozen**. | P0 |

---

## 5. Traceability Matrix

| PRD Section | Related User Stories |
|-------------|----------------------|
| Contract Upload | F-01, F-02, F-03, F-04, A-11 |
| Clause Segmentation | A-01 |
| Clause Classification | F-05–F-10, A-02, A-05 |
| Plain-Language Summary | F-05, S-02 |
| Risk Assessment | F-11–F-14, A-03, A-04, A-06 |
| UPL Safeguards | F-12, F-13, F-14, F-18, F-19, A-07 |
| User Auth & History | F-15, F-16, F-17 |
| Admin/Monitoring | A-05, A-06, A-08, A-09 |

---

*User stories should be refined during sprint planning. Acceptance criteria for each story are defined in [AcceptanceCriteria.md](./AcceptanceCriteria.md).*
