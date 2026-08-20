"""UPL guardrails — automated prescriptive-language filter (AC-P02).

The PRD requires zero instances of advice-style language in user-facing
output ("you should", "we recommend", "we advise"). LLMs drift toward
advice even when prompted not to, so every generated summary passes through
``sanitize()`` before persistence: known prescriptive openers are rewritten
to observational equivalents, and each rewrite is counted so runs can report
how often the model needed correcting.

The replacements are deliberately narrow — phrases whose observational
substitution stays grammatical. Factual descriptions of the contract's own
obligations ("the clause requires you to deliver…") are not violations and
are left untouched.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# (pattern, replacement) — replacements chosen so the sentence still parses.
_REWRITES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\byou should consider\b", re.IGNORECASE), "some freelancers consider"),
    (re.compile(r"\byou should not\b", re.IGNORECASE), "freelancers commonly avoid agreeing to"),
    (re.compile(r"\byou should\b", re.IGNORECASE), "it is common to"),
    (re.compile(r"\bwe (?:strongly )?recommend that you\b", re.IGNORECASE), "a common practice is to"),
    (re.compile(r"\bwe (?:strongly )?recommend\b", re.IGNORECASE), "a common practice is"),
    (re.compile(r"\bwe advise (?:you )?(?:to )?\b", re.IGNORECASE), "a common practice is to "),
    (re.compile(r"\bour advice is\b", re.IGNORECASE), "a common observation is"),
    (re.compile(r"\bmy advice is\b", re.IGNORECASE), "a common observation is"),
    (re.compile(r"\byou need to renegotiate\b", re.IGNORECASE), "this term is often renegotiated"),
    (re.compile(r"\bmake sure (?:that )?you\b", re.IGNORECASE), "signers often verify that they"),
]

# Detection-only patterns for the compliance report: caught by tests/metrics
# even where no safe automated rewrite exists.
_DETECT_ONLY: list[re.Pattern[str]] = [
    re.compile(r"\byou must (?:sign|reject|refuse|walk away)\b", re.IGNORECASE),
]


@dataclass(frozen=True)
class SanitizeResult:
    text: str
    rewrites: int
    residual_flags: list[str]

    @property
    def clean(self) -> bool:
        return self.rewrites == 0 and not self.residual_flags


def sanitize(text: str) -> SanitizeResult:
    """Rewrite prescriptive phrasing to observational phrasing."""
    rewritten = text
    count = 0
    for pattern, replacement in _REWRITES:
        rewritten, n = pattern.subn(replacement, rewritten)
        count += n

    flags = [p.pattern for p in _DETECT_ONLY if p.search(rewritten)]
    return SanitizeResult(text=rewritten, rewrites=count, residual_flags=flags)


def violations(text: str) -> list[str]:
    """All prescriptive patterns present in ``text`` (for tests/metrics)."""
    found: list[str] = []
    for pattern, _replacement in _REWRITES:
        if pattern.search(text):
            found.append(pattern.pattern)
    found.extend(p.pattern for p in _DETECT_ONLY if p.search(text))
    return found
