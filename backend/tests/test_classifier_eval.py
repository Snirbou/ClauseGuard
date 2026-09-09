"""The committed held-out evaluation sidecar reaches the dashboard, not health."""

from __future__ import annotations

import json

import classifier


def test_eval_sidecar_is_attached_only_on_request(tmp_path, monkeypatch) -> None:
    sidecar = tmp_path / "clause_classifier_v1.eval.json"
    sidecar.write_text(
        json.dumps({"dataset": "x", "labels": ["a", "b"], "confusion_matrix": [[1, 0], [0, 1]]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(classifier, "_EVAL_PATH", sidecar)
    monkeypatch.setattr(classifier, "_eval_cache", None)

    assert "eval" not in classifier.classifier_info()
    info = classifier.classifier_info(include_eval=True)
    assert info["eval"]["confusion_matrix"] == [[1, 0], [0, 1]]
    # Cached: a later rewrite of the file is not re-read within the process.
    sidecar.write_text("{}", encoding="utf-8")
    assert classifier.classifier_info(include_eval=True)["eval"]["labels"] == ["a", "b"]


def test_missing_or_malformed_sidecar_is_not_an_error(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(classifier, "_EVAL_PATH", tmp_path / "missing.json")
    monkeypatch.setattr(classifier, "_eval_cache", None)
    assert "eval" not in classifier.classifier_info(include_eval=True)

    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(classifier, "_EVAL_PATH", bad)
    monkeypatch.setattr(classifier, "_eval_cache", None)
    assert "eval" not in classifier.classifier_info(include_eval=True)


def test_shipped_sidecar_matches_the_artifact_labels() -> None:
    monkeypatched = classifier.classifier_eval()
    if not monkeypatched:
        return  # sidecar not generated in this checkout
    assert set(monkeypatched["labels"]) == set(monkeypatched["per_class"].keys())
    n = len(monkeypatched["labels"])
    assert len(monkeypatched["confusion_matrix"]) == n
    assert all(len(row) == n for row in monkeypatched["confusion_matrix"])
