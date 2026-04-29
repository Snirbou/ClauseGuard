"""
dspy_pipeline.py — Core DSPy pipeline for ClauseGuard (Developer 2, Step 1).

ARCHITECTURE
------------
1. ContractClauseAnalysis  — DSPy Signature (defines I/O contract for the LLM)
2. ClauseAnalyzer          — DSPy Module (wraps ChainOfThought)
3. configure_lm()          — Sets the global DSPy LM (OpenAI by default)
4. process_clauses()       — Batch-processes a list of ClauseInput → ClauseAnalysisResult

STAGE 1 FOCUS
-------------
This module focuses on the core logic flow: DB/mock data → DSPy → structured output.
Complex risk scoring (numeric), DSPy optimizers (MIPROv2), and prompt compilation
will be added in Stage 2.

LLM PROVIDER
------------
Defaults to OpenAI gpt-4o-mini (cost-efficient for development).
To switch to Ollama (local/free):

    configure_lm(provider="ollama", model="llama3.2")

Both paths use the same dspy.LM API.
"""

from __future__ import annotations

import os

import dspy

from schemas import ClauseAnalysisResult, ClauseInput


# ---------------------------------------------------------------------------
# 1. DSPy Signature — defines the I/O contract for the LLM
# ---------------------------------------------------------------------------

class ContractClauseAnalysis(dspy.Signature):
    """
    Analyze a single legal contract clause and produce a plain-language
    explanation alongside an initial risk assessment for a non-lawyer user.

    You are a legal document assistant helping ordinary people understand
    the contracts they sign.  Be concise, factual, and avoid legal jargon.
    Risk level must be exactly one of: low, medium, or high.
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
            "for the person signing the contract.  Highlight any important "
            "obligations, rights, or restrictions that affect the signer."
        )
    )
    initial_risk_assessment: str = dspy.OutputField(
        desc=(
            "A single word risk level: 'low', 'medium', or 'high'.  "
            "'high' means the clause significantly limits the signer's rights or "
            "imposes major obligations.  'medium' means the clause is notable but "
            "standard.  'low' means the clause is routine and non-burdensome."
        )
    )


# ---------------------------------------------------------------------------
# 2. DSPy Module — wraps ChainOfThought over the Signature
# ---------------------------------------------------------------------------

class ClauseAnalyzer(dspy.Module):
    """
    A DSPy module that uses ChainOfThought reasoning to analyze legal clauses.

    ChainOfThought is used (rather than Predict) so that the LLM is
    encouraged to reason step-by-step before producing the final outputs.
    This improves output quality, especially for the risk assessment, and
    makes the reasoning transparent for future DSPy optimization.
    """

    def __init__(self) -> None:
        super().__init__()
        self.analyze = dspy.ChainOfThought(ContractClauseAnalysis)

    def forward(self, raw_text: str, clause_type: str) -> dspy.Prediction:
        """
        Run the ChainOfThought analysis on a single clause.

        Args:
            raw_text:    Verbatim clause text.
            clause_type: Predicted semantic category from the classifier.

        Returns:
            A ``dspy.Prediction`` with ``plain_language_summary`` and
            ``initial_risk_assessment`` fields.
        """
        return self.analyze(raw_text=raw_text, clause_type=clause_type)


# ---------------------------------------------------------------------------
# 3. LLM Configuration
# ---------------------------------------------------------------------------

def configure_lm(
    provider: str = "openai",
    model: str = "gpt-4o-mini",
    api_key: str | None = None,
    base_url: str | None = None,
) -> None:
    """
    Configure the global DSPy language model.

    Parameters
    ----------
    provider : str
        LLM provider.  Supported values:
          - "openai"  — Uses OpenAI API (requires OPENAI_API_KEY in .env)
          - "ollama"  — Uses a locally-running Ollama server (free, no key needed)
    model : str
        Model identifier.
        OpenAI examples : "gpt-4o-mini" (cheap dev), "gpt-4o" (higher quality)
        Ollama examples : "llama3.2", "mistral", "phi3"
    api_key : str | None
        Override API key.  If None, reads OPENAI_API_KEY from the environment.
    base_url : str | None
        Override base URL.  Set automatically for Ollama if not provided.

    Examples
    --------
    # OpenAI (default)
    configure_lm()

    # Ollama local server
    configure_lm(provider="ollama", model="llama3.2")

    # Explicit OpenAI model
    configure_lm(model="gpt-4o")
    """
    if provider == "openai":
        resolved_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not resolved_key:
            raise EnvironmentError(
                "OPENAI_API_KEY is not set.  "
                "Add it to backend/.env or export it as an environment variable."
            )
        lm = dspy.LM(
            model=f"openai/{model}",
            api_key=resolved_key,
        )

    elif provider == "ollama":
        resolved_base_url = base_url or "http://localhost:11434"
        lm = dspy.LM(
            model=f"ollama/{model}",
            api_base=resolved_base_url,
        )

    else:
        raise ValueError(
            f"Unsupported provider '{provider}'.  Choose 'openai' or 'ollama'."
        )

    dspy.configure(lm=lm)
    print(f"[DSPy] LM configured: provider={provider}, model={model}")


# ---------------------------------------------------------------------------
# 4. Batch Processing
# ---------------------------------------------------------------------------

def process_clauses(clauses: list[ClauseInput]) -> list[ClauseAnalysisResult]:
    """
    Run the ClauseAnalyzer DSPy pipeline over a list of clauses.

    This is the main integration point that Developer 1's FastAPI endpoint
    (or the CLI runner) will call.

    Parameters
    ----------
    clauses : list[ClauseInput]
        Parsed clauses from Developer 1's handoff (DB or mock data).

    Returns
    -------
    list[ClauseAnalysisResult]
        Enriched results ready to be stored in the ``risk_scores`` table
        or returned directly to the frontend.

    Notes
    -----
    Processing is synchronous and sequential in Stage 1.
    Concurrent processing (asyncio.gather / ThreadPoolExecutor) will be
    added in Stage 2 once the pipeline is stable.
    """
    analyzer = ClauseAnalyzer()
    results: list[ClauseAnalysisResult] = []

    for clause in clauses:
        print(
            f"  >> Processing clause [{clause.clause_type}] "
            f"(id: {str(clause.parsed_clause_id)[:8]}...)"
        )
        try:
            prediction = analyzer(
                raw_text=clause.raw_text,
                clause_type=clause.clause_type,
            )

            # Normalise risk level to lowercase and guard against unexpected values
            raw_risk = prediction.initial_risk_assessment.strip().lower()
            valid_risk_levels = {"low", "medium", "high"}
            risk_level = raw_risk if raw_risk in valid_risk_levels else "medium"

            result = ClauseAnalysisResult(
                parsed_clause_id=clause.parsed_clause_id,
                contract_id=clause.contract_id,
                clause_type=clause.clause_type,
                plain_language_summary=prediction.plain_language_summary.strip(),
                initial_risk_assessment=risk_level,
            )
            results.append(result)

        except Exception as exc:  # noqa: BLE001
            # Log the error but continue processing remaining clauses
            print(f"  x Error processing clause {clause.parsed_clause_id}: {exc}")

    return results
