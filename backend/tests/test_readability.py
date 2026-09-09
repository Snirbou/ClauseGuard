"""Unit tests for backend.readability — AC-P04 Flesch-Kincaid scoring.

AC-P04 ("average Flesch-Kincaid grade level <= 12") is reported straight to the
dashboard, so the number has to be defensible without a third-party library
vouching for it. These tests pin the properties the criterion actually rests on:
the syllable heuristic stays within its documented +-1 accuracy on the legal
vocabulary the summaries are full of, sentence splitting is not fooled by the
abbreviations and hard-wrapped lines that PDF text is full of, plain language
lands far under the bar while legalese lands far above it, and the aggregate
dict is internally consistent with the individual grades it summarizes.

Every assertion is a range or a relation. Exact floats would freeze the
heuristic instead of the criterion, and turn any future tuning of the
syllable rules into a spurious failure.
"""

from __future__ import annotations

import pytest

from readability import (
    DEFAULT_TARGET_GRADE,
    count_syllables,
    count_words,
    flesch_kincaid_grade,
    readability_summary,
    split_sentences,
)

# A plain-language summary of the kind Layer 2 is prompted to produce.
PLAIN = "You get paid within 30 days."
PLAIN_2 = "We pay you fast. You do the work."
PLAIN_3 = "The client must give notice before they end the deal."

# One sentence of genuine contract boilerplate — long, and dense with
# polysyllabic Latinate words. This is what AC-P04 exists to keep out.
LEGALESE = (
    "Notwithstanding any provision to the contrary contained herein, the "
    "indemnifying party shall indemnify, defend, and hold harmless the "
    "indemnified party from and against any and all liabilities, obligations, "
    "damages, penalties, claims, costs, charges, and expenses, including "
    "reasonable attorneys' fees, arising out of or attributable to the "
    "performance or nonperformance of the aforementioned contractual "
    "obligations under this agreement."
)


# --- Syllables ------------------------------------------------------------

# The reference counts are the dictionary pronunciations. The module documents
# +-1 accuracy on ordinary words, so that is the tolerance the tests enforce:
# tighter would pin the heuristic, looser would not catch a real regression.
SYLLABLE_TABLE = [
    ("the", 1),
    ("clause", 1),
    ("agreement", 3),
    ("indemnification", 6),
    ("liability", 5),
    ("payment", 2),
    ("terminate", 3),
    ("contractor", 3),
    ("quality", 3),
    ("nation", 2),
]


@pytest.mark.parametrize("word,expected", SYLLABLE_TABLE)
def test_count_syllables_within_one_of_the_dictionary(word: str, expected: int) -> None:
    assert abs(count_syllables(word) - expected) <= 1


@pytest.mark.parametrize("word,_expected", SYLLABLE_TABLE)
def test_every_spoken_word_has_at_least_one_syllable(word: str, _expected: int) -> None:
    # A zero here would silently deflate the grade of any text containing the
    # word, so the floor matters independently of the estimate's accuracy.
    assert count_syllables(word) >= 1


@pytest.mark.parametrize("token", ["12,000", "$500", "30", "60-day"])
def test_numeric_tokens_are_spoken(token: str) -> None:
    assert count_syllables(token) >= 1


@pytest.mark.parametrize("token", ["", "   ", "!!!", "...", "--"])
def test_unspoken_tokens_have_no_syllables(token: str) -> None:
    assert count_syllables(token) == 0


def test_longer_words_are_not_counted_as_shorter_ones() -> None:
    # The grade level only separates plain from dense text if the estimate
    # actually ranks words by length, whatever its per-word error.
    assert count_syllables("indemnification") > count_syllables("payment")
    assert count_syllables("payment") > count_syllables("the")


# --- Sentence splitting ---------------------------------------------------

def test_abbreviations_do_not_end_a_sentence() -> None:
    text = "The fee is due on time, e.g. within 30 days. See No. 5 for the schedule."
    sentences = split_sentences(text)
    assert len(sentences) == 2
    assert "e.g. within 30 days" in sentences[0]
    assert "No. 5" in sentences[1]


def test_decimal_numbers_do_not_end_a_sentence() -> None:
    sentences = split_sentences("The rate is 12.5 percent of the total. It is fixed.")
    assert len(sentences) == 2
    assert "12.5 percent" in sentences[0]


def test_company_suffix_before_a_capital_starts_a_new_sentence() -> None:
    # Documented deliberate choice: "Inc." is not in the abbreviation list,
    # because a capital after it is far more often a new sentence than not.
    lower = split_sentences("The work is done by Acme Inc. and its affiliates are bound.")
    assert len(lower) == 1
    upper = split_sentences("The work is done by Acme Inc. The Client shall pay the fee.")
    assert len(upper) == 2


@pytest.mark.parametrize("ellipsis", ["…", "..."])
def test_ellipsis_is_one_boundary_not_three(ellipsis: str) -> None:
    text = f"The Client may terminate{ellipsis} Notice is still required. The fee is due."
    assert len(split_sentences(text)) == 3


def test_hard_wrapped_lines_are_joined_but_blank_lines_split() -> None:
    wrapped = "The Contractor shall provide\nweb development services to the Client."
    assert len(split_sentences(wrapped)) == 1

    paragraphs = "First paragraph sentence\n\nSecond paragraph sentence"
    assert len(split_sentences(paragraphs)) == 2


def test_trailing_fragment_is_kept_as_a_sentence() -> None:
    # Dropping it would shrink the denominator and understate the grade of any
    # summary the model ended without punctuation.
    sentences = split_sentences("The fee is due. The term is one year. And a trailing fragment")
    assert len(sentences) == 3
    assert sentences[-1] == "And a trailing fragment"


def test_mixed_real_world_text() -> None:
    text = (
        "The Client shall pay the fee, e.g. within 30 days… "
        "See No. 5 of Schedule A.\n"
        "Acme Inc. and its affiliates are bound.\n\n"
        "A trailing fragment with no period"
    )
    sentences = split_sentences(text)
    assert len(sentences) == 4
    assert all(sentence == sentence.strip() for sentence in sentences)
    assert all(sentence for sentence in sentences)


@pytest.mark.parametrize("text", ["", "   ", "\n\n\t ", "... !!! ---"])
def test_wordless_text_yields_no_sentences(text: str) -> None:
    assert split_sentences(text) == []


# --- Word counting --------------------------------------------------------

def test_punctuation_is_not_a_word() -> None:
    assert count_words("Hello, world! Yes -- really?") == 4
    assert count_words("... !!! -- ;") == 0


def test_compound_and_numeric_tokens_count_once() -> None:
    # "long-term" and "12,000" are each read as a single word; splitting them
    # would inflate the word count and deflate the grade.
    assert count_words("long-term") == 1
    assert count_words("12,000") == 1
    assert count_words("e.g.") == 1
    assert count_words("Client's") == 1
    assert count_words("The fee (USD 12,000) is due; net-60.") == 7


def test_count_words_matches_the_plain_sample() -> None:
    assert count_words(PLAIN) == 6


@pytest.mark.parametrize("text", ["", "   ", "\n"])
def test_count_words_on_empty_text(text: str) -> None:
    assert count_words(text) == 0


# --- Flesch-Kincaid grade -------------------------------------------------

def test_plain_language_scores_well_under_the_target() -> None:
    grade = flesch_kincaid_grade(PLAIN)
    assert grade is not None
    assert grade < 8.0


def test_legalese_scores_above_the_target() -> None:
    grade = flesch_kincaid_grade(LEGALESE)
    assert grade is not None
    assert grade > 12.0


def test_legalese_scores_higher_than_plain_language() -> None:
    # The ordering is the whole point of the metric; the absolute values are
    # only as good as the heuristic behind them.
    plain = flesch_kincaid_grade(PLAIN)
    dense = flesch_kincaid_grade(LEGALESE)
    assert plain is not None and dense is not None
    assert dense > plain


@pytest.mark.parametrize("text", ["", "   ", "\n\t ", "... !!!", "--- ;"])
def test_no_words_means_no_grade(text: str) -> None:
    # None, not 0.0: a summary that was never produced must not be scored as a
    # perfectly readable one and drag the sample average down.
    assert flesch_kincaid_grade(text) is None


@pytest.mark.parametrize("text", [
    "Go.",
    "We pay you fast. You do the work.",
    " ".join(["We pay you fast."] * 10),
    "Pay",
])
def test_grade_is_never_negative(text: str) -> None:
    grade = flesch_kincaid_grade(text)
    assert grade is not None
    assert grade >= 0.0


def test_grade_is_clamped_rather_than_going_negative() -> None:
    # Very short monosyllabic sentences drive the raw formula below zero; the
    # clamp keeps "grade level" meaningful (there is no grade -3).
    assert flesch_kincaid_grade("We pay you fast. You do the work.") == 0.0


def test_missing_terminal_punctuation_does_not_explode_the_grade() -> None:
    # LLM summaries sometimes stop without a period; the split still yields one
    # sentence, so the score must stay close to the punctuated version.
    with_period = flesch_kincaid_grade(PLAIN)
    without = flesch_kincaid_grade(PLAIN.rstrip("."))
    assert with_period is not None and without is not None
    assert abs(with_period - without) < 0.5


# --- readability_summary --------------------------------------------------

MIXED_SAMPLE = [PLAIN, PLAIN_2, PLAIN_3, LEGALESE]


def _grades(texts: list[str]) -> list[float]:
    graded = [flesch_kincaid_grade(t) for t in texts]
    assert all(g is not None for g in graded)
    return [g for g in graded if g is not None]


def test_summary_is_consistent_with_the_individual_grades() -> None:
    grades = _grades(MIXED_SAMPLE)
    summary = readability_summary(MIXED_SAMPLE)
    target = summary["target_grade"]
    assert isinstance(target, float)

    assert summary["sample_size"] == len(grades)
    assert summary["avg_grade"] == pytest.approx(sum(grades) / len(grades), abs=0.01)
    assert min(grades) <= summary["avg_grade"] <= max(grades)
    assert min(grades) <= summary["median_grade"] <= max(grades)
    assert summary["share_at_or_below_target"] == pytest.approx(
        sum(1 for g in grades if g <= target) / len(grades), abs=0.001
    )
    assert summary["meets_target"] is (summary["avg_grade"] <= target)


def test_median_of_an_odd_sample_is_the_middle_grade() -> None:
    sample = [PLAIN, PLAIN_3, LEGALESE]
    middle = sorted(_grades(sample))[1]
    assert readability_summary(sample)["median_grade"] == pytest.approx(middle, abs=0.01)


def test_blank_and_missing_texts_are_skipped_not_scored() -> None:
    # A clause whose summary failed or was never generated must not count as a
    # sample point at all — in either direction.
    padded = [PLAIN, None, "", "   ", PLAIN_2, "\n\t", "!!!", PLAIN_3]
    clean = [PLAIN, PLAIN_2, PLAIN_3]
    assert readability_summary(padded) == readability_summary(clean)
    assert readability_summary(padded)["sample_size"] == 3


@pytest.mark.parametrize("texts", [
    [],
    [None, "", "   "],
    ["!!!", "..."],
])
def test_empty_sample_returns_the_none_shaped_dict(texts: list[str | None]) -> None:
    summary = readability_summary(texts)
    assert summary["sample_size"] == 0
    assert summary["avg_grade"] is None
    assert summary["median_grade"] is None
    assert summary["share_at_or_below_target"] is None
    assert summary["meets_target"] is None
    # The target still has to be reported: the dashboard renders "-- / 12".
    assert summary["target_grade"] == pytest.approx(DEFAULT_TARGET_GRADE)


def test_plain_sample_passes_and_legalese_sample_fails_ac_p04() -> None:
    passing = readability_summary([PLAIN, PLAIN_2, PLAIN_3])
    assert passing["meets_target"] is True
    assert passing["share_at_or_below_target"] == pytest.approx(1.0)

    failing = readability_summary([LEGALESE, LEGALESE])
    assert failing["meets_target"] is False
    assert failing["share_at_or_below_target"] == pytest.approx(0.0)


def test_target_grade_is_honoured_and_echoed() -> None:
    assert DEFAULT_TARGET_GRADE == 12.0  # the acceptance criterion itself
    strict = readability_summary([PLAIN, LEGALESE], target_grade=8.0)
    lenient = readability_summary([PLAIN, LEGALESE], target_grade=40.0)

    assert strict["target_grade"] == pytest.approx(8.0)
    assert lenient["target_grade"] == pytest.approx(40.0)
    # Same sample, same grades — only the bar moved.
    assert strict["avg_grade"] == lenient["avg_grade"]
    assert strict["meets_target"] is False
    assert lenient["meets_target"] is True
    assert strict["share_at_or_below_target"] < lenient["share_at_or_below_target"]


def test_summary_accepts_any_iterable() -> None:
    # /api/metrics passes a generator over the run's clause summaries.
    from_generator = readability_summary(t for t in MIXED_SAMPLE)
    assert from_generator == readability_summary(MIXED_SAMPLE)
