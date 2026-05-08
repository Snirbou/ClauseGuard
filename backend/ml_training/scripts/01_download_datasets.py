"""Download LEDGAR (primary, training) and CUAD (secondary, evaluation only).

Caches into backend/ml_training/data_cache/. Idempotent — HuggingFace `datasets`
handles the local cache.

    python backend/ml_training/scripts/01_download_datasets.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import _path  # noqa: F401

CACHE_DIR = Path(__file__).resolve().parents[1] / "data_cache"


def main() -> int:
    try:
        from datasets import load_dataset  # type: ignore
    except ImportError:
        print("[01_download] `datasets` not installed.", file=sys.stderr)
        return 1

    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    print("[01_download] Loading LEDGAR (coastalcph/lex_glue, config='ledgar')...")
    ledgar = load_dataset("coastalcph/lex_glue", "ledgar", cache_dir=str(CACHE_DIR))
    print(f"[01_download] LEDGAR splits: { {k: len(v) for k, v in ledgar.items()} }")

    print("[01_download] Loading CUAD (theatticusproject/cuad-qa)...")
    try:
        cuad = load_dataset("theatticusproject/cuad-qa", cache_dir=str(CACHE_DIR), trust_remote_code=True)
        print(f"[01_download] CUAD splits: { {k: len(v) for k, v in cuad.items()} }")
    except Exception as exc:  # noqa: BLE001
        print(f"[01_download] CUAD download failed (non-fatal — used for eval only): {exc}", file=sys.stderr)

    print("[01_download] Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
