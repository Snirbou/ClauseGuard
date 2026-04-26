"""Rule-based mock clause classifier (Step 1 stand-in).

This will be replaced by Developer 1 (Full-Stack & ML) with a real
spaCy + Scikit-learn pipeline.  Developer 2 (DSPy) does NOT touch this
function — they only consume the classified records from the database.
"""

from __future__ import annotations


def mock_classify(raw_text: str) -> tuple[str, float]:
    """
    Rule-based mock classifier.
    Returns (clause_type, confidence).
    """
    text_lower = raw_text.lower()

    rules: list[tuple[list[str], str, float]] = [
        (
            ["intellectual property", "ip ", "ip,", "ownership of work",
             "work product", "inventions", "copyright assignment"],
            "ip_assignment",
            0.92,
        ),
        (
            ["payment", "invoice", "compensation", "fee", "remuneration",
             "net 30", "net 60", "billing"],
            "payment_terms",
            0.85,
        ),
        (
            ["terminat", "cancel", "expir", "end of term",
             "notice period", "wind down"],
            "termination",
            0.88,
        ),
        (
            ["liable", "liability", "indemnif", "damages",
             "limitation of liability", "hold harmless"],
            "liability",
            0.83,
        ),
        (
            ["confidential", "non-disclosure", "nda", "proprietary information",
             "trade secret"],
            "confidentiality",
            0.90,
        ),
        (
            ["scope of work", "deliverables", "services", "obligations",
             "responsibilities", "statement of work"],
            "scope_of_work",
            0.80,
        ),
        (
            ["governing law", "jurisdiction", "dispute resolution",
             "arbitration", "venue", "applicable law"],
            "governing_law",
            0.87,
        ),
    ]

    for keywords, clause_type, confidence in rules:
        if any(kw in text_lower for kw in keywords):
            return clause_type, confidence

    return "general", 0.50
