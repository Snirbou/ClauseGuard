# ClauseGuard — Product Requirements Document (PRD)

**Version:** 1.0  
**Status:** Living Document  
**Last Updated:** March 2026  
**Document Owner:** Product / Engineering

---

## Document Purpose

This PRD serves as the **single source of truth** for ClauseGuard, aligning development, design, and product stakeholders on what to build and why. It is maintained as a living document throughout the development lifecycle to prevent scope creep and ensure consistent execution. Updates should follow a controlled process (e.g., Pull Requests) to maintain traceability.

---

## 1. Overview

### 1.1 Vision

ClauseGuard is an AI-powered contract analysis platform that democratizes access to contract understanding for freelancers and small business owners. By combining classical Machine Learning, advanced NLP, and programmatic LLM optimization (DSPy), the system provides **educational, pattern-based analysis** of freelance service agreements—enabling users to identify key clauses, understand their implications in plain language, and recognize statistically flagged risk patterns—without crossing into the provision of legal advice.

The platform lowers the barrier to contract literacy and empowers users to make informed decisions about when to seek professional legal counsel.

### 1.2 Problem Statement

Freelancers and small business owners routinely sign contracts without legal review due to cost constraints. This exposes them to significant risks:

- **Scope creep** from vague deliverables and unlimited revision rounds
- **Payment traps** (Net 60 terms, payment contingent on approval, no late-payment penalties)
- **Blanket IP assignment** without carve-outs for pre-existing work or payment-contingent ownership
- **One-sided termination clauses** favoring the client
- **Uncapped liability** exposing small projects to disproportionate legal exposure

ClauseGuard addresses these pain points by providing an **informational tool** that flags clause types, summarizes content in plain language, and surfaces pattern-based risk indicators—all while remaining firmly within UPL-safe boundaries.

### 1.3 Core Principles

| Principle | Description |
|-----------|-------------|
| **Informational Only** | The system provides educational content and pattern-matching observations, never legal advice or recommendations to sign or reject. |
| **UPL Compliance** | All outputs are framed as comparative, observational, and statistical—never prescriptive. |
| **Technical Depth** | The architecture demonstrates genuine Data Science and NLP capabilities, not a thin LLM wrapper. |
| **Data-Driven** | Models are trained on public legal datasets (LEDGAR, CUAD, UNFAIR-ToS) with measurable evaluation metrics. |

---

## 2. Objectives

| Objective | Description | Success Indicator |
|-----------|-------------|-------------------|
| **O1** | Enable freelancers to upload and analyze freelance service agreements in under 60 seconds | 95% of valid uploads processed within 60 seconds |
| **O2** | Classify clause types with high accuracy using classical ML | F1 ≥ 0.85 on top 20 clause types |
| **O3** | Provide plain-language explanations without legal advice | All outputs pass UPL compliance review |
| **O4** | Surface pattern-based risk indicators for key pain points | 5 pain point categories addressed with measurable detection |
| **O5** | Demonstrate portfolio-level algorithmic depth | 3-layer AI architecture documented and operational |

---

## 3. Target Audience

### 3.1 Primary Persona: Freelancer

- **Profile:** Independent contractors (designers, developers, writers, consultants) who work on project-based engagements
- **Needs:** Understand contract terms before signing; identify red flags without hiring a lawyer
- **Pain Points:** Vague scope, payment traps, IP assignment, one-sided termination, liability exposure
- **Technical Comfort:** Varies; expects simple upload and intuitive results

### 3.2 Secondary Persona: Small Business Owner

- **Profile:** Owners of small businesses who occasionally engage freelancers or sign service agreements
- **Needs:** Quick contract review for inbound agreements; awareness of standard vs. non-standard terms
- **Pain Points:** Similar to freelancers; may also act as contract drafter

### 3.3 Secondary Persona: System Administrator

- **Profile:** Technical operator responsible for model deployment, monitoring, and compliance
- **Needs:** Visibility into model performance, pipeline health, and audit trails
- **Pain Points:** Debugging model drift, ensuring UPL compliance in outputs

---

## 4. MVP Scope

### 4.1 In Scope (MVP)

| Feature | Description | Priority |
|---------|-------------|----------|
| **Contract Upload** | PDF upload (max 10MB), parsing, and storage | P0 |
| **Clause Segmentation** | Automatic splitting of contract text into provisions | P0 |
| **Clause Classification** | ML-based classification into 5–20 clause types (payment, termination, IP, liability, scope, confidentiality) | P0 |
| **Plain-Language Summary** | DSPy-generated explanation of each clause in accessible language | P0 |
| **Risk Assessment** | Pattern-based risk scoring (high/medium/low) with comparative framing | P0 |
| **Pain Point Detection** | Flagging of scope creep, payment traps, IP assignment, termination asymmetry, liability gaps | P0 |
| **Disclaimer & UX Safeguards** | Persistent non-dismissable disclaimer; "Consult a Lawyer" CTA; progressive disclosure | P0 |
| **User Authentication** | Registration and login for contract history | P1 |
| **Contract History** | View past analyses and re-access results | P1 |

### 4.2 Out of Scope (MVP)

| Feature | Rationale | Future Release |
|---------|-----------|-------------------|
| Lease agreements | Jurisdiction-heavy; different domain | Post-MVP |
| Employment contracts | Labor law complexity; different domain | Post-MVP |
| NDAs / Consulting agreements | Post-MVP expansion |
| Alternative clause drafting | UPL risk; never in scope | N/A |
| Multi-language support | MVP English only | Post-MVP |
| Template comparison | Nice-to-have feature | Post-MVP |

### 4.3 Contract Type Support

**MVP:** Freelance Service Agreements (Independent Contractor Agreements) only.

The pipeline is designed to be contract-type-agnostic at the infrastructure level. A `contract_type` metadata field enables future expansion without pipeline rebuilds. Classification labels and risk logic are tailored to the freelance domain for MVP.

---

## 5. Technical Specifications

### 5.1 Technology Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Backend** | FastAPI | REST API, async processing, validation |
| **Frontend** | Next.js | React-based SPA, responsive UI |
| **Database** | PostgreSQL | Persistent storage, relational integrity |
| **Document Parsing** | PyMuPDF / pdfplumber | PDF text extraction |
| **NLP Preprocessing** | spaCy | Tokenization, lemmatization, NER |
| **Classical ML** | Scikit-learn | Clause classification, hybrid scoring |
| **LLM Programming** | DSPy | Risk assessment, plain-language explanation |
| **LLM Provider** | OpenAI / Anthropic (configurable) | Backend for DSPy modules |

### 5.2 Three-Layer AI Architecture

The AI/ML layer is explicitly divided into three layers to demonstrate algorithmic depth and avoid the "GPT wrapper" perception:

---

#### **Layer 1: Classical ML (Scikit-learn + spaCy) — Clause Classification**

**Purpose:** Classify clause types using traditional ML—no LLMs. Demonstrates Data Science fundamentals.

| Component | Technology | Output |
|-----------|------------|--------|
| Preprocessing | spaCy | Tokenization, lemmatization, NER (parties, dates, amounts) |
| Feature extraction | TF-IDF, clause length, modal verbs, NER counts, sentence complexity | Feature vector per clause |
| Classifier | Scikit-learn (SVM or Gradient Boosting) | Clause type label + confidence |

**Training:** LEDGAR-derived labels; top 20 clause types relevant to freelance contracts.

**Performance Target:** F1 ≥ 0.85 on top 20 clause types.

**Evaluation:** Classification report (precision, recall, F1 per class) published in README and evaluation dashboard.

---

#### **Layer 2: DSPy Pipeline — Risk Assessment & Plain-Language Explanation**

**Purpose:** Systematic programmatic LLM use with optimizer-driven prompt optimization—not hand-tuned prompts.

| Component | DSPy Module | Purpose |
|-----------|-------------|---------|
| Risk assessment | `ChainOfThought` | Step-by-step reasoning about risk factors |
| Plain-language explanation | `ChainOfThought` | Generate accessible summary |
| Template comparison (future) | `Predict` | Compare clause to standard templates |

**Optimizer:** MIPROv2 for Bayesian optimization over instructions and few-shot examples.

**Key Differentiators:**
- Custom metric function evaluating risk accuracy against CUAD/UNFAIR-ToS labeled data
- Before/after optimization prompts documented
- A/B test: DSPy-optimized vs. hand-written prompts (report accuracy delta)

**Output:** Risk score, risk factors, plain-language explanation—all framed as comparative/observational.

---

#### **Layer 3: Hybrid Scoring — Ensemble**

**Purpose:** Combine ML and LLM signals into a final risk score.

| Input Features | Source |
|----------------|--------|
| Clause type confidence | Layer 1 (ML) |
| Presence/absence of key protections | NER |
| Statistical one-sidedness indicators | ML |
| DSPy risk factors | Layer 2 (LLM) |

**Output:** Logistic regression meta-model produces final weighted risk score.

**Rationale:** Demonstrates ensemble design, ML + LLM integration, and engineering judgment.

---

### 5.3 End-to-End Pipeline

```
PDF Upload → Parse (PDF→Text) → Segment (Clauses) → Classify (ML) → Assess Risk (DSPy) → Explain (DSPy) → Score (Hybrid) → Store
```

---

### 5.4 UPL Safety Constraints (Technical)

| Constraint | Implementation |
|------------|----------------|
| No prescriptive language | Output templates use "commonly associated with," "typically includes," "pattern flagged" |
| No alternative clause drafting | System never generates replacement clause text |
| Comparative risk framing | Risk score presented as percentile ("bottom 15th percentile") not absolute judgment |
| Audit trail | All disclaimers shown logged with timestamps |
| Template comparison (future) | Framed as "For reference: common alternative pattern" not "Use this instead" |

---

## 6. Release Plan

### 6.1 Milestones

| Milestone | Description | Target |
|-----------|-------------|--------|
| **M1** | Data pipeline + clause classification (5 clause types) | Week 4 |
| **M2** | DSPy integration for risk assessment and plain-language explanation | Week 6 |
| **M3** | Hybrid scoring + full pain point detection | Week 8 |
| **M4** | MVP launch: full stack, auth, disclaimer, UX safeguards | Week 10 |

### 6.2 Dependencies

- LEDGAR/CUAD dataset access via HuggingFace
- LLM API key (OpenAI or Anthropic)
- PostgreSQL instance
- Deployment environment (e.g., Vercel + Railway, or Docker)

---

## 7. Assumptions and Constraints

### 7.1 Assumptions

- Users will use the system as an educational tool, not as a substitute for legal advice
- Users will seek professional counsel when appropriate (e.g., via "Consult a Lawyer" CTA)
- Freelance contracts are primarily in English for MVP
- Public datasets (LEDGAR, CUAD, UNFAIR-ToS) provide sufficient training signal for domain adaptation
- UPL statutes remain interpretable as applying to human conduct; AI tools in informational lane remain low-risk

### 7.2 Constraints

- **Regulatory:** Must avoid UPL; no legal advice, no drafting
- **Technical:** MVP limited to English-only contract text
- **Scope:** No lease or employment contracts in MVP
- **Data:** No PII in training data; user contracts stored with user consent per ToS

---

## 8. Related Documents

| Document | Purpose |
|----------|---------|
| [UserStories.md](./UserStories.md) | Persona-based user stories in standard format |
| [DataModel.md](./DataModel.md) | PostgreSQL schema and entity relationships |
| [Glossary.md](./Glossary.md) | Project-specific terminology |
| [AcceptanceCriteria.md](./AcceptanceCriteria.md) | Measurable KPIs and success metrics |

---

*This document should be updated via controlled changes (e.g., PRs) and versioned. All feature additions must be evaluated against UPL safety guidelines.*
