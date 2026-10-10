"""Tests for evaluation integrity (Phase 4, Part B): no leakage, no tuning on test."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import scripts.make_heldout as mh
from scripts.review_pilot import apply_decision, load_pilot


@pytest.fixture()
def reviewed_env(tmp_path, monkeypatch):
    """10 reviewed examples (8 approved, 2 corrected) wired into make_heldout."""
    pilot = load_pilot()
    rev_path = tmp_path / "pilot_reviews.jsonl"
    with rev_path.open("w", encoding="utf-8") as f:
        for i, ex in enumerate(pilot[:10]):
            if i < 8:
                rec = apply_decision(ex, "approved", [], "", "t")
            else:
                skills = [{**s, "change": "kept"} for s in ex["expected_skills"][:2]]
                rec = apply_decision(ex, "corrected", skills, "trimmed", "t")
            f.write(json.dumps(rec) + "\n")
    monkeypatch.setattr(mh, "REVIEWS", rev_path)
    return tmp_path


def test_heldout_refuses_without_reviews(tmp_path, monkeypatch):
    monkeypatch.setattr(mh, "REVIEWS", tmp_path / "missing.jsonl")
    with pytest.raises(SystemExit, match="REFUSAL"):
        mh.make_heldout("v1", "t", "salt", 0.3, 10, tmp_path / "h")


def test_heldout_split_disjoint_and_deterministic(reviewed_env):
    out1 = reviewed_env / "h1"
    out2 = reviewed_env / "h2"
    m1 = mh.make_heldout("v1", "t", "salt123", 0.3, 10, out1)
    m2 = mh.make_heldout("v1", "t", "salt123", 0.3, 10, out2)
    assert m1["dev_ids"] == m2["dev_ids"] and m1["test_ids"] == m2["test_ids"]
    assert not set(m1["dev_ids"]) & set(m1["test_ids"]), "LEAKAGE: overlap!"
    assert len(m1["dev_ids"]) + len(m1["test_ids"]) == 10
    assert m1["test_ids"] and m1["dev_ids"]
    # different salt -> different (but still disjoint) split
    m3 = mh.make_heldout("v1", "t", "other", 0.3, 10, reviewed_env / "h3")
    assert not set(m3["dev_ids"]) & set(m3["test_ids"])


def test_heldout_manifest_records_versions(reviewed_env):
    m = mh.make_heldout("v9", "tester", "s", 0.3, 10, reviewed_env / "h")
    for key in ("data_checksum", "registry_checksum", "pilot_checksum",
                "reviews_checksum", "salt", "created_by", "created_at"):
        assert m[key], f"manifest missing {key}"
    assert m["version"] == "v9"


def test_evaluate_uses_only_manifest_split(reviewed_env):
    from scripts import evaluate_extractor as ev
    import scripts.make_heldout as mh2
    m = mh2.make_heldout("v1", "t", "salt123", 0.3, 10, reviewed_env / "h")
    import scripts.evaluate_extractor as evm
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(evm, "REVIEWS", reviewed_env / "pilot_reviews.jsonl")
    try:
        examples, meta = evm.load_reviewed_examples(m, "test")
        assert {e["example_id"] for e in examples} == set(m["test_ids"])
        assert meta["split"] == "test" and meta["manifest"] == "v1"
        examples_dev, _ = evm.load_reviewed_examples(m, "dev")
        assert {e["example_id"] for e in examples_dev} == set(m["dev_ids"])
    finally:
        monkeypatch.undo()


def test_evaluate_refuses_with_no_reviews(tmp_path, monkeypatch):
    import scripts.evaluate_extractor as evm
    monkeypatch.setattr(evm, "REVIEWS", tmp_path / "missing.jsonl")
    with pytest.raises(SystemExit) as ei:
        evm.load_reviewed_examples(None)
    assert ei.value.code == 2
