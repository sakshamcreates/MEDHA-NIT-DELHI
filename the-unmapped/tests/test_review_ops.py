"""Tests for Phase 6 review operations: versioning, duplicates, export/import,
multi-reviewer handling, and the status report."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from scripts.review_pilot import (DuplicateReviewError, apply_batch, apply_decision,
                                  export_cases, import_csv_decisions, load_pilot,
                                  load_registry_by_id, load_reviews, review_history,
                                  reviewed_label_set, reviewers_in, save_review,
                                  validate_review)
from scripts.review_report import build_report


@pytest.fixture(scope="module")
def pilot():
    return load_pilot()


@pytest.fixture()
def out(tmp_path):
    return tmp_path / "pilot_reviews.jsonl"


def _rec(pilot, i, reviewer="r1", decision="approved"):
    return apply_decision(pilot[i], decision, [], "", reviewer)


# --- versioning & duplicates -------------------------------------------------

def test_first_save_is_version_1(pilot, out):
    stored = save_review(out, _rec(pilot, 0))
    assert stored["version"] == 1 and stored["supersedes"] is None


def test_duplicate_refused_without_amend(pilot, out):
    save_review(out, _rec(pilot, 0))
    with pytest.raises(DuplicateReviewError, match="--amend"):
        save_review(out, _rec(pilot, 0))
    # file still has exactly one record
    assert sum(1 for _ in out.open()) == 1


def test_amend_appends_new_version(pilot, out):
    save_review(out, _rec(pilot, 0, decision="approved"))
    v2 = save_review(out, _rec(pilot, 0, decision="rejected"), allow_overwrite=True)
    assert v2["version"] == 2 and v2["supersedes"] == 1
    hist = review_history(out, pilot[0]["example_id"])
    assert [r["version"] for r in hist] == [1, 2]
    assert hist[0]["decision"] == "approved"  # history preserved
    latest = load_reviews(out)[(pilot[0]["example_id"], "r1")]
    assert latest["decision"] == "rejected"


def test_same_example_different_reviewers_coexist(pilot, out):
    save_review(out, _rec(pilot, 0, reviewer="r1"))
    save_review(out, _rec(pilot, 0, reviewer="r2"))
    assert reviewers_in(out) == ["r1", "r2"]


# --- batch atomicity & fabricated-label protection ----------------------------

def test_batch_atomic_on_invalid(pilot, out):
    good = {"example_id": pilot[0]["example_id"], "decision": "approved"}
    bad = {"example_id": pilot[1]["example_id"], "decision": "corrected",
           "skills": [{"skill_id": "SKL-999", "skill_label": "Invented",
                       "evidence_span": "nope", "change": "added"}]}
    with pytest.raises(ValueError, match="nothing was written"):
        apply_batch(pilot, [good, bad], "r1", out)
    assert not out.exists() or out.read_text().strip() == ""


def test_batch_rejects_unknown_example(pilot, out):
    with pytest.raises(ValueError, match="unknown example_id"):
        apply_batch(pilot, [{"example_id": "PILOT-999", "decision": "approved"}],
                      "r1", out)


def test_batch_duplicate_needs_amend(pilot, out):
    d = {"example_id": pilot[0]["example_id"], "decision": "approved"}
    apply_batch(pilot, [d], "r1", out)
    with pytest.raises(DuplicateReviewError):
        apply_batch(pilot, [d], "r1", out)
    recs = apply_batch(pilot, [d], "r1", out, amend=True)
    assert recs[0]["version"] == 2


# --- multi-reviewer label sets -------------------------------------------------

def test_label_set_single_reviewer(pilot, out):
    save_review(out, _rec(pilot, 0))
    got = reviewed_label_set(pilot, load_reviews(out))
    assert list(got) == [pilot[0]["example_id"]]


def test_label_set_multi_reviewer_requires_choice(pilot, out):
    save_review(out, _rec(pilot, 0, reviewer="r1"))
    save_review(out, _rec(pilot, 1, reviewer="r2"))
    with pytest.raises(ValueError, match="specify reviewer"):
        reviewed_label_set(pilot, load_reviews(out))
    got = reviewed_label_set(pilot, load_reviews(out), reviewer="r2")
    assert list(got) == [pilot[1]["example_id"]]


# --- export / import round trip -------------------------------------------------

def test_export_json_and_csv(pilot, tmp_path, out):
    save_review(out, _rec(pilot, 0))
    jp, cp = tmp_path / "cases.json", tmp_path / "cases.csv"
    n_json = export_cases(pilot, load_reviews(out), jp, "json", pending_only=True)
    n_csv = export_cases(pilot, load_reviews(out), cp, "csv", pending_only=True)
    assert n_json == n_csv == 29
    data = json.loads(jp.read_text())
    assert data[0]["example_id"] == pilot[1]["example_id"]
    assert "proposed_skills" in data[0]
    with cp.open() as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["example_id"] == pilot[1]["example_id"]
    assert rows[0]["status"] == "pending"
    assert "decision" in rows[0] and "notes" in rows[0]


def test_import_csv_round_trip(pilot, tmp_path, out):
    cp = tmp_path / "decisions.csv"
    with cp.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["example_id", "decision", "notes"])
        w.writerow([pilot[1]["example_id"], "approved", "looks good"])
        w.writerow([pilot[2]["example_id"], "rejected", "implausible text"])
    records = import_csv_decisions(cp, pilot, "r1", load_registry_by_id())
    assert len(records) == 2
    for rec in records:
        save_review(out, rec)
    got = reviewed_label_set(pilot, load_reviews(out))
    assert pilot[1]["example_id"] in got          # approved
    assert pilot[2]["example_id"] not in got     # rejected excluded


def test_import_csv_rejects_corrected(pilot, tmp_path):
    cp = tmp_path / "d.csv"
    with cp.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["example_id", "decision", "notes"])
        w.writerow([pilot[0]["example_id"], "corrected", ""])
    with pytest.raises(ValueError, match="JSON --batch"):
        import_csv_decisions(cp, pilot, "r1", load_registry_by_id())


def test_import_csv_rejects_unknown_example(pilot, tmp_path):
    cp = tmp_path / "d.csv"
    with cp.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["example_id", "decision", "notes"])
        w.writerow(["PILOT-999", "approved", ""])
    with pytest.raises(ValueError, match="unknown example_id"):
        import_csv_decisions(cp, pilot, "r1", load_registry_by_id())


# --- review report ---------------------------------------------------------------

def test_report_counts_and_incomplete(pilot, tmp_path):
    out = tmp_path / "r.jsonl"
    save_review(out, _rec(pilot, 0, decision="approved"))
    save_review(out, _rec(pilot, 1, decision="corrected"))
    save_review(out, _rec(pilot, 2, decision="rejected"))
    rep = build_report(out)
    assert rep["n_valid_reviews"] == 2
    assert rep["n_pending"] == 27
    assert rep["decisions"] == {"approved": 1, "corrected": 1, "rejected": 1}
    assert rep["evaluation_ready"] is False
    assert rep["status"].startswith("INCOMPLETE: 2/30")


def test_report_flags_invalid_records(pilot, tmp_path):
    out = tmp_path / "r.jsonl"
    rec = _rec(pilot, 0, decision="corrected")
    rec["skills"] = [{"skill_id": "SKL-999", "skill_label": "Fake",
                      "evidence_span": "zzz", "change": "added"}]
    # bypass save-time validation by writing directly (simulates hand-edited file)
    out.write_text(json.dumps(rec) + "\n")
    rep = build_report(out)
    assert rep["n_invalid_records"] == 1
    assert rep["n_valid_reviews"] == 0, "invalid records must not count"
    assert "unknown skill_id" in rep["invalid_records"][0]["problems"][0]


def test_report_agreement(pilot, tmp_path):
    out = tmp_path / "r.jsonl"
    ex = pilot[0]
    # r1 approves all proposed; r2 approves all but one
    save_review(out, apply_decision(ex, "approved", [], "", "r1"))
    kept = [{**s, "change": "kept"} for s in ex["expected_skills"][:-1]]
    save_review(out, apply_decision(ex, "corrected", kept, "dropped one", "r2"))
    rep = build_report(out)
    assert rep["agreement"]["n_doubly_reviewed"] == 1
    a = rep["agreement"]["examples"][0]
    n = len(ex["expected_skills"])
    assert a["exact_match_rate"] == 0.0
    assert a["mean_pairwise_jaccard"] == pytest.approx((n - 1) / n)


def test_report_empty_is_honest(tmp_path):
    rep = build_report(tmp_path / "missing.jsonl")
    assert rep["n_valid_reviews"] == 0 and rep["n_pending"] == 30
    assert rep["status"].startswith("INCOMPLETE")
