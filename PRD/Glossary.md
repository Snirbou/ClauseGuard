# ClauseGuard — Glossary

**Version:** 1.0  
**Purpose:** Ensure consistent terminology across the project (PRD, code, documentation, and UX copy).

---

## A

### Acceptance Criteria
Measurable conditions that must be satisfied for a feature or user story to be considered complete. Defined in [AcceptanceCriteria.md](./AcceptanceCriteria.md).

### Analysis Run
A single execution of the full pipeline (parse → segment → classify → assess → explain → score) for a given contract. Multiple runs may occur for the same contract (e.g., after model updates).

### Asymmetric Termination
A termination clause that grants one party (typically the client) more favorable rights than the other (e.g., client may terminate at any time without notice; freelancer must give 30 days' notice).

---

## C

### ChainOfThought (CoT)
A DSPy module that prompts the LLM to produce step-by-step reasoning before the final answer. Used for risk assessment and plain-language explanation to improve faithfulness and debuggability.

### Clause
A distinct provision or section within a contract that addresses a specific topic (e.g., payment terms, IP assignment). The unit of analysis in ClauseGuard.

### Clause Classification
The ML task of assigning each clause to a predefined category (e.g., payment, termination, IP, liability, scope, confidentiality). Performed by the Scikit-learn classifier (Layer 1).

### Clause Segmentation
The process of splitting a contract's raw text into individual clauses using heuristics (headers, paragraph breaks, numbering). Precedes classification.

### Comparative Framing
The practice of presenting risk and other outputs as relative to a reference set (e.g., "this clause is in the bottom 15th percentile of freelance contracts") rather than as absolute judgments. Required for UPL safety.

### Contract Type
The domain of the contract (e.g., freelance_service, nda, consulting). Determines which classification labels and risk logic apply. MVP supports freelance_service only.

### CUAD
Contract Understanding Attitude Dataset. An expert-annotated NLP dataset for legal contract review, containing 510 contracts and 13K+ annotations across 41 clause categories. Used for training and evaluating risk detection.

---

## D

### DSPy
A framework for programming—not prompting—language models. Enables systematic optimization of prompts and few-shot examples via optimizers (e.g., MIPROv2) rather than manual tuning.

### DSPy Optimizer
A component (e.g., MIPROv2) that automatically searches for optimal prompts and few-shot examples by evaluating candidate configurations against a metric. Produces a "compiled" program for production use.

---

## E

### EDGAR
Electronic Data Gathering, Analysis, and Retrieval system. The SEC's repository of corporate filings. Exhibit-10 filings contain material contracts; LEDGAR and CUAD are derived from EDGAR data.

### Ensemble
A model that combines predictions from multiple sub-models. In ClauseGuard, the hybrid scorer (Layer 3) is an ensemble of ML features and LLM outputs.

---

## F

### F1 Score
The harmonic mean of precision and recall. Primary metric for clause classification performance. Target: ≥ 0.85 on top 20 clause types.

### Freelance Service Agreement
A contract between a freelancer (independent contractor) and a client for the provision of services. The sole contract type supported in MVP.

---

## H

### Hybrid Scoring
The combination of Layer 1 (ML) and Layer 2 (LLM) outputs into a final risk score via a logistic regression meta-model (Layer 3).

---

## I

### Informational Tool
A system that provides educational content and pattern-matching observations without offering legal advice. ClauseGuard is designed as an informational tool to avoid UPL.

### IP Assignment
A clause that transfers intellectual property rights from one party to another. Blanket IP assignment without carve-outs for pre-existing work is a key freelancer pain point.

---

## L

### LEDGAR
Large-scale multi-label corpus of legal provisions from SEC EDGAR contracts. Contains 846K provisions with 100 topic labels. Used for training the clause classifier.

### Liability Cap
A clause that limits a party's maximum financial exposure (e.g., to the total contract value). Absence of a liability cap is a risk indicator.

### Living Document
A document that is updated throughout the project lifecycle rather than frozen at a single point. The PRD is a living document.

---

## M

### MIPROv2
Multiprompt Instruction PRoposal Optimizer Version 2. A DSPy optimizer that performs Bayesian optimization over instruction prompts and few-shot example selection.

### MVP
Minimum Viable Product. The initial release of ClauseGuard, scoped to freelance service agreements in English with core analysis features.

---

## N

### NER (Named Entity Recognition)
The NLP task of identifying and classifying named entities (e.g., dates, amounts, party names, legal entities) in text. Performed by spaCy in ClauseGuard.

### NDA
Non-Disclosure Agreement. A contract type considered for post-MVP expansion.

---

## P

### Pain Point
A recurring problem or risk that freelancers face in contracts. ClauseGuard addresses five: scope creep, payment traps, IP assignment, asymmetric termination, and missing liability caps.

### Plain-Language Summary
A user-accessible explanation of a clause's meaning, generated by the DSPy pipeline. Must avoid legal jargon and prescriptive language.

### Progressive Disclosure
A UX pattern where detailed information (e.g., risk assessment) is hidden by default and revealed only when the user explicitly expands it. Reinforces that the user is actively choosing to view pattern-based analysis.

### PRD
Product Requirements Document. The main living document defining vision, scope, and specifications.

---

## R

### Risk Factor
A specific reason or pattern identified as contributing to a clause's risk level (e.g., "payment contingent on approval," "no pre-existing IP carve-out").

### Risk Level
A categorical label (low, medium, high) assigned to a clause based on the hybrid score. Used for UX display and filtering.

### Risk Score
A normalized numeric value (0–1) representing the pattern-based risk of a clause. Combined with risk factors and percentile for display.

---

## S

### Scope Creep
Uncontrolled expansion of project scope beyond the original agreement. Often caused by vague scope definitions (e.g., "design support" without deliverable limits or revision caps).

### Scope Creep (PRD)
Uncontrolled expansion of product scope beyond the defined MVP. The PRD and release plan are designed to prevent scope creep.

### spaCy
An open-source NLP library used for tokenization, lemmatization, and NER in ClauseGuard.

---

## T

### TF-IDF
Term Frequency–Inverse Document Frequency. A numerical statistic reflecting the importance of a term in a document relative to a corpus. Used as a feature for clause classification.

### Template Comparison
A future feature that compares a clause to standard contract templates. Must be framed as "For reference: common alternative pattern" to avoid UPL.

---

## U

### UNFAIR-ToS
A dataset of Terms of Service with unfairness annotations. Used to train the risk/fairness scoring component. Categories transfer well to freelance contracts.

### UPL (Unauthorized Practice of Law)
The provision of legal services (e.g., legal advice, drafting documents) by a non-licensed person or entity. ClauseGuard is designed to avoid UPL by remaining an informational tool.

### UPL Safety
The set of design principles and constraints that keep ClauseGuard's outputs within the informational lane and avoid crossing into legal advice.

---

## V

### Validation Set
A held-out dataset used to evaluate model performance during development. For ClauseGuard, a domain-specific validation set of 200–500 hand-labeled freelance clauses is recommended.

---

## X

*(No entries)*

---

## Y

*(No entries)*

---

## Z

*(No entries)*

---

*When adding new terms, maintain alphabetical order and cross-reference related PRD sections.*
