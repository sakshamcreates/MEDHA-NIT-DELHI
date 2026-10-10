"""Tests for the human-review workflow (Phase 4, Part A)."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from scripts.review_pilot import (DuplicateReviewError, apply_decision, load_pilot,
                                  load_registry, reviewed_label_set, save_review,
                                  validate_review, load_reviews, review_history,
                                  reviewers_in)
from scripts.review_pairs import (apply_pair_decision, load_queue,
                                  validate_pair_review)


@pytest.fixture(scope="module")
def pilot():
    return load_pilot()


@pytest.fixture(scope="module")
def registry():
    return load_registry()


@pytest.fixture(scope="module")
def example(pilot):
    return pilot[0]


def test_apply_approve_keeps_labels(example):
    rec = apply_decision(example, "approved", [], "looks good", "tester")
    assert rec["decision"] == "approved"
    assert rec["reviewer"] == "tester"
    assert rec["reviewed_at"]
    assert [s["skill_id"] for s in rec["skills"]] == \
           [s["skill_id"] for s in example["expected_skills"]]
    assert all(s["change"] == "kept" for s in rec["skills"])


def test_apply_reject_carries_no_skills(example):
    rec = apply_decision(example, "rejected", [], "bad description", "tester")
    assert rec["decision"] == "rejected" and rec["skills"] == []


def test_apply_bad_decision_raises(example):
    with pytest.raises(ValueError):
        apply_decision(example, "maybe", [], "", "tester")


def test_validate_catches_problems(example, registry):
    rec = apply_decision(example, "corrected",
                         [{"skill_id": "SKL-999", "skill_label": "Nope",
                           "evidence_span": "not in text", "change": "added"}],
                         "", reviewer="")
    problems = validate_review(rec, example, registry)
    assert any("unknown skill_id" in p for p in problems)
    assert any("not verbatim" in p for p in problems)
    assert any("reviewer" in p for p in problems)


def test_reviews_stored_separately(pilot, tmp_path):
    """Decisions go to the reviews file; the pilot file is never mutated."""
    out = tmp_path / "pilot_reviews.jsonl"
    ex = pilot[1]
    rec = apply_decision(ex, "approved", [], "", "tester")
    stored = save_review(out, rec)
    assert stored["version"] == 1
    saved = load_reviews(out)
    assert list(saved) == [(ex["example_id"], "tester")]
    # pilot source untouched: still pending, no reviewer fields
    for r in pilot:
        assert r["review_status"] == "pending"
        assert "reviewer" not in r


def test_reviewed_label_set_excludes_pending_and_rejected(pilot):
    ex_a, ex_b, ex_c = pilot[0], pilot[1], pilot[2]
    reviews = {
        (ex_a["example_id"], "t"): apply_decision(ex_a, "approved", [], "", "t"),
        (ex_b["example_id"], "t"): apply_decision(ex_b, "rejected", [], "bad", "t"),
    }
    got = reviewed_label_set(pilot, reviews)
    assert ex_a["example_id"] in got
    assert ex_b["example_id"] not in got
    assert ex_c["example_id"] not in got  # pending


def test_corrected_labels_used(pilot):
    ex = pilot[0]
    corrected = [{"skill_id": "SKL-092", "skill_label": "Financial Accounting",
                  "evidence_span": ex["description"][:10], "change": "kept"}]
    assert corrected[0]["evidence_span"] in ex["description"]
    rec = apply_decision(ex, "corrected", corrected, "trimmed", "t")
    got = reviewed_label_set(pilot, {(ex["example_id"], "t"): rec})
    assert got[ex["example_id"]] == corrected


# --- pair reviews -------------------------------------------------------------

@pytest.fixture(scope="module")
def pair():
    return load_queue()[0]


@pytest.fixture(scope="module")
def reg_by_id():
    from scripts.review_pairs import load_registry as lr
    return lr()


def test_pair_keep_separate_default(pair, reg_by_id):
    rec = apply_pair_decision(pair, "keep_separate", "", "", "skills stay distinct", "t")
    assert validate_pair_review(rec, pair, reg_by_id) == []


def test_pair_rationale_required(pair, reg_by_id):
    rec = apply_pair_decision(pair, "keep_separate", "", "", "", "t")
    assert any("rationale" in p for p in validate_pair_review(rec, pair, reg_by_id))


def test_pair_merge_needs_valid_canonical(pair, reg_by_id):
    rec = apply_pair_decision(pair, "merge", "SKL-999", "", "rationale", "t")
    assert any("canonical_skill_id" in p for p in validate_pair_review(rec, pair, reg_by_id))
    rec = apply_pair_decision(pair, "merge", pair["skill_a_id"], "", "rationale", "t")
    assert validate_pair_review(rec, pair, reg_by_id) == []


def test_pair_alias_records_text(pair, reg_by_id):
    rec = apply_pair_decision(pair, "alias", pair["skill_b_id"],
                              pair["skill_a_label"], "true synonym", "t")
    assert validate_pair_review(rec, pair, reg_by_id) == []
    assert rec["alias_text"] == pair["skill_a_label"]
    assert rec["canonical_skill_id"] == pair["skill_b_id"]


# --- patch application ---------------------------------------------------------

def _tmp_processed(tmp_path) -> Path:
    from tests.conftest import PROCESSED
    d = tmp_path / "processed"
    d.mkdir()
    for name in ("skill_registry.csv", "skill_aliases.csv"):
        shutil.copy(PROCESSED / name, d / name)
    return d


def test_patch_dry_run_empty_without_reviews(tmp_path):
    from scripts.apply_registry_patch import plan
    d = _tmp_processed(tmp_path)
    assert plan(d, tmp_path / "none.jsonl") == []


def test_patch_apply_alias_idempotent(tmp_path, pair):
    from scripts.apply_registry_patch import apply, plan
    d = _tmp_processed(tmp_path)
    rev_path = tmp_path / "pair_reviews.jsonl"
    rec = apply_pair_decision(pair, "alias", pair["skill_b_id"],
                              pair["skill_a_label"], "synonym", "t")
    rev_path.write_text(json.dumps(rec) + "\n", encoding="utf-8")
    ops = plan(d, rev_path)
    assert len(ops) == 1 and ops[0]["op"] == "alias"
    n_before = sum(1 for _ in (d / "skill_aliases.csv").open())
    apply(ops, d)
    apply(plan(d, rev_path), d)  # second run: nothing pending
    n_after = sum(1 for _ in (d / "skill_aliases.csv").open())
    assert n_after == n_before + 1, "alias appended exactly once"
    assert not (d / "skill_deprecations.csv").exists() or \
        sum(1 for _ in (d / "skill_deprecations.csv").open()) <= 1


def test_patch_apply_merge_keeps_ids(tmp_path, pair):
    from scripts.apply_registry_patch import apply, plan
    d = _tmp_processed(tmp_path)
    rev_path = tmp_path / "pair_reviews.jsonl"
    rec = apply_pair_decision(pair, "merge", pair["skill_a_id"], "",
                              "same concept", "t")
    rev_path.write_text(json.dumps(rec) + "\n", encoding="utf-8")
    apply(plan(d, rev_path), d)
    dep = d / "skill_deprecations.csv"
    assert dep.exists()
    rows = list(dep.read_text(encoding="utf-8").splitlines())
    assert len(rows) == 2  # header + one deprecation
    # deprecated ID still present in the registry (traceability)
    reg_ids = {r["skill_id"] for r in
               __import__("csv").DictReader((d / "skill_registry.csv").open())}
    assert pair["skill_b_id"] in reg_ids, "deprecated ID must not be deleted"
