"""Add the parent ml_training/ directory to sys.path so scripts can `from src...`.

Imported at the top of every script in this folder. Lets us run
`python backend/ml_training/scripts/04_train.py` from the repo root without
installing the sandbox as a package.
"""
from __future__ import annotations

import sys
from pathlib import Path

ML_TRAINING_DIR = Path(__file__).resolve().parents[1]
if str(ML_TRAINING_DIR) not in sys.path:
    sys.path.insert(0, str(ML_TRAINING_DIR))
