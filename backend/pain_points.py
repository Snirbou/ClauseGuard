"""Missing-protection detection — the PRD's five pain points, by absence.

The per-clause pipeline can only assess text that exists. For a freelancer,
the sharper risk is usually what the contract does NOT say: no late-payment
penalty, no liability cap, no IP carve-out. This module diffs the clause
types found in a contract against the protections a freelance service
agreement is expected to address, and reports the gaps as contract-level
findings.

Pure module: no DB, no LLM. Deliberately a checklist, not a model — the
Layer 1 classifier already established which clause types are present, and
absence is a set operation on its output.

UPL framing: every detail is observational ("was not detected", "typically
address") — never prescriptive ("you should add").
"""

from __future__ import annotations

from dataclasses import dataclass

# The five pain points from PRD §1.2, keyed to the clause type whose absence
# leaves the pain point entirely unaddressed.
_CHECKLIST: list[dict[str, str]] = [
    {
        "pain_point": "payment_traps",
        "required_type": "payment_terms",
        "severity": "high",
        "title": "No payment terms detected",
        "detail": (
            "No payment-terms clause was detected in this contract. Freelance "
            "service agreements typically state the fee, the invoicing "
            "schedule, and the payment window — terms that are much harder to "
            "enforce when they are not written down. Their absence is "
            "commonly associated with delayed or disputed payment."
        ),
    },
    {
        "pain_point": "scope_creep",
        "required_type": "scope_of_work",
        "severity": "medium",
        "title": "No scope of work detected",
        "detail": (
            "No scope-of-work clause was detected. Agreements without a "
            "written scope commonly leave deliverables, revision rounds, and "
            "acceptance criteria undefined — the pattern most associated "
            "with scope creep and unpaid extra work."
        ),
    },
    {
        "pain_point": "ip_assignment",
        "required_type": "ip_assignment",
        "severity": "medium",
        "title": "No intellectual-property clause detected",
        "detail": (
            "No clause addressing intellectual-property ownership was "
            "detected. When a contract is silent on IP, ownership of the "
            "work product — and of any pre-existing tools reused in it — is "
            "left to default law, which varies by jurisdiction and often "
            "surprises both sides."
        ),
    },
    {
        "pain_point": "termination_asymmetry",
        "required_type": "termination",
        "severity": "medium",
        "title": "No termination clause detected",
        "detail": (
            "No termination clause was detected. Without one, the notice "
            "period, wind-down obligations, and payment for work in progress "
            "are undefined if either side ends the engagement early."
        ),
    },
    {
        "pain_point": "liability_gaps",
        "required_type": "liability",
        "severity": "high",
        "title": "No liability clause detected",
        "detail": (
            "No liability or indemnification clause was detected. Contracts "
            "that are silent on liability leave exposure uncapped by "
            "default; liability clauses typically address caps, exclusions "
            "of indirect damages, and indemnity obligations."
        ),
    },
]


@dataclass(frozen=True)
class MissingProtection:
    pain_point: str
    severity: str          # "high" | "medium"
    title: str
    detail: str


def detect_missing_protections(present_clause_types: set[str]) -> list[MissingProtection]:
    """Return one finding per expected protection absent from the contract."""
    findings: list[MissingProtection] = []
    for item in _CHECKLIST:
        if item["required_type"] not in present_clause_types:
            findings.append(
                MissingProtection(
                    pain_point=item["pain_point"],
                    severity=item["severity"],
                    title=item["title"],
                    detail=item["detail"],
                )
            )
    return findings


def checklist_size() -> int:
    return len(_CHECKLIST)


def required_type_by_pain_point() -> dict[str, str]:
    """pain_point -> the clause type whose presence satisfies it."""
    return {item["pain_point"]: item["required_type"] for item in _CHECKLIST}
