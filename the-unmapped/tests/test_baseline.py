"""Tests for the keyword-matching baseline (engine/keyword_baseline.py)."""
from __future__ import annotations

import pytest

from engine.keyword_baseline import extract_skills, load_terms


def test_overlapping_alias_longest_wins(terms, skill_ids):
    preds = extract_skills("I improved business communication with clients.", terms)
    labels = [p["label"] for p in preds]
    assert labels == ["Business Communication"], f"got {labels}"
    assert all(p["skill_id"] in skill_ids for p in preds)


def test_evidence_spans_exact_on_pilot(terms, pilot):
    n = 0
    for rec in pilot:
        text = rec["description"]
        for p in extract_skills(text, terms):
            n += 1
            assert text[p["start"]:p["end"]] == p["span"], (rec["example_id"], p)
            assert p["span"], "span must be non-empty"
            assert 0 <= p["start"] < p["end"] <= len(text)
    assert n > 0, "baseline should fire at least once on the pilot set"


def test_alias_resolution(terms):
    preds = extract_skills("I did accounts in Tally and made bills in Excel.", terms)
    by_label = {p["label"]: p for p in preds}
    assert by_label["Financial Accounting"]["source"] == "alias"
    assert by_label["Financial Accounting"]["span"] == "Tally"
    assert by_label["Excel/Spreadsheets"]["span"] == "Excel"


def test_case_insensitive_matching(terms):
    preds = extract_skills("EXCEL and excel and Excel", terms)
    assert len(preds) == 3
    assert [p["span"] for p in preds] == ["EXCEL", "excel", "Excel"]


def test_empty_and_whitespace_input(terms):
    assert extract_skills("", terms) == []
    assert extract_skills("   \n\t  ", terms) == []


def test_unknown_terms_safely_ignored(terms):
    assert extract_skills("I love quantum teleportation xyzzy plugh.", terms) == []


def test_non_string_input_raises(terms):
    with pytest.raises(TypeError):
        extract_skills(None, terms)


def test_deterministic(terms, pilot):
    text = pilot[0]["description"]
    assert extract_skills(text, terms) == extract_skills(text, terms)


def test_predictions_reference_canonical_ids(terms, skill_ids, pilot):
    for rec in pilot:
        for p in extract_skills(rec["description"], terms):
            assert p["skill_id"] in skill_ids
            assert p["source"] in {"label", "alias"}


def test_no_duplicate_predictions(terms, pilot):
    for rec in pilot:
        preds = extract_skills(rec["description"], terms)
        keys = [(p["skill_id"], p["start"], p["end"]) for p in preds]
        assert len(keys) == len(set(keys)), f"dupes in {rec['example_id']}"


def test_load_terms_deterministic_order():
    from .conftest import PROCESSED
    a = [(t.term, t.skill_id) for t in load_terms(PROCESSED)]
    b = [(t.term, t.skill_id) for t in load_terms(PROCESSED)]
    assert a == b
