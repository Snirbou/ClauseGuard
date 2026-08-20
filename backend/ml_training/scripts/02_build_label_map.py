"""Audit LEDGAR -> CG8 mapping coverage and emit artifacts/label_map.json.

Reports:
  * The set of LEDGAR labels in the corpus.
  * For each, the CG8 destination (mapped or 'general').
  * Per-CG8 counts in the train split.

    python backend/ml_training/scripts/02_build_label_map.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import _path  # noqa: F401

from src.label_map import LEDGAR_TO_CG8, map_label  # noqa: E402

ARTIFACTS_DIR = Path(__file__).resolve().parents[1] / "artifacts"
CACHE_DIR = Path(__file__).resolve().parents[1] / "data_cache"


def main() -> int:
    try:
        from datasets import load_dataset  # type: ignore
    except ImportError:
        print("[02_build_label_map] `datasets` not installed.", file=sys.stderr)
        return 1

    ds = load_dataset("coastalcph/lex_glue", "ledgar", cache_dir=str(CACHE_DIR))
    label_names: list[str] = ds["train"].features["label"].names

    cg8_counts: Counter[str] = Counter()
    label_dest: dict[str, str] = {}
    for raw in label_names:
        dest = map_label(raw)
        label_dest[raw] = dest

    for example in ds["train"]:
        cg8_counts[map_label(label_names[example["label"]])] += 1

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = ARTIFACTS_DIR / "label_map.json"
    out_path.write_text(json.dumps({
        "ledgar_labels": label_names,
        "ledgar_to_cg8": label_dest,
        "explicit_dict_size": len(LEDGAR_TO_CG8),
        "cg8_train_counts": dict(cg8_counts),
    }, indent=2))

    print(f"[02_build_label_map] Wrote {out_path}")
    print("[02_build_label_map] Train-split CG8 counts:")
    for cg8, n in cg8_counts.most_common():
        print(f"  {cg8:18s} {n:>8d}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
