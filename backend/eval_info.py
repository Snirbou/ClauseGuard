"""Risk-evaluation sidecar reader for the evaluation dashboard (AC-R05).

``eval/risk_eval.py`` measures high-risk precision/recall against labelled
clauses and writes ``models/risk_eval.json``. This module is the read side —
the one thing ``main.py`` imports to put those numbers on ``/api/metrics``.

Two properties matter here and nothing else:

* **It never raises.** A missing, truncated, or hand-edited sidecar must
  degrade the dashboard to "not measured yet", never take the metrics
  endpoint down. Same defensive contract as ``classifier.classifier_info()``.
* **It stays import-light.** Only the standard library — no DSPy, no
  classifier, no spaCy — so importing it costs the API nothing and cannot
  disturb the numpy-before-dspy import order the classifier depends on.

The sidecar is written only for a real LLM provider. A ``fake``-provider run
measures the offline demo analyzer (scores derived from a text hash), so it
writes ``eval/results/risk_eval.provisional.json`` instead and is deliberately
invisible here: the dashboard must never present plumbing output as a
measured result.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parent

#: The committed, metrics-only sidecar produced by ``eval/risk_eval.py``.
RISK_EVAL_PATH = BACKEND_DIR / "models" / "risk_eval.json"

#: AcceptanceCriteria section 3.1 — the numbers this project promises.
TARGETS: dict[str, float] = {"precision": 0.75, "recall": 0.70}

#: Shown in the dashboard while Phase 4 (the key-gated LLM work) is pending.
NOT_MEASURED_REASON = "not yet measured - requires an LLM key (Phase 4)"


def _not_measured(**extra: Any) -> dict[str, Any]:
    return {
        "measured": False,
        "targets": dict(TARGETS),
        "reason": NOT_MEASURED_REASON,
        **extra,
    }


def risk_eval_info() -> dict[str, Any]:
    """High-risk precision/recall for ``/api/metrics``; never raises.

    Returns the sidecar's contents with ``measured: true`` when one is
    present and parseable, otherwise a ``measured: false`` envelope carrying
    the targets and the reason. A sidecar that exists but is unreadable adds
    an ``error`` field so a broken artifact is visible on the dashboard
    rather than indistinguishable from a run that never happened.

    Read on every call rather than cached: the file is a couple of kilobytes,
    ``/api/metrics`` is not a hot path, and re-reading means a fresh
    measurement lands without a restart.
    """
    path = RISK_EVAL_PATH
    try:
        if not path.exists():
            return _not_measured()
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return _not_measured(error=f"{type(exc).__name__}: {exc}")

    if not isinstance(data, dict):
        return _not_measured(error=f"expected a JSON object, got {type(data).__name__}")

    info = dict(data)
    info.setdefault("targets", dict(TARGETS))
    # The presence of a readable sidecar *is* the measurement; the writer only
    # ever puts a real-provider run here.
    info["measured"] = True
    return info
