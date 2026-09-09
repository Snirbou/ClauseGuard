"""
readability.py — AC-P04 readability scoring for plain-language summaries.

The acceptance criterion reads "Flesch-Kincaid grade level <= 12; pass if the
average grade level <= 12". This module scores the summaries the LLM layer
actually produced for a user, so /api/metrics can report the criterion over
real output rather than over a hand-picked sample.

Pure module: no DB, IO, DSPy, or framework imports, and no third-party
readability package. Flesch-Kincaid only needs word, sentence, and syllable
counts, and a dependency-free implementation keeps the number identical on
the API, in CI, and inside the evaluation scripts.

Syllables come from a vowel-group heuristic with the usual English
adjustments (silent final "e", "-le" endings, "-ed"/"-es" inflections, vowel
hiatus). That is accurate to +-1 on ordinary words — the same accuracy class
as the popular readability libraries — and the per-word errors average out
over a summary of any length, so the grade level is stable even though a
single word may be off.
"""

from __future__ import annotations

import re
import statistics
from collections.abc import Iterable

DEFAULT_TARGET_GRADE = 12.0

# --- Syllables ----------------------------------------------------------------

_VOWELS = "aeiouy"
_VOWEL_GROUP = re.compile(r"[aeiouy]+")

# Adjacent vowels English usually voices as two syllables ("violation",
# "curious", "actual"). After c/s/t/g/l/n/x an "i" glides into one sound
# ("nation", "special", "million", "anxious"), and "ua" after q/g is one sound
# ("quality", "guarantee") — those stay with the plain vowel-group count.
_HIATUS = re.compile(r"(?<=[bdfhjkmprvwz])i[aou]|(?<=[bdfhjklmnprstvwxz])ua")

# A medial "e" before a consonant-initial suffix is silent ("likely",
# "statement", "careful", "useless", "awareness"). "l" is excluded because
# "-lement" words keep the syllable ("settlement", "element", "implement").
_SILENT_MEDIAL_E = re.compile(r"[^aeiouyl]e(?:ly|ful|less|ment|ness)$")


def _has_silent_final_e(word: str) -> bool:
    """Whether the final "e" (also the "e" of an "-ed"/"-es" ending) is unvoiced."""
    if len(word) < 3:
        return False
    if word.endswith("ed"):
        if word[-3] in "dt":  # want-ed, need-ed
            return False
        stem = word[:-1]
    elif word.endswith("es"):
        if word[-3] in "sxzcgh":  # claus-es, tax-es, servic-es, charg-es, wish-es
            return False
        stem = word[:-1]
    elif word.endswith("e"):
        stem = word
    else:
        return False
    if stem.endswith(("gue", "que")):  # league, unique
        return True
    if stem[-2] in _VOWELS:  # agree, movie, value, parties — the "e" is voiced
        return False
    # "-le" after a consonant is its own syllable (table, titled, articles);
    # after "l" it is not (called, cancelled).
    if stem.endswith("le") and len(stem) >= 3 and stem[-3] not in _VOWELS + "l":
        return False
    return True


def count_syllables(word: str) -> int:
    """Estimate the syllables in one word; never below 1 for a spoken token."""
    letters = "".join(ch for ch in word.lower() if "a" <= ch <= "z")
    if not letters:
        # A number or symbol token ("12,000", "$500") is still read aloud as at
        # least one syllable; an empty or punctuation-only token is not spoken.
        return 1 if any(ch.isalnum() for ch in word) else 0
    count = len(_VOWEL_GROUP.findall(letters)) + len(_HIATUS.findall(letters))
    if count > 1 and (_has_silent_final_e(letters) or _SILENT_MEDIAL_E.search(letters)):
        count -= 1
    return max(count, 1)


# --- Words and sentences -------------------------------------------------------

# A word is a run of letters/digits, optionally joined by an apostrophe,
# hyphen, or an internal period/comma ("Client's", "long-term", "e.g.",
# "12,000"). Trailing punctuation is never part of the word.
_WORD = re.compile(r"[^\W_]+(?:['’.,\-][^\W_]+)*")

_PARAGRAPH_BREAK = re.compile(r"\n[ \t]*\n+")
_BULLET_LINE = re.compile(r"^\s*(?:[-*•‣▪–—]|\(?\d{1,3}[.)]|\(?[A-Za-z][.)])\s+")

# A sentence ends at terminal punctuation (optionally followed by closing
# quotes/brackets) when the next token starts with a capital, a digit, or an
# opening quote/bracket. Requiring that start is what keeps "e.g. the fee" and
# "12.5 percent" intact without a dictionary.
_TERMINATOR = re.compile(r"""[.!?]+["'”’)\]]*(?=\s+["'“‘(\[]?[A-Z0-9])""")
_LAST_TOKEN = re.compile(r"(\S+)$")
_LETTER_DOT_ABBREVIATION = re.compile(r"(?:[a-z]\.)+[a-z]?")  # e.g, i.e, u.s, a.m

# Abbreviations that are routinely followed by a capital or a digit mid-sentence
# ("Sec. 4", "Dr. Smith", "Smith vs. Jones"). "etc." and company suffixes are
# left out on purpose: when a capital follows them it usually is a new sentence.
_ABBREVIATIONS = frozenset({
    "vs", "cf", "viz", "mr", "mrs", "ms", "dr", "prof", "jr", "sr", "st",
    "no", "nos", "sec", "sect", "art", "para", "ch", "cl", "fig", "vol", "pp", "p", "approx",
})


def _ends_with_abbreviation(before_punctuation: str) -> bool:
    match = _LAST_TOKEN.search(before_punctuation)
    if match is None:
        return False
    token = match.group(1).lower().strip("\"'“‘”’()[]")
    return token in _ABBREVIATIONS or _LETTER_DOT_ABBREVIATION.fullmatch(token) is not None


def _line_units(text: str) -> list[str]:
    """Group lines into candidate sentences before punctuation splitting.

    A blank line always separates sentences and a bullet/enumerated line always
    starts one; any other line break is treated as a hard wrap and joined with
    a space, so PDF-wrapped text does not inflate the sentence count.
    """
    units: list[str] = []
    for paragraph in _PARAGRAPH_BREAK.split(text):
        lines = paragraph.split("\n")
        chunk = lines[0]
        for line in lines[1:]:
            if _BULLET_LINE.match(line):
                units.append(chunk)
                chunk = line
            else:
                chunk = f"{chunk} {line}"
        units.append(chunk)
    return units


def split_sentences(text: str) -> list[str]:
    """Split text into sentences; only chunks containing a word are returned."""
    sentences: list[str] = []
    for unit in _line_units((text or "").replace("…", "...")):
        start = 0
        for match in _TERMINATOR.finditer(unit):
            if _ends_with_abbreviation(unit[start:match.start()]):
                continue
            sentences.append(unit[start:match.end()])
            start = match.end()
        sentences.append(unit[start:])
    return [s.strip() for s in sentences if _WORD.search(s)]


def count_words(text: str) -> int:
    return len(_WORD.findall(text or ""))


# --- Flesch-Kincaid -------------------------------------------------------------

def flesch_kincaid_grade(text: str) -> float | None:
    """US school grade level of the text, clamped at 0; None when there are no words."""
    words = _WORD.findall(text or "")
    if not words:
        return None
    sentences = max(1, len(split_sentences(text)))
    syllables = sum(count_syllables(w) for w in words)
    grade = 0.39 * (len(words) / sentences) + 11.8 * (syllables / len(words)) - 15.59
    return round(max(0.0, grade), 2)


def readability_summary(
    texts: Iterable[str | None],
    target_grade: float = DEFAULT_TARGET_GRADE,
) -> dict[str, float | int | bool | None]:
    """Aggregate AC-P04 over a sample of summaries; empty/None texts are skipped.

    ``meets_target`` is the acceptance rule itself (average grade <= target) so
    the dashboard does not re-derive it; ``share_at_or_below_target`` shows how
    evenly the sample sits under the bar rather than only its mean.
    """
    grades = [g for g in (flesch_kincaid_grade(t) for t in texts if t) if g is not None]
    if not grades:
        return {
            "sample_size": 0,
            "avg_grade": None,
            "median_grade": None,
            "share_at_or_below_target": None,
            "meets_target": None,
            "target_grade": float(target_grade),
        }
    avg_grade = round(statistics.fmean(grades), 2)
    return {
        "sample_size": len(grades),
        "avg_grade": avg_grade,
        "median_grade": round(statistics.median(grades), 2),
        "share_at_or_below_target": round(
            sum(1 for g in grades if g <= target_grade) / len(grades), 3
        ),
        "meets_target": avg_grade <= target_grade,
        "target_grade": float(target_grade),
    }
