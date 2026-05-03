"""
optimizer.py — DSPy Optimization Workflows for ClauseGuard.

Provides training data, a custom evaluation metric, and functions to run
BootstrapFewShot (fast) or MIPROv2 (thorough) optimizers. Saves the compiled
program to disk for subsequent runs.
"""

from __future__ import annotations

import os

import dspy
from dspy.teleprompt import BootstrapFewShot, MIPROv2

from dspy_pipeline import ClauseAnalyzerV2, _parse_risk_factors, _parse_risk_score
from logger import get_logger

logger = get_logger(__name__)

OPTIMIZED_PROGRAM_PATH = os.path.join(os.path.dirname(__file__), "optimized_pipeline.json")


# ---------------------------------------------------------------------------
# 1. Training Data (Examples)
# ---------------------------------------------------------------------------

TRAIN_DATA = [
    dspy.Example(
        raw_text="The Contractor retains all intellectual property rights to the background technology. However, the Contractor grants the Client a non-exclusive, worldwide, royalty-free license to use the background technology solely in connection with the Deliverables.",
        clause_type="ip_assignment",
        plain_language_summary="You keep the rights to your pre-existing tools and technology. The client only gets a license to use your tools as part of the final project you deliver to them.",
        risk_factors="None",
        dspy_risk_score="0.1",
    ).with_inputs("raw_text", "clause_type"),
    
    dspy.Example(
        raw_text="The Client shall pay the Contractor a fixed fee of USD 5,000 upon execution of this Agreement, and USD 5,000 upon completion. No expenses will be reimbursed unless pre-approved in writing.",
        clause_type="payment_terms",
        plain_language_summary="You will receive $5,000 upfront and $5,000 when the work is finished. Keep in mind that you cannot claim any expenses unless the client approves them in writing beforehand.",
        risk_factors="Requires written pre-approval for expenses",
        dspy_risk_score="0.3",
    ).with_inputs("raw_text", "clause_type"),

    dspy.Example(
        raw_text="Contractor shall indemnify, defend, and hold harmless Client from and against any and all claims, damages, liabilities, costs, and expenses (including reasonable attorneys' fees) arising out of Contractor's gross negligence or willful misconduct.",
        clause_type="liability",
        plain_language_summary="If your gross negligence or intentional bad behavior causes a lawsuit or damages, you must pay the client's legal fees and cover their losses.",
        risk_factors="Indemnification obligation, Covers attorney fees",
        dspy_risk_score="0.6",
    ).with_inputs("raw_text", "clause_type"),

    dspy.Example(
        raw_text="This Agreement shall be governed by the laws of the State of New York. The parties agree to exclusive jurisdiction in the courts located in Manhattan, New York.",
        clause_type="governing_law",
        plain_language_summary="This contract is governed by New York law. If there is a legal dispute, you must go to court in Manhattan, New York.",
        risk_factors="Forces litigation in New York (potential travel/cost burden)",
        dspy_risk_score="0.5",
    ).with_inputs("raw_text", "clause_type"),
    
    dspy.Example(
        raw_text="During the Term and for a period of two (2) years thereafter, Contractor shall not directly or indirectly solicit any employees or clients of the Client.",
        clause_type="general",
        plain_language_summary="You are forbidden from trying to hire the client's employees or poach their customers while working for them and for two years after the contract ends.",
        risk_factors="2-year non-solicitation clause limits future business, Covers both employees and clients",
        dspy_risk_score="0.8",
    ).with_inputs("raw_text", "clause_type"),
]


# ---------------------------------------------------------------------------
# 2. Evaluation Metric
# ---------------------------------------------------------------------------

def quality_metric(example: dspy.Example, pred: dspy.Prediction, trace: any = None) -> float:
    """
    Evaluates the quality of the LLM's prediction.
    Returns a score between 0.0 and 1.0.
    """
    score = 0.0

    # 1. Summary length & quality (0.0 to 0.4)
    summary = pred.plain_language_summary.strip()
    if len(summary) > 30:
        score += 0.4

    # 2. Risk factors parsing (0.0 to 0.3)
    factors = _parse_risk_factors(pred.risk_factors)
    # If the ground truth has 'None', we reward the model for recognizing low risk.
    # Otherwise, we reward the model for extracting at least one factor.
    if example.risk_factors.lower() == "none":
        if not factors or factors[0].lower() == "none":
            score += 0.3
    elif len(factors) > 0:
        score += 0.3

    # 3. Numeric risk score validity & accuracy (0.0 to 0.3)
    try:
        val = float(_parse_risk_score(pred.dspy_risk_score))
        if 0.0 <= val <= 1.0:
            expected_val = float(example.dspy_risk_score)
            # Full points if within 0.2 of ground truth, partial otherwise
            diff = abs(val - expected_val)
            if diff <= 0.2:
                score += 0.3
            elif diff <= 0.4:
                score += 0.15
    except Exception:
        pass

    return score


# ---------------------------------------------------------------------------
# 3. Optimization Workflows
# ---------------------------------------------------------------------------

def run_bootstrap_fewshot() -> dspy.Module:
    """
    Run BootstrapFewShot optimizer. Fast (~5-10 LLM calls).
    Compiles the module with few-shot examples from TRAIN_DATA.
    """
    logger.info("Starting BootstrapFewShot optimization...")
    analyzer = ClauseAnalyzerV2()
    
    teleprompter = BootstrapFewShot(
        metric=quality_metric,
        max_bootstrapped_demos=3,
        max_labeled_demos=5,
    )
    
    optimized_analyzer = teleprompter.compile(
        analyzer,
        trainset=TRAIN_DATA,
    )
    
    optimized_analyzer.save(OPTIMIZED_PROGRAM_PATH)
    logger.info("Optimization complete. Program saved to %s", OPTIMIZED_PROGRAM_PATH)
    return optimized_analyzer


def run_miprov2() -> dspy.Module:
    """
    Run MIPROv2 optimizer. Thorough and potentially slow (~50+ LLM calls).
    Generates dynamic prompt instructions and few-shot examples.
    """
    logger.info("Starting MIPROv2 optimization (this may take a while)...")
    analyzer = ClauseAnalyzerV2()
    
    # MIPROv2 requires a separate prompter LM. We use the currently configured one.
    teleprompter = MIPROv2(
        metric=quality_metric,
        auto="light", # 'light' does ~50-60 trials. 'heavy' does ~300.
    )
    
    optimized_analyzer = teleprompter.compile(
        analyzer,
        trainset=TRAIN_DATA,
        num_batches=2,
        max_bootstrapped_demos=3,
        max_labeled_demos=5,
        requires_permission_to_run=False,
    )
    
    optimized_analyzer.save(OPTIMIZED_PROGRAM_PATH)
    logger.info("MIPROv2 optimization complete. Program saved to %s", OPTIMIZED_PROGRAM_PATH)
    return optimized_analyzer


def load_optimized_analyzer() -> dspy.Module:
    """Load the compiled program if it exists, otherwise return a fresh one."""
    analyzer = ClauseAnalyzerV2()
    if os.path.exists(OPTIMIZED_PROGRAM_PATH):
        try:
            analyzer.load(OPTIMIZED_PROGRAM_PATH)
            logger.info("Loaded optimized DSPy program from %s", OPTIMIZED_PROGRAM_PATH)
        except Exception as exc:
            logger.warning("Failed to load optimized program: %s. Using unoptimized.", exc)
    else:
        logger.info("No optimized program found. Using unoptimized analyzer.")
    
    return analyzer
