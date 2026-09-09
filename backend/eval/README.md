# Real-contract evaluation corpus

Everything in `backend/eval/` exists to answer one question honestly: **does
ClauseGuard work on real contracts, not just on the PDFs our tests build?**

The unit tests in `backend/tests/` construct documents whose structure we
chose, so they prove the code paths fire — not that they fire on what a
freelancer actually uploads. This harness measures the second thing against
the owner's own contracts.

---

## Privacy rule (read this first)

**`backend/eval/corpus/` never enters git.** It holds real signed contracts —
counterparties' names, rates, terms. It is listed in the repository
`.gitignore` and must stay there.

- Committed: **metrics only** — `backend/eval/results/*.json` (counts, scores,
  file slugs) and the model sidecars under `backend/models/`.
- Never committed: PDFs, extracted text, clause text, anchors, LLM responses
  (`results/l2_cache.jsonl` is ignored for the same reason).
- Before committing a result file, skim it. If you can read a sentence of a
  contract in it, that is a bug — say so instead of committing it.

A fresh clone therefore has no corpus. Every script and test here treats that
as normal: they print "nothing to evaluate" and exit `0`, or `pytest.skip`.

---

## Adding a contract

1. Anonymise it if you want to: replace names and figures in the PDF itself.
   The harness reads whatever text layer is there.
2. Drop it in `backend/eval/corpus/` with a short slug filename:
   `corpus/saas-retainer-2024.pdf`. The slug appears in committed metrics, so
   do not name it after the client.
3. Scanned PDFs (no text layer) are out of scope until OCR lands in Phase 5.
   `annotate.py` refuses them with that message rather than writing an empty
   gold file.

Aim for ~10 contracts spanning the shapes that break segmentation: numbered
sections, unnumbered bold headings, two-column layouts, one-paragraph
letters.

---

## Annotating

One file per contract — `corpus/<slug>.pdf` gets `corpus/<slug>.gold.json` —
and **one format for both evaluations**: `segmentation_eval.py` reads the
anchors, `risk_eval.py` reads `high_risk`. Annotate a contract once.

Start from a draft rather than a blank file:

```powershell
# from backend/
venv\Scripts\python.exe eval\annotate.py corpus\saas-retainer-2024.pdf
venv\Scripts\python.exe eval\annotate.py --all --force   # every PDF, overwriting
```

That writes one entry per clause the **current** segmenter found, with the
anchors quoted and the Layer 1 prediction filled in. It never overwrites an
existing gold file without `--force`: a day of annotation is not recoverable
from git, because the corpus is gitignored. Add `--no-classify` to skip
loading the classifier (leaves `clause_type` null).

**A draft is not ground truth.** It agrees with the segmenter by construction,
so evaluating an unedited draft scores 1.0 and means nothing. Your edits are
the benchmark:

```jsonc
{
  "file": "saas-retainer-2024.pdf",
  "annotator": "snir",
  "annotated_at": "2026-09-09",
  "notes": "two-column layout, signature page ignored",
  "clauses": [
    {
      "id": 1,
      "anchor_start": "5. PAYMENT. The Client shall pay each", // first ~40 chars
      "anchor_end": "within sixty (60) days.",                 // last ~30 chars
      "clause_type": "payment_terms",
      "high_risk": true,
      "risk_note": "net-60 with no late fee"
    }
  ],
  "missing_protections": ["liability_gaps"]
}
```

What to fix, in order of value:

1. **Boundaries.** Merge clauses the segmenter split, split ones it ran
   together, delete entries that are page furniture. Keep the clauses in
   document order — anchors are resolved with a cursor that only moves
   forward, because "The Contractor shall" is not unique in any contract.
2. **`clause_type`.** One of `payment_terms`, `termination`, `ip_assignment`,
   `liability`, `confidentiality`, `scope_of_work`, `governing_law`,
   `general` — or `null` for "not annotated", which is skipped rather than
   scored. Unknown values are rejected loudly.
3. **`high_risk`.** The one judgement no model can make for you: **`true`
   when the clause, as written, is a term a freelancer would likely lose
   money or rights on** — unpaid revisions, net-90 with no late fee, IP
   assigned before payment clears, uncapped indemnity, termination for
   convenience with no kill fee. `false` for ordinary terms, `null` for
   "haven't decided". `risk_note` is free text for your reasoning; it is
   never published.
4. **`missing_protections`.** Contract-level gaps, from the five pain points
   in `pain_points.py`: `payment_traps`, `scope_creep`, `ip_assignment`,
   `termination_asymmetry`, `liability_gaps`.

Anchors are literal quotes with whitespace ignored, so a line break in the
PDF does not matter — but a paraphrase will not resolve. If an anchor cannot
be found the tools say so and name the clause; they never skip it silently,
because a skipped clause quietly shrinks the benchmark and flatters the
score.

---

## Running the evaluation

```powershell
# from backend/
venv\Scripts\python.exe eval\segmentation_eval.py
venv\Scripts\python.exe eval\segmentation_eval.py --baseline   # the merge gate
```

Output: one row per contract plus a micro-average, and
`eval/results/segmentation_eval.json` (metrics, slugs, tolerance, timestamp —
no text).

| Column | Meaning |
|---|---|
| `gold` / `pred` | annotated vs predicted clause count |
| `hit` | boundaries matched one-to-one within the tolerance |
| `P` / `R` / `F1` | boundary precision, recall, F1 (AC-S01) |
| `cover` | non-whitespace characters preserved (AC-S03, floor 0.95) |
| `L1 acc` | `classifier.classify` accuracy on the gold spans |

A predicted clause start matches a gold start when the two are within
`--tolerance` characters (default 20) of the normalised text —
`segmentation._merge_tiny_fragments` folds page furniture forward and shifts a
start by a few characters without getting the clause wrong. Matching is
one-to-one and nearest-first, so one gold clause split into three costs
precision once per spurious boundary, and a single early miss does not
misalign everything after it.

### The merge gate

`--baseline` compares this run's micro-F1 with the value in the committed
`eval/results/segmentation_eval.json` and **exits `2` if it dropped by more
than 0.02** (`--max-drop`). On a regression the file is *not* rewritten —
otherwise the next run would compare against the worse number and pass. It is
also not written when any gold problem is reported, so the committed metrics
always describe a clean run over the whole annotated corpus.

Exit codes: `0` fine (including "no corpus on this machine"), `2` regression,
`3` a gold file could not be read or an anchor did not resolve. `3` means the
benchmark is broken, not the segmenter.

Other flags: `--corpus DIR`, `--tolerance N`, `--json-out PATH`,
`--no-classify` (skips Layer 1 accuracy and never loads spaCy).

Run the gate after any change to `segmentation.py`, `pdf_extract.py` or the
classifier artifact. It needs no API key.

---

## Risk detection (AC-R05)

`risk_eval.py` answers the other half of the acceptance criteria: **how often
is a clause we call high-risk actually high-risk, and how many do we miss?**
Targets are precision ≥ 0.75 and recall ≥ 0.70 on high-risk detection.

```powershell
# from backend/
venv\Scripts\python.exe eval\risk_eval.py --provider fake              # plumbing check only
venv\Scripts\python.exe eval\risk_eval.py --provider openai --cuad 50  # the real measurement
```

It reads `high_risk` from the same gold files, runs each clause through the
**production path** (`classifier.classify` → `dspy_pipeline.process_clauses`
→ `analysis_service.finalize_clause_result`), and reports precision, recall,
F1, a confusion matrix, a per-source breakdown and a threshold sweep over
`scoring.THRESHOLD_HIGH`, so you can see what a different cut-off would buy.

`--cuad N` adds a proxy set from CUAD, mapping its categories to "high risk
for the person signing" (uncapped liability, non-compete, IP assignment,
termination for convenience, …). It is a **proxy**: commercial contracts,
category-level labels, and the signer is not always the freelancer. The
caveat travels with the numbers into the sidecar and onto the dashboard.

**The provider gate matters.** With `--provider fake` the offline analyzer
scores clauses from a hash of their text, so its precision and recall mean
nothing about quality. That run writes only
`results/risk_eval.provisional.json` and **refuses** to write the committed
`models/risk_eval.json`; until a real run happens, `/api/metrics` reports
`measured: false` and the dashboard says "not yet measured". This is
deliberate — an unmeasured criterion must look unmeasured.

Layer 2 responses are cached in `results/l2_cache.jsonl` (gitignored: it
holds LLM output about real contracts) keyed by text plus provider/model, so
re-runs and the sweep cost nothing. Deleting it only costs another LLM pass.

---

## Layout

```
eval/
  __init__.py            shared: normalise, resolve_anchor, the gold format
  annotate.py            draft a gold file from the current segmentation
  segmentation_eval.py   boundary P/R/F1, coverage, Layer 1 accuracy, the gate
  risk_eval.py           AC-R05, reads high_risk from the same gold files
  corpus/                real contracts + gold files — GITIGNORED
  results/               committed metrics only
```

`eval/__init__.py` is deliberately cheap to import (stdlib plus
`pain_points`): loading PyMuPDF or the classifier is each script's own
decision. Both CLIs are guarded by `if __name__ == "__main__"`, so their
functions stay importable — `backend/tests/test_segmentation_corpus.py`
exercises them without a corpus.
