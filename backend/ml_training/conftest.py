"""Pytest fixtures: tiny synthetic clause sets for smoke tests."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ML_TRAINING_DIR = Path(__file__).resolve().parent
if str(ML_TRAINING_DIR) not in sys.path:
    sys.path.insert(0, str(ML_TRAINING_DIR))


SYNTHETIC_CLAUSES: list[tuple[str, str]] = [
    (
        "Contractor hereby assigns to Client all right, title and interest in any "
        "intellectual property created hereunder, including all copyrights and patents.",
        "ip_assignment",
    ),
    (
        "Client shall pay Contractor a fee of $5,000 within 30 days of invoice receipt.",
        "payment_terms",
    ),
    (
        "Either party may terminate this Agreement upon 30 days' prior written notice.",
        "termination",
    ),
    (
        "Contractor shall indemnify and hold harmless Client from all liabilities arising "
        "from Contractor's negligence.",
        "liability",
    ),
    (
        "Each party shall keep all confidential information strictly confidential and shall "
        "not disclose it to any third party.",
        "confidentiality",
    ),
    (
        "Contractor shall provide the deliverables described in Exhibit A in accordance with "
        "the project specifications.",
        "scope_of_work",
    ),
    (
        "This Agreement shall be governed by the laws of the State of Delaware, "
        "and any disputes shall be resolved in Wilmington courts.",
        "governing_law",
    ),
    (
        "The headings of the sections of this Agreement are for convenience only and shall "
        "not affect interpretation.",
        "general",
    ),
]


@pytest.fixture
def synthetic_clauses() -> list[tuple[str, str]]:
    return SYNTHETIC_CLAUSES.copy()


@pytest.fixture
def synthetic_texts(synthetic_clauses) -> list[str]:
    return [t for t, _ in synthetic_clauses]


@pytest.fixture
def synthetic_labels(synthetic_clauses) -> list[str]:
    return [lbl for _, lbl in synthetic_clauses]
