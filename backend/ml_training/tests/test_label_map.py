"""Tests for src/label_map.py."""
from __future__ import annotations

from src.label_map import CG8_TARGETS, LEDGAR_TO_CG8, map_label, map_labels


def test_cg8_targets_are_eight():
    assert len(CG8_TARGETS) == 8


def test_explicit_dict_only_maps_to_known_targets():
    for ledgar, cg8 in LEDGAR_TO_CG8.items():
        assert cg8 in CG8_TARGETS, f"{ledgar} -> {cg8} not in CG8_TARGETS"


def test_map_label_unknown_falls_to_general():
    assert map_label("Severability") == "general"
    assert map_label("Notices") == "general"
    assert map_label("Counterparts") == "general"
    assert map_label("__definitely_not_a_label__") == "general"


def test_map_label_case_insensitive():
    assert map_label("INTELLECTUAL PROPERTY") == "ip_assignment"
    assert map_label("Intellectual Property") == "ip_assignment"


def test_map_labels_batch():
    out = map_labels(["Payments", "Severability", "Confidentiality"])
    assert out == ["payment_terms", "general", "confidentiality"]
