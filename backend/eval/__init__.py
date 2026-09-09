"""Real-contract evaluation harness — the pieces every evaluator shares.

Every quality claim that matters is a claim about *real* contracts. The unit
tests build synthetic PDFs whose structure we chose, so they prove the
strategies fire, not that they fire on the documents a freelancer actually
uploads. This package measures the second thing against the owner's own
contracts, which cannot enter git: the corpus lives in an ignored folder and
only metrics are committed (see ``eval/README.md``).

One annotation format serves both evaluations. ``segmentation_eval.py`` reads
the anchors (AC-S01..S03) and ``risk_eval.py`` reads ``high_risk`` (AC-R05)
from the *same* ``<slug>.gold.json``, so a contract is annotated once.

Anchors, not offsets, identify a clause: byte offsets would rot the moment
``pdf_extract`` changed a space, whereas a literal quote from the clause
survives. They are resolved against the whitespace-normalised text of
``pdf_extract.extract_document_text`` — the shared extraction seam — with a
cursor that walks the document in order, because "The Contractor shall" is
not unique in any contract. An anchor that will not resolve is an error, never
a skipped clause: silently dropping it would quietly shrink the gold set and
flatter the metrics.

Import stays cheap (stdlib plus ``pain_points``); pulling in PyMuPDF or the
classifier is the caller's decision.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pain_points import required_type_by_pain_point

BACKEND_DIR = Path(__file__).resolve().parents[1]
EVAL_DIR = BACKEND_DIR / "eval"
#: The owner's real contracts and their gold files. Gitignored, often absent.
CORPUS_DIR = EVAL_DIR / "corpus"
#: Committed metrics. Never contract text.
RESULTS_DIR = EVAL_DIR / "results"

#: The Layer 1 label set (``models/clause_classifier_v1.joblib``). ``null`` in
#: a gold file means "not annotated" and is skipped by the Layer 1 scoring.
CLAUSE_TYPES: tuple[str, ...] = (
    "payment_terms",
    "termination",
    "ip_assignment",
    "liability",
    "confidentiality",
    "scope_of_work",
    "governing_law",
    "general",
)

#: Contract-level protections whose absence ``pain_points`` reports. Kept in
#: sync by reading that module rather than by copying its keys here.
PAIN_POINTS: tuple[str, ...] = tuple(required_type_by_pain_point())

#: Values an annotator may write for "no label" (JSON null is the canonical
#: one; the strings are typos we would rather accept than reject).
_NULL_STRINGS = frozenset({"", "null", "none", "n/a", "-"})


class GoldFormatError(ValueError):
    """A gold file is malformed. The message names the file and the field."""


class AnchorError(LookupError):
    """An anchor could not be resolved against the extracted text."""


# ---------------------------------------------------------------------------
# Text normalisation and anchor resolution
# ---------------------------------------------------------------------------

def normalise(text: str) -> str:
    """Collapse every whitespace run to a single space and strip the ends.

    Anchors are quoted by a human from a PDF viewer, and PDF extraction
    breaks lines wherever the layout did. Normalising both sides makes the
    quote match the text regardless of where the line broke.
    """
    return " ".join(text.split())


def resolve_anchor(normalised_text: str, anchor: str, start_at: int = 0) -> int:
    """Offset of ``anchor`` in ``normalised_text`` at or after ``start_at``.

    Clauses are annotated in document order, so each search starts where the
    previous clause ended; that is what makes repeated phrases unambiguous.
    Raises ``AnchorError`` — loudly, with the reason — when the anchor is
    absent, and says so explicitly when the anchor exists *earlier* in the
    document, which almost always means the gold clauses are out of order.
    """
    needle = normalise(anchor)
    if not needle:
        raise AnchorError("empty anchor: every clause needs an anchor_start")

    index = normalised_text.find(needle, max(0, start_at))
    if index >= 0:
        return index

    earlier = normalised_text.find(needle)
    quoted = needle[:60]
    if earlier >= 0:
        raise AnchorError(
            f"anchor {quoted!r} occurs at offset {earlier}, before the previous "
            f"clause ended (offset {start_at}) — are the clauses in document order?"
        )
    raise AnchorError(
        f"anchor {quoted!r} does not occur in the extracted text — re-copy it "
        "from the PDF (it must be a literal quote, whitespace ignored)"
    )


def locate_segments(normalised_text: str, segments: list[str]) -> list[int]:
    """Start offsets of ``segments`` in ``normalised_text``, in order.

    The segmentation strategies partition their input, so every segment is a
    substring of the normalised document; walking a cursor forward keeps
    repeated boilerplate on the right occurrence. Raises ``AnchorError`` if a
    segment cannot be located — that would mean segmentation stopped
    preserving text, which the metrics must not paper over.
    """
    offsets: list[int] = []
    cursor = 0
    for position, segment in enumerate(segments):
        needle = normalise(segment)
        if not needle:
            continue
        index = normalised_text.find(needle, cursor)
        if index < 0:
            raise AnchorError(
                f"predicted segment {position} is not a substring of the "
                f"normalised document: {needle[:60]!r}"
            )
        offsets.append(index)
        cursor = index + len(needle)
    return offsets


# ---------------------------------------------------------------------------
# The gold annotation format
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GoldClause:
    """One annotated clause. ``clause_type``/``high_risk`` may be unlabelled."""

    id: int
    anchor_start: str
    anchor_end: str
    clause_type: str | None = None
    high_risk: bool | None = None
    risk_note: str = ""


@dataclass(frozen=True)
class GoldFile:
    """A parsed ``<slug>.gold.json`` plus where it came from."""

    path: Path
    file: str
    clauses: list[GoldClause]
    missing_protections: list[str] = field(default_factory=list)
    annotator: str = ""
    annotated_at: str = ""
    notes: str = ""

    @property
    def slug(self) -> str:
        """``payments-2024.gold.json`` -> ``payments-2024``."""
        return self.path.name.removesuffix(".gold.json")

    @property
    def pdf_path(self) -> Path:
        """The contract this gold file annotates, next to the gold file."""
        return self.path.parent / (self.file or f"{self.slug}.pdf")

    @property
    def has_clause_types(self) -> bool:
        return any(clause.clause_type for clause in self.clauses)

    @property
    def has_risk_labels(self) -> bool:
        return any(clause.high_risk is not None for clause in self.clauses)


@dataclass(frozen=True)
class ResolvedClause:
    """A gold clause bound to its span in the normalised document text."""

    clause: GoldClause
    start: int
    end: int
    text: str

    @property
    def clause_type(self) -> str | None:
        return self.clause.clause_type

    @property
    def high_risk(self) -> bool | None:
        return self.clause.high_risk


def gold_path_for(pdf_path: Path) -> Path:
    """``corpus/foo.pdf`` -> ``corpus/foo.gold.json``."""
    return pdf_path.parent / f"{pdf_path.stem}.gold.json"


def iter_gold_files(corpus_dir: Path = CORPUS_DIR) -> list[Path]:
    """Every gold file in the corpus, sorted. Empty when the corpus is absent."""
    if not corpus_dir.is_dir():
        return []
    return sorted(corpus_dir.glob("*.gold.json"))


def _as_optional_label(raw: Any, where: str) -> str | None:
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise GoldFormatError(f"{where}: clause_type must be a string or null, got {raw!r}")
    value = raw.strip().lower()
    if value in _NULL_STRINGS:
        return None
    if value not in CLAUSE_TYPES:
        raise GoldFormatError(
            f"{where}: unknown clause_type {raw!r} — expected one of "
            f"{', '.join(CLAUSE_TYPES)} or null"
        )
    return value


def _as_optional_bool(raw: Any, where: str) -> bool | None:
    if raw is None:
        return None
    if isinstance(raw, bool):
        return raw
    raise GoldFormatError(
        f"{where}: high_risk must be true, false or null (JSON literals, not "
        f"strings), got {raw!r}"
    )


def parse_gold(payload: Any, path: Path) -> GoldFile:
    """Validate a decoded gold document. Separate from IO so tests can call it."""
    where = path.name
    if not isinstance(payload, dict):
        raise GoldFormatError(f"{where}: the top level must be a JSON object")

    raw_clauses = payload.get("clauses")
    if not isinstance(raw_clauses, list) or not raw_clauses:
        raise GoldFormatError(f"{where}: 'clauses' must be a non-empty list")

    clauses: list[GoldClause] = []
    for position, raw in enumerate(raw_clauses):
        label = f"{where} clause #{position + 1}"
        if not isinstance(raw, dict):
            raise GoldFormatError(f"{label}: each clause must be a JSON object")
        anchor_start = str(raw.get("anchor_start", "")).strip()
        if not anchor_start:
            raise GoldFormatError(f"{label}: anchor_start is required")
        clauses.append(
            GoldClause(
                id=int(raw.get("id", position + 1)),
                anchor_start=anchor_start,
                anchor_end=str(raw.get("anchor_end", "") or ""),
                clause_type=_as_optional_label(raw.get("clause_type"), label),
                high_risk=_as_optional_bool(raw.get("high_risk"), label),
                risk_note=str(raw.get("risk_note", "") or ""),
            )
        )

    raw_missing = payload.get("missing_protections") or []
    if not isinstance(raw_missing, list):
        raise GoldFormatError(f"{where}: 'missing_protections' must be a list")
    missing: list[str] = []
    for item in raw_missing:
        value = str(item).strip().lower()
        if value not in PAIN_POINTS:
            raise GoldFormatError(
                f"{where}: unknown missing_protections entry {item!r} — expected "
                f"one of {', '.join(PAIN_POINTS)}"
            )
        missing.append(value)

    return GoldFile(
        path=path,
        file=str(payload.get("file", "") or ""),
        clauses=clauses,
        missing_protections=missing,
        annotator=str(payload.get("annotator", "") or ""),
        annotated_at=str(payload.get("annotated_at", "") or ""),
        notes=str(payload.get("notes", "") or ""),
    )


def load_gold(path: Path) -> GoldFile:
    """Read and validate one ``<slug>.gold.json``."""
    try:
        # utf-8-sig, not utf-8: Notepad and PowerShell 5.1's `Set-Content
        # -Encoding utf8` both prepend a BOM, and a gold file that took an
        # hour to write must not be rejected over three invisible bytes.
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except OSError as exc:
        raise GoldFormatError(f"{path.name}: cannot be read ({exc})") from exc
    except ValueError as exc:
        raise GoldFormatError(f"{path.name}: is not valid JSON ({exc})") from exc
    return parse_gold(payload, path)


def resolve_gold(
    normalised_text: str, gold: GoldFile
) -> tuple[list[ResolvedClause], list[str]]:
    """Bind every gold clause to its span in the normalised document text.

    Returns the clauses that resolved and a list of human-readable problems.
    Callers must report the problems: an unresolved anchor means the gold file
    and the extracted text disagree, and metrics computed over the remainder
    are measuring a smaller benchmark than the annotator wrote.

    A clause whose ``anchor_end`` is blank (or does not resolve) ends where the
    next clause begins, so a half-finished annotation still yields usable
    spans instead of one clause swallowing the rest of the contract.
    """
    problems: list[str] = []
    # (clause, start, end) with ``None`` for "ends where the next clause begins".
    staged: list[tuple[GoldClause, int, int | None]] = []
    cursor = 0

    for clause in gold.clauses:
        label = f"{gold.path.name} clause #{clause.id}"
        try:
            start = resolve_anchor(normalised_text, clause.anchor_start, cursor)
        except AnchorError as exc:
            problems.append(f"{label}: {exc}")
            continue

        end: int | None = None
        cursor = max(cursor, start + len(normalise(clause.anchor_start)))
        tail = normalise(clause.anchor_end)
        if tail:
            try:
                # Searched from the clause's own start so that a short clause,
                # whose head and tail anchors overlap, still resolves.
                end = resolve_anchor(normalised_text, tail, start) + len(tail)
                cursor = end
            except AnchorError as exc:
                problems.append(f"{label}: anchor_end unresolved — {exc}")

        staged.append((clause, start, end))

    resolved: list[ResolvedClause] = []
    for position, (clause, start, end) in enumerate(staged):
        if end is None:
            # A blank (or unresolvable) anchor_end means "runs to the next
            # clause" — what a human expects, and what stops one missing tail
            # from swallowing the rest of the contract into a single span.
            following = (
                staged[position + 1][1]
                if position + 1 < len(staged)
                else len(normalised_text)
            )
            end = max(start, following)
        resolved.append(
            ResolvedClause(
                clause=clause,
                start=start,
                end=end,
                text=normalised_text[start:end],
            )
        )

    return resolved, problems


def load_contract(pdf_path: Path) -> tuple[Any, str]:
    """Extract a corpus PDF exactly as the upload endpoint does.

    Returns ``(ExtractedDocument, normalised_full_text)``. PyMuPDF is imported
    here rather than at module scope so that importing this package stays
    cheap for callers that only need the gold format.
    """
    from pdf_extract import extract_document_text

    extracted = extract_document_text(pdf_path.read_bytes())
    return extracted, normalise(extracted.full_text)
