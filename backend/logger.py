"""
logger.py — Structured logging for the ClauseGuard DSPy pipeline.

Provides a pre-configured logger that all pipeline modules import.
Replaces ad-hoc print() calls with structured, levelled log messages.

USAGE
-----
    from logger import get_logger
    logger = get_logger(__name__)
    logger.info("Processing clause %s", clause_id)
    logger.error("Failed clause %s: %s", clause_id, exc)
"""

from __future__ import annotations

import logging
import sys

_LOG_FORMAT = "[%(levelname)s] %(asctime)s | %(name)s | %(message)s"
_DATE_FORMAT = "%H:%M:%S"

# Module-level flag so we only configure the root logger once.
_configured = False


def _configure_root_logger(level: int = logging.INFO) -> None:
    global _configured
    if _configured:
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT))

    root = logging.getLogger("clauseguard")
    root.setLevel(level)
    root.addHandler(handler)
    root.propagate = False  # Don't bubble up to the root Python logger

    _configured = True


def get_logger(name: str, level: int | None = None) -> logging.Logger:
    """
    Return a logger namespaced under 'clauseguard.<name>'.

    Parameters
    ----------
    name : str
        Typically __name__ of the calling module.
    level : int | None
        Override log level for this specific logger (e.g. logging.DEBUG).
        If None, inherits from the parent 'clauseguard' logger.
    """
    _configure_root_logger()
    logger = logging.getLogger(f"clauseguard.{name}")
    if level is not None:
        logger.setLevel(level)
    return logger


# ---------------------------------------------------------------------------
# Pipeline run statistics helper
# ---------------------------------------------------------------------------

class RunStats:
    """
    Tracks success/failure counts for a single pipeline run.
    Use as a context manager or directly.

    Example
    -------
        stats = RunStats(total=8)
        stats.record_success()
        stats.record_failure("clause-uuid", "Timeout")
        stats.log_summary(logger)
    """

    def __init__(self, total: int) -> None:
        self.total = total
        self.succeeded = 0
        self.failed = 0
        self._failures: list[tuple[str, str]] = []

    def record_success(self) -> None:
        self.succeeded += 1

    def record_failure(self, clause_id: str, reason: str) -> None:
        self.failed += 1
        self._failures.append((clause_id, reason))

    def log_summary(self, logger: logging.Logger) -> None:
        logger.info(
            "Run complete: %d/%d succeeded, %d failed.",
            self.succeeded,
            self.total,
            self.failed,
        )
        for cid, reason in self._failures:
            logger.warning("  FAILED clause %s: %s", cid, reason)
