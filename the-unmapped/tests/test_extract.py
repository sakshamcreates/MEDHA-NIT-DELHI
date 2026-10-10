"""Tests for the TF-IDF Skills Signal Engine (engine/extract.py)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine.extract import (MAX_INPUT_CHARS, ExtractorConfig, SkillExtractor,
                            extract_skills, get_extractor)


@pytest.fixture(scope="module")
def ext() -> SkillExtractor:
    root = Path(__file__).resolve().parent.parent
    return SkillExtractor.build(root / "data" / "raw" / "indian_skills_dataset.csv",
                                root / "data" / "processed",
                                ExtractorConfig(vectorizer="word", ctx_mode="maxpool"))


@pytest.fixture(scope="module")
def skill_ids(ext) -> set[str]:
    return set(ext.skill_ids)


# --- interface validation ----------------------------------------------------

def test_empty_input_abstains(ext):
    out = ext.extract_skills("   ")
    assert out["abstained"] is True
    assert out["abstention_reason"] == "empty_input"
    assert out["skills"] == []


def test_non_string_raises(ext):
    with pytest.raises(TypeError):
        ext.extract_skills(None)
    with pytest.raises(TypeError):
        ext.extract_skills(123)


def test_too_long_input_raises(ext):
    with pytest.raises(ValueError, match="too long"):
        ext.extract_skills("x" * (MAX_INPUT_CHARS + 1))


@pytest.mark.parametrize("bad", [0, -1, "5", 2.5, True, None])
def test_invalid_top_k_raises(ext, bad):
    with pytest.raises(ValueError):
        ext.extract_skills("data entry work", top_k=bad)


def test_top_k_respected(ext):
    out = ext.extract_skills(
        "I did data entry, accounting, taught students, cooked food, drove deliveries", top_k=2)
    assert len(out["skills"]) <= 2
    assert out["top_k"] == 2


# --- prediction integrity -----------------------------------------------------

def test_canonical_ids_preserved(ext, skill_ids):
    out = ext.extract_skills("I did the accounts in Tally and taught maths to students")
    assert out["skills"], "expected at least one prediction"
    for p in out["skills"]:
        assert p["skill_id"] in skill_ids
        assert p["label"] == ext.skill_labels[ext.skill_ids.index(p["skill_id"])]


def test_deterministic(ext):
    text = "I typed lorry receipts into Excel at high speed"
    assert ext.extract_skills(text) == ext.extract_skills(text)


def test_no_duplicate_skill_ids(ext):
    out = ext.extract_skills("data entry and more data entry, excel spreadsheets excel")
    ids = [p["skill_id"] for p in out["skills"]]
    assert len(ids) == len(set(ids))


def test_direct_evidence_offsets_exact(ext):
    text = "For six months I did data entry at a transport company"
    out = ext.extract_skills(text)
    direct = [p for p in out["skills"] if p["evidence"]["type"] == "direct"]
    assert direct, "expected a direct phrase match for 'data entry'"
    for p in direct:
        ev = p["evidence"]
        assert text[ev["start"]:ev["end"]] == ev["span"]
        assert p["method"] == "phrase_match"


def test_no_fabricated_spans(ext):
    out = ext.extract_skills("I looked after my bedridden grandmother for a year")
    for p in out["skills"]:
        ev = p["evidence"]
        if ev["type"] == "contextual_inference":
            assert "start" not in ev and "end" not in ev, \
                f"fabricated span on {p['skill_id']}"
            assert p["method"] == "contextual_inference"


def test_alias_overlap_dedup(ext):
    out = ext.extract_skills("I improved business communication with clients")
    labels = [p["label"] for p in out["skills"]]
    assert "Business Communication" in labels
    assert "Communication" not in labels, "longest match must win, no dupes"


def test_gates_respected(ext):
    out = ext.extract_skills("I did data entry and accounts in Tally for two years")
    cfg = ext.config
    for p in out["skills"]:
        assert p["score"] >= cfg.review_threshold
        assert p["confidence"] in {"high", "review"}
        if p["confidence"] == "high":
            assert p["score"] >= cfg.high_threshold


def test_ambiguity_flagging_mechanism():
    root = Path(__file__).resolve().parent.parent
    ext = SkillExtractor.build(
        root / "data" / "raw" / "indian_skills_dataset.csv",
        root / "data" / "processed",
        ExtractorConfig(vectorizer="word", ctx_mode="maxpool", ambiguity_margin=999.0))
    out = ext.extract_skills("my typing speed is very good and I finish work at speed")
    by_id = {p["skill_id"]: p for p in out["skills"]}
    # SKL-237 Typing Speed, SKL-198 Speed: near-duplicate pair, both predicted
    assert "SKL-237" in by_id and "SKL-198" in by_id
    for sid in ("SKL-237", "SKL-198"):
        assert by_id[sid]["confidence"] == "review"
        assert any(n.startswith("ambiguous_with:") for n in by_id[sid]["notes"])
    # never merged: distinct canonical IDs preserved
    assert by_id["SKL-237"]["label"] == "Typing Speed"
    assert by_id["SKL-198"]["label"] == "Speed"


def test_occupation_context_present(ext):
    out = ext.extract_skills("I did data entry at a transport company")
    assert out["skills"]
    for p in out["skills"]:
        ctx = p["occupation_context"]
        assert len(ctx) == 2
        for c in ctx:
            assert c["occupation_id"] in ext.occ_ids
            assert c["title"]


def test_scores_not_probabilities(ext):
    out = ext.extract_skills("data entry")
    assert "NOT a calibrated probability" in out["model"]["score_note"]


def test_low_confidence_abstention(ext):
    out = ext.extract_skills("xyzzy plugh quantum")
    assert out["abstained"] is True
    assert out["abstention_reason"] == "no_confident_predictions"


# --- build / persistence -------------------------------------------------------

def test_missing_columns_raise(tmp_path):
    import csv
    bad = tmp_path / "bad.csv"
    with bad.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "title"])  # missing chunk_text etc.
        w.writerow(["x", "y"])
    root = Path(__file__).resolve().parent.parent
    with pytest.raises(ValueError, match="missing required columns"):
        SkillExtractor.build(bad, root / "data" / "processed")


def test_save_load_roundtrip(ext, tmp_path):
    path = tmp_path / "ext.joblib"
    ext.save(path)
    ext2 = SkillExtractor.load(path)
    text = "I typed lorry receipts into Excel at high speed"
    assert ext2.extract_skills(text) == ext.extract_skills(text)
    assert ext2.data_checksum == ext.data_checksum


def test_module_level_interface():
    out = extract_skills("I did data entry work", top_k=5)
    assert out["top_k"] == 5
    assert isinstance(out["skills"], list)
    assert get_extractor() is get_extractor(), "singleton"


def test_baseline_still_independent():
    from engine.keyword_baseline import extract_skills as b
    from tests.conftest import PROCESSED
    from engine.keyword_baseline import load_terms
    preds = b("I improved business communication", load_terms(PROCESSED))
    assert [p["label"] for p in preds] == ["Business Communication"]
