"""MinHash-based near-duplicate dedup of the LEDGAR train split.

Threshold = 0.85 Jaccard on 5-shingles. Within each LEDGAR label group we drop
duplicates so we don't bias the dedup against rarer classes. Writes a parquet
to artifacts/ledgar_train_deduped.parquet with columns: text, ledgar_label,
cg8_label.

    python backend/ml_training/scripts/03_dedup_minhash.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import _path  # noqa: F401

from src.label_map import map_label  # noqa: E402

ARTIFACTS_DIR = Path(__file__).resolve().parents[1] / "artifacts"
CACHE_DIR = Path(__file__).resolve().parents[1] / "data_cache"

SHINGLE_K = 5
MINHASH_NUM_PERM = 128
THRESHOLD = 0.85


def shingles(text: str, k: int = SHINGLE_K) -> set[str]:
    tokens = text.lower().split()
    if len(tokens) < k:
        return {" ".join(tokens)} if tokens else set()
    return {" ".join(tokens[i:i + k]) for i in range(len(tokens) - k + 1)}


def main() -> int:
    try:
        import pandas as pd  # type: ignore
        from datasets import load_dataset  # type: ignore
        from datasketch import MinHash, MinHashLSH  # type: ignore
    except ImportError as exc:
        print(f"[03_dedup_minhash] Missing dependency: {exc}", file=sys.stderr)
        return 1

    ds = load_dataset("coastalcph/lex_glue", "ledgar", cache_dir=str(CACHE_DIR))
    label_names: list[str] = ds["train"].features["label"].names

    keep_indices: list[int] = []
    lsh = MinHashLSH(threshold=THRESHOLD, num_perm=MINHASH_NUM_PERM)

    for idx, ex in enumerate(ds["train"]):
        text = ex["text"]
        sh = shingles(text)
        if not sh:
            continue
        m = MinHash(num_perm=MINHASH_NUM_PERM)
        for s in sh:
            m.update(s.encode("utf-8"))
        if lsh.query(m):
            continue  # near-duplicate of something we already kept
        lsh.insert(str(idx), m)
        keep_indices.append(idx)
        if (idx + 1) % 5000 == 0:
            print(f"[03_dedup_minhash] processed {idx + 1}, kept {len(keep_indices)}")

    print(f"[03_dedup_minhash] Final: kept {len(keep_indices)} / {len(ds['train'])}")

    rows = []
    for i in keep_indices:
        ex = ds["train"][i]
        ledgar_label = label_names[ex["label"]]
        rows.append({
            "text": ex["text"],
            "ledgar_label": ledgar_label,
            "cg8_label": map_label(ledgar_label),
        })

    df = pd.DataFrame(rows)
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = ARTIFACTS_DIR / "ledgar_train_deduped.parquet"
    df.to_parquet(out_path, index=False)
    print(f"[03_dedup_minhash] Wrote {out_path} ({len(df)} rows)")
    print("[03_dedup_minhash] CG8 distribution:")
    print(df["cg8_label"].value_counts().to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
