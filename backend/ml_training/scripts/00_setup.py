"""Idempotent setup: ensure the spaCy model is installed.

Run once after `pip install -r backend/ml_training/requirements-dev.txt`:

    python backend/ml_training/scripts/00_setup.py

Safe to re-run; exits 0 if the model is already present.
"""
from __future__ import annotations

import os
import subprocess
import sys

import _path  # noqa: F401  side-effect: adds ml_training/ to sys.path

MODEL_NAME = os.environ.get("SPACY_MODEL", "en_core_web_lg")
MODEL_VERSION = "3.7.1"


def main() -> int:
    try:
        import spacy  # type: ignore
    except ImportError:
        print("[00_setup] spaCy is not installed. Run `pip install -r requirements-dev.txt` first.", file=sys.stderr)
        return 1

    try:
        spacy.load(MODEL_NAME)
        print(f"[00_setup] spaCy model '{MODEL_NAME}' already installed. OK.")
        return 0
    except OSError:
        pass

    print(f"[00_setup] Downloading spaCy model {MODEL_NAME}=={MODEL_VERSION}...")
    cmd = [sys.executable, "-m", "spacy", "download", f"{MODEL_NAME}=={MODEL_VERSION}"]
    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        print(f"[00_setup] Pinned download failed; falling back to latest {MODEL_NAME}.", file=sys.stderr)
        result = subprocess.run([sys.executable, "-m", "spacy", "download", MODEL_NAME], check=False)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
