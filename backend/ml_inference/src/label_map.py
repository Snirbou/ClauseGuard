"""LEDGAR (100 labels) -> ClauseGuard 8-label mapping.

Source label set: coastalcph/lex_glue, config="ledgar". The 100 LEDGAR labels are
fine-grained provision titles (e.g., "Indemnifications", "Notices"). We project
them onto the 8 literals defined in backend/schemas.py: ClauseInput.clause_type.

Anything not in CG8_TARGETS below collapses to "general". The test suite asserts
that every LEDGAR label has a deterministic destination (mapped or general).
"""

from __future__ import annotations

from typing import Iterable

CG8_TARGETS: tuple[str, ...] = (
    "ip_assignment",
    "payment_terms",
    "termination",
    "liability",
    "confidentiality",
    "scope_of_work",
    "governing_law",
    "general",
)

LEDGAR_TO_CG8: dict[str, str] = {
    # ---- ip_assignment ----
    "intellectual property": "ip_assignment",
    "assigns": "ip_assignment",
    "assignments": "ip_assignment",
    "licenses": "ip_assignment",

    # ---- payment_terms ----
    "payments": "payment_terms",
    "expenses": "payment_terms",
    "fees": "payment_terms",
    "taxes": "payment_terms",
    "compensation": "payment_terms",
    "costs": "payment_terms",
    "withholdings": "payment_terms",

    # ---- termination ----
    "terminations": "termination",
    "expiration": "termination",
    "survival": "termination",

    # ---- liability ----
    "indemnifications": "liability",
    "indemnity": "liability",
    "liability": "liability",
    "warranties": "liability",
    "insurance": "liability",
    "disclaimers": "liability",
    "remedies": "liability",
    "releases": "liability",

    # ---- confidentiality ----
    "confidentiality": "confidentiality",
    "non-disclosure": "confidentiality",
    "non-disclosures": "confidentiality",
    "publicity": "confidentiality",

    # ---- scope_of_work ----
    "duties": "scope_of_work",
    "obligations": "scope_of_work",
    "cooperation": "scope_of_work",
    "performance": "scope_of_work",
    "deliveries": "scope_of_work",
    "use of proceeds": "scope_of_work",

    # ---- governing_law ----
    "governing laws": "governing_law",
    "jurisdictions": "governing_law",
    "arbitration": "governing_law",
    "venues": "governing_law",
    "waiver of jury trials": "governing_law",
    "submission to jurisdiction": "governing_law",
    "applicable laws": "governing_law",
}


def map_label(ledgar_label: str) -> str:
    """Map a single LEDGAR label string to one of the 8 CG8 targets.

    Matching is case-insensitive. Unknown labels collapse to "general".
    """
    return LEDGAR_TO_CG8.get(ledgar_label.strip().lower(), "general")


def map_labels(ledgar_labels: Iterable[str]) -> list[str]:
    return [map_label(lbl) for lbl in ledgar_labels]
