"""Faithfulness judge — the LLM half of the optimizer's quality metric.

The old ``quality_metric`` could not tell a good summary from a fluent lie:
its summary component was ``len(summary) > 30``. Anything wordy scored full
marks, so optimizing against it rewarded length, not accuracy. This module
supplies the missing signal — an LLM that reads the clause and the summary
side by side and reports whether every claim in the summary is supported by
the clause text.

Kept out of ``optimizer.py`` for the same reason ``contract_summary.py`` is
kept out of ``dspy_pipeline.py``: the judge is a separate program with its
own signature, and the optimizer should be able to import it without
dragging the whole optimization stack into a test.

Two properties matter for cost and for reproducibility:

* **Judging is memoised.** MIPROv2 re-evaluates the same (clause, summary)
  pair many times across trials — identical demos, identical predictions
  under a deterministic task LM. Each distinct pair is judged once per
  process. DSPy's own LM cache would catch most repeats anyway; this keeps
  the metric fast even when that cache is cold or disabled.
* **A judge failure is not a zero.** If the judge errors or the adapter
  cannot parse its answer, the verdict is returned with ``judged=False`` so
  the caller can fall back to a neutral score. Scoring a candidate program
  0.0 because the *judge* broke would corrupt the optimizer's search.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import dspy

from logger import get_logger

logger = get_logger(__name__)

# Distinct (clause, summary) pairs kept in the memo. One optimizer run judges
# at most trials x valset distinct pairs, which is far below this; the cap
# only exists so a long-lived process cannot grow without bound.
_CACHE_MAXSIZE = 4_096


class SummaryFaithfulness(dspy.Signature):
    """Check a plain-language summary against the contract clause it describes.

    You are auditing an automated contract-analysis tool. You are given one
    clause of a freelance service agreement and the plain-English summary the
    tool produced for it. Decide whether the summary is faithful.

    A summary is faithful when every factual claim it makes is supported by
    the clause text: the parties, the obligations, and every number, duration,
    amount and deadline. A summary is NOT faithful if it invents a term the
    clause does not contain, states an obligation as stronger or weaker than
    the clause does, attributes an obligation to the wrong party, or omits a
    term that materially changes what the clause does.

    Judge only faithfulness. Do not mark a summary unfaithful for being short,
    plainly worded, informal, or for leaving out minor detail that does not
    change the meaning. Simplification is the tool's purpose; fabrication is
    the failure being looked for.
    """

    clause_text: str = dspy.InputField(desc="The contract clause, verbatim.")
    summary: str = dspy.InputField(
        desc="The plain-English summary produced for that clause."
    )
    faithful: bool = dspy.OutputField(
        desc="True when every claim in the summary is supported by the clause."
    )
    unsupported_claims: list[str] = dspy.OutputField(
        desc="Each claim in the summary that the clause does not support, "
        "quoted from the summary. Empty when the summary is faithful."
    )


@dataclass(frozen=True)
class FaithfulnessVerdict:
    """Outcome of one judge call.

    ``judged`` is False when the judge itself failed — no LM configured, an
    API error, or an answer the adapter could not parse. ``faithful`` is then
    meaningless and callers must fall back rather than treat it as a verdict.
    """

    faithful: bool
    unsupported_claims: list[str] = field(default_factory=list)
    judged: bool = True


_UNJUDGED = FaithfulnessVerdict(faithful=False, unsupported_claims=[], judged=False)

_program: dspy.Module | None = None
_cache: dict[tuple[str, str], FaithfulnessVerdict] = {}


def _get_program() -> dspy.Module:
    """The judge program, built once per process."""
    global _program
    if _program is None:
        _program = dspy.ChainOfThought(SummaryFaithfulness)
    return _program


def use_program(program: Any) -> None:
    """Install a replacement judge program and clear the memo.

    ``program`` is any callable accepting ``clause_text=`` and ``summary=``
    keywords and returning an object with ``faithful`` and
    ``unsupported_claims`` attributes. The offline twin in ``fake_llm``
    is installed this way under ``DSPY_PROVIDER=fake`` so the evaluation
    harness exercises the whole metric without an LM; tests install stubs.
    """
    global _program
    _program = program
    _cache.clear()


def reset_judge() -> None:
    """Drop the compiled program and the memo. For tests and CLI reruns."""
    global _program
    _program = None
    _cache.clear()


def cache_size() -> int:
    """Number of distinct (clause, summary) pairs judged so far."""
    return len(_cache)


def _coerce_claims(raw: object) -> list[str]:
    """Normalise the judge's ``unsupported_claims`` into a list of strings."""
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
    if isinstance(raw, str):
        text = raw.strip()
        if not text or text.lower() in {"none", "n/a", "[]"}:
            return []
        return [part.strip() for part in text.split(";") if part.strip()]
    return []


def judge_faithfulness(clause_text: str, summary: str) -> FaithfulnessVerdict:
    """Ask the configured LM whether ``summary`` is faithful to ``clause_text``.

    Never raises: a judge that cannot run returns ``judged=False``.
    """
    clause_text = (clause_text or "").strip()
    summary = (summary or "").strip()
    if not clause_text or not summary:
        # Nothing to support, or nothing to check. Not a judge failure — an
        # empty summary is unfaithful by construction.
        return FaithfulnessVerdict(faithful=False, unsupported_claims=[], judged=True)

    key = (clause_text, summary)
    cached = _cache.get(key)
    if cached is not None:
        return cached

    try:
        prediction = _get_program()(clause_text=clause_text, summary=summary)
        verdict = FaithfulnessVerdict(
            faithful=bool(prediction.faithful),
            unsupported_claims=_coerce_claims(
                getattr(prediction, "unsupported_claims", [])
            ),
            judged=True,
        )
    except Exception as exc:  # noqa: BLE001 — any judge failure must be survivable
        logger.warning("Faithfulness judge unavailable (%s): %s", type(exc).__name__, exc)
        return _UNJUDGED

    if len(_cache) < _CACHE_MAXSIZE:
        _cache[key] = verdict
    return verdict
