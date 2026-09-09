"""
dspy_pipeline.py — Core DSPy pipeline for ClauseGuard (Developer 2, Stage 2).

ARCHITECTURE
------------
1. ContractClauseAnalysisV2  — DSPy Signature (defines I/O contract for the LLM)
2. ClauseAnalyzerV2          — DSPy Module (wraps ChainOfThought)
3. configure_lm()            — Sets the global DSPy LM (OpenAI / Ollama)
4. process_clauses()         — Batch-processes a list of ClauseInput → ClauseAnalysisResult
"""

from __future__ import annotations

import os
import re

import dspy

from logger import get_logger
from schemas import ClauseAnalysisResult, ClauseInput

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# 1. DSPy Signature
# ---------------------------------------------------------------------------

class ContractClauseAnalysisV2(dspy.Signature):
    """
    Analyze a single legal contract clause and produce a plain-language
    explanation alongside a detailed risk assessment.

    You are an expert legal document assistant helping ordinary people understand
    the contracts they sign. Be concise, factual, and avoid legal jargon.
    """

    # --- Inputs ---
    raw_text: str = dspy.InputField(
        desc=(
            "The verbatim text of the legal clause extracted from the contract PDF."
        )
    )
    clause_type: str = dspy.InputField(
        desc=(
            "The predicted semantic category of this clause "
            "(e.g. 'ip_assignment', 'payment_terms', 'termination', "
            "'liability', 'confidentiality', 'scope_of_work', "
            "'governing_law', 'general')."
        )
    )

    # --- Outputs ---
    plain_language_summary: str = dspy.OutputField(
        desc=(
            "A 2–4 sentence plain-English explanation of what this clause means "
            "for the person signing the contract. Highlight any important "
            "obligations, rights, or restrictions that affect the signer."
        )
    )
    risk_factors: str = dspy.OutputField(
        desc=(
            "A comma-separated list of specific reasons why this clause might be "
            "problematic or risky for the signer. E.g., 'No pre-existing IP carve-out, "
            "Uncapped liability'. If no major risks, output 'None'."
        )
    )
    dspy_risk_score: str = dspy.OutputField(
        desc=(
            "A single float value between 0.0 and 1.0 representing the risk severity. "
            "0.0 is completely harmless, 1.0 is extremely dangerous/burdensome. "
            "Output ONLY the float number, nothing else."
        )
    )


# ---------------------------------------------------------------------------
# 2. DSPy Module
# ---------------------------------------------------------------------------

class ClauseAnalyzerV2(dspy.Module):
    """
    A DSPy module that uses ChainOfThought reasoning to analyze legal clauses.
    """

    def __init__(self) -> None:
        super().__init__()
        self.analyze = dspy.ChainOfThought(ContractClauseAnalysisV2)

    def forward(self, raw_text: str, clause_type: str) -> dspy.Prediction:
        """Run the analysis."""
        return self.analyze(raw_text=raw_text, clause_type=clause_type)


# ---------------------------------------------------------------------------
# 3. LLM Configuration
# ---------------------------------------------------------------------------

# DSPy 3.3 leaves `dspy.LM(temperature=None)`, which omits the parameter and
# lets the provider default apply — 1.0 for OpenAI. Two things depend on the
# task LM being deterministic instead:
#
#   * clause results are cached by a content hash (analysis_service), so a
#     sampled answer makes the same clause return different text on a cache
#     miss than it did on the run that populated the cache;
#   * optimizer trial scores are only comparable to each other when the
#     variation between them comes from the prompt, not from sampling.
#
# This does not flatten MIPROv2's instruction search: its proposer builds its
# own LM at `init_temperature` (1.0) and swaps it in with `dspy.context`
# (dspy/propose/grounded_proposer.py), so candidate instructions stay diverse
# while the program being scored stays deterministic.
TASK_TEMPERATURE = 0.0


def configure_lm(
    provider: str = "openai",
    model: str = "gpt-4o-mini",
    api_key: str | None = None,
    base_url: str | None = None,
) -> None:
    if provider == "openai":
        resolved_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not resolved_key:
            raise OSError(
                "OPENAI_API_KEY is not set. Add it to backend/.env."
            )
        lm = dspy.LM(
            model=f"openai/{model}",
            api_key=resolved_key,
            temperature=TASK_TEMPERATURE,
        )

    elif provider == "ollama":
        # No API key required for local Ollama. Use the ollama_chat/ prefix so
        # LiteLLM routes through the /api/chat endpoint, which matches how
        # chat-tuned models (llama3, mistral, etc.) expect to be prompted.
        resolved_base_url = (
            base_url
            or os.environ.get("OLLAMA_BASE_URL")
            or "http://localhost:11434"
        )
        lm = dspy.LM(
            model=f"ollama_chat/{model}",
            api_base=resolved_base_url,
            api_key="",
            temperature=TASK_TEMPERATURE,
        )

    else:
        raise ValueError(f"Unsupported provider '{provider}'.")

    dspy.configure(lm=lm)
    logger.info("DSPy LM configured: provider=%s, model=%s", provider, model)


# ---------------------------------------------------------------------------
# 4. Batch Processing
# ---------------------------------------------------------------------------

def _parse_risk_factors(raw: str) -> list[str]:
    """Parse comma-separated string or numbered list into a Python list."""
    if not raw or raw.strip().lower() in ("none", "n/a", "null"):
        return []
    # Try splitting by newline first if it looks like a list
    if "\n" in raw:
        items = [re.sub(r"^[\-\*\d\.\s]+", "", line).strip() for line in raw.split("\n")]
    else:
        items = [item.strip() for item in raw.split(",")]
    return [item for item in items if item]


# Any decimal or integer, including a bare fractional form like ".85".
_NUMBER = re.compile(r"\d*\.\d+|\d+")

#: Returned when the model's answer contains no number at all. Deliberately
#: mid-scale: an unparseable answer is unknown risk, not low risk.
UNPARSEABLE_RISK_SCORE = 0.5


def _parse_risk_score(raw: str) -> float:
    """Extract the risk score from the model's answer, clamped to 0.0-1.0.

    The previous pattern was ``0?\\.\\d+``, which made the optional leading
    zero match nothing and let the search start mid-number: on the answer
    "1.0" it matched the substring ".0" and returned **0.0**. The highest
    possible risk score parsed as the lowest one, and silently — the value is
    in range, so nothing downstream could notice. "1.00" failed the same way.

    Reading the whole number fixes that. Preferring a candidate already in
    [0, 1] keeps a prose answer like "clause 3.2 scores 0.4" from latching
    onto the section number, and a trailing "%" is read as a percentage
    because a model asked for 0-1 that answers "85%" means 0.85, not 1.0.
    """
    try:
        text = raw if isinstance(raw, str) else str(raw)
        candidates = [float(token) for token in _NUMBER.findall(text)]
    except (TypeError, ValueError):
        return UNPARSEABLE_RISK_SCORE

    if not candidates:
        return UNPARSEABLE_RISK_SCORE

    in_range = [value for value in candidates if 0.0 <= value <= 1.0]
    if in_range:
        return in_range[0]

    value = candidates[0]
    if "%" in text:
        value /= 100.0
    return max(0.0, min(1.0, value))


def _score_to_level(score: float) -> str:
    """Convert float score to categorical risk level."""
    if score < 0.4:
        return "low"
    if score < 0.7:
        return "medium"
    return "high"


def process_clauses(
    clauses: list[ClauseInput],
    analyzer: dspy.Module | None = None,
) -> list[ClauseAnalysisResult]:
    """
    Run the DSPy pipeline over a list of clauses.
    Accepts an injected analyzer (for optimized programs).
    """
    analyzer = analyzer or ClauseAnalyzerV2()
    results: list[ClauseAnalysisResult] = []

    for clause in clauses:
        logger.info(
            "Processing clause [%s] (id: %s...)",
            clause.clause_type,
            str(clause.parsed_clause_id)[:8],
        )
        try:
            prediction = analyzer(
                raw_text=clause.raw_text,
                clause_type=clause.clause_type,
            )

            score = _parse_risk_score(prediction.dspy_risk_score)
            factors = _parse_risk_factors(prediction.risk_factors)
            level = _score_to_level(score)

            result = ClauseAnalysisResult(
                parsed_clause_id=clause.parsed_clause_id,
                contract_id=clause.contract_id,
                clause_type=clause.clause_type,
                clause_type_confidence=clause.clause_type_confidence,
                plain_language_summary=prediction.plain_language_summary.strip(),
                risk_factors=factors,
                dspy_risk_score=score,
                risk_level=level,
            )
            results.append(result)

        except Exception as exc:
            logger.error("Error processing clause %s: %s", clause.parsed_clause_id, exc, exc_info=True)

    return results
