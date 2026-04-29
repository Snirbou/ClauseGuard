"""
mock_data.py — Realistic mock clause data for offline DSPy development.

WHY THIS EXISTS
---------------
Developer 2 (DSPy) can develop and test the pipeline logic in full without
needing a running PostgreSQL instance or waiting for Developer 1 to finalize
the database schema.  Simply call ``get_mock_clauses()`` to get a list of
``ClauseInput`` objects that cover every clause_type the mock classifier
can produce.

USAGE
-----
    from mock_data import get_mock_clauses
    clauses = get_mock_clauses()
"""

from __future__ import annotations

import uuid

from schemas import ClauseInput

# ---------------------------------------------------------------------------
# Fixed UUIDs — stable across runs so console output is reproducible
# ---------------------------------------------------------------------------

_CONTRACT_ID = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")

_MOCK_CLAUSES_RAW: list[dict] = [
    {
        "parsed_clause_id": uuid.UUID("11111111-0000-0000-0000-000000000001"),
        "contract_id": _CONTRACT_ID,
        "clause_type": "ip_assignment",
        "raw_text": (
            "All intellectual property, inventions, and work product created by "
            "the Contractor during the term of this Agreement, or as a result of "
            "services provided hereunder, shall be the sole and exclusive property "
            "of the Client. The Contractor hereby irrevocably assigns to the Client "
            "all right, title, and interest in such intellectual property, including "
            "all patent, copyright, trade secret, and other proprietary rights. "
            "The Contractor waives any moral rights in the work product."
        ),
    },
    {
        "parsed_clause_id": uuid.UUID("22222222-0000-0000-0000-000000000002"),
        "contract_id": _CONTRACT_ID,
        "clause_type": "payment_terms",
        "raw_text": (
            "The Client shall pay the Contractor a fixed fee of USD 8,500 per month, "
            "payable within Net 30 days of receipt of a valid invoice. Late payments "
            "shall accrue interest at the rate of 1.5% per month (18% per annum). "
            "All invoices must be submitted by the 1st of each calendar month. "
            "Disputed invoices must be raised in writing within 10 business days of receipt."
        ),
    },
    {
        "parsed_clause_id": uuid.UUID("33333333-0000-0000-0000-000000000003"),
        "contract_id": _CONTRACT_ID,
        "clause_type": "termination",
        "raw_text": (
            "Either party may terminate this Agreement for convenience upon 30 days' "
            "written notice to the other party. The Client may terminate this Agreement "
            "immediately, without notice or liability, in the event of: (a) the "
            "Contractor's material breach of any provision hereof; (b) the Contractor's "
            "insolvency or bankruptcy; or (c) the Contractor's conviction of a criminal "
            "offence. Upon termination, the Contractor shall deliver all work product "
            "and client data within 5 business days."
        ),
    },
    {
        "parsed_clause_id": uuid.UUID("44444444-0000-0000-0000-000000000004"),
        "contract_id": _CONTRACT_ID,
        "clause_type": "liability",
        "raw_text": (
            "In no event shall either party be liable to the other for any indirect, "
            "incidental, special, consequential, or punitive damages arising out of or "
            "related to this Agreement, even if advised of the possibility of such "
            "damages. The total cumulative liability of the Contractor to the Client "
            "under this Agreement shall not exceed the fees paid in the three (3) "
            "calendar months immediately preceding the claim. The Client agrees to "
            "indemnify and hold harmless the Contractor from any third-party claims "
            "arising from the Client's use of the deliverables."
        ),
    },
    {
        "parsed_clause_id": uuid.UUID("55555555-0000-0000-0000-000000000005"),
        "contract_id": _CONTRACT_ID,
        "clause_type": "confidentiality",
        "raw_text": (
            "Each party ('Recipient') agrees to hold in strict confidence all "
            "Confidential Information disclosed by the other party ('Discloser') and "
            "to use such information solely for the purpose of performing its "
            "obligations under this Agreement. 'Confidential Information' includes "
            "all trade secrets, non-public technical data, business plans, and client "
            "lists. This obligation of confidentiality shall survive termination of "
            "this Agreement for a period of five (5) years."
        ),
    },
    {
        "parsed_clause_id": uuid.UUID("66666666-0000-0000-0000-000000000006"),
        "contract_id": _CONTRACT_ID,
        "clause_type": "scope_of_work",
        "raw_text": (
            "The Contractor agrees to deliver the following services and deliverables: "
            "(1) Full-stack web application development per the statement of work "
            "attached as Exhibit A; (2) Weekly progress reports submitted every Friday; "
            "(3) Source code repository with full commit history; (4) Deployment to "
            "the Client's AWS infrastructure. Any changes to the scope of work must "
            "be agreed in writing and may result in a change order for additional fees."
        ),
    },
    {
        "parsed_clause_id": uuid.UUID("77777777-0000-0000-0000-000000000007"),
        "contract_id": _CONTRACT_ID,
        "clause_type": "governing_law",
        "raw_text": (
            "This Agreement shall be governed by and construed in accordance with the "
            "laws of the State of Delaware, without regard to its conflict of law "
            "provisions. Any dispute arising out of or relating to this Agreement "
            "shall first be subject to good-faith mediation. If mediation fails, "
            "the parties agree to submit to binding arbitration under the rules of "
            "the American Arbitration Association. The venue for arbitration shall "
            "be Wilmington, Delaware."
        ),
    },
    {
        "parsed_clause_id": uuid.UUID("88888888-0000-0000-0000-000000000008"),
        "contract_id": _CONTRACT_ID,
        "clause_type": "general",
        "raw_text": (
            "This Agreement constitutes the entire agreement between the parties with "
            "respect to the subject matter hereof and supersedes all prior agreements, "
            "understandings, negotiations, and representations, whether oral or written. "
            "No amendment or modification of this Agreement shall be valid unless made "
            "in writing and signed by authorized representatives of both parties."
        ),
    },
]


def get_mock_clauses() -> list[ClauseInput]:
    """
    Return a list of ``ClauseInput`` objects covering all supported clause types.

    These are realistic (but entirely fictional) contract clauses that exercise
    every branch of the DSPy pipeline.
    """
    return [ClauseInput(**raw) for raw in _MOCK_CLAUSES_RAW]
