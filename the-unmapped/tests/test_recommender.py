"""Tests for the Transition Recommender (engine/recommender.py)."""
from __future__ import annotations

import csv
from pathlib import Path

import pytest

from engine.recommender import TransitionRecommender, recommend

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "indian_skills_dataset.csv"
PROCESSED = ROOT / "data" / "processed"


@pytest.fixture(scope="module")
def rec() -> TransitionRecommender:
    return TransitionRecommender.build(RAW, PROCESSED)


def test_valid_target_partitions_skills(rec):
    out = rec.recommend(["SKL-092", "SKL-089"], "soc_13-2011_00")
    matched = {s["skill_id"] for s in out["matched_skills"]}
    missing = {s["skill_id"] for s in out["missing_skills"]}
    assert matched | missing == set(rec.occ_skills["soc_13-2011_00"])
    assert not matched & missing
    assert out["target_occupation"]["title"] == "Accountants and Auditors"


def test_invalid_target_raises(rec):
    with pytest.raises(ValueError, match="unknown target occupation"):
        rec.recommend(["SKL-001"], "soc_00-0000.00")


def test_unknown_skill_ids_warned_and_excluded(rec):
    out = rec.recommend(["SKL-092", "SKL-999", "NOPE"], "soc_13-2011_00")
    assert out["profile"]["n_skills"] == 1
    assert any("unknown skill IDs" in w for w in out["warnings"])
    assert "SKL-999" in out["profile"]["unknown_skill_ids"]


def test_duplicate_skills_deduped(rec):
    out = rec.recommend(["SKL-092", "SKL-092", "SKL-092"], "soc_13-2011_00")
    assert out["profile"]["n_skills"] == 1
    assert any("deduplicated" in w for w in out["warnings"])


def test_empty_profile(rec):
    out = rec.recommend([], "soc_13-2011_00")
    assert out["matched_skills"] == []
    assert len(out["missing_skills"]) == 10
    assert out["skill_overlap"]["dice"] == 0.0
    assert out["pathway"], "empty profile still gets a full pathway"


def test_deterministic_and_explanation_consistent(rec):
    a = rec.recommend(["SKL-092", "SKL-089"], "soc_13-2011_00", "12th Pass")
    b = rec.recommend(["SKL-089", "SKL-092"], "soc_13-2011_00", "12th Pass")
    assert a == b
    assert a["explanation"] == b["explanation"]


def test_heuristic_separated_from_probability(rec):
    out = rec.recommend(["SKL-092"], "soc_13-2011_00")
    assert "probability" not in out
    assert "NOT a probability" in out["score_note"]
    assert out["twelve_month_feasibility"]["available"] is False
    assert "no observed transition-outcome labels" in \
        out["twelve_month_feasibility"]["reason"]


def test_education_fit(rec):
    low = rec.recommend(["SKL-092"], "soc_13-2011_00", profile_education="12th Pass")
    high = rec.recommend(["SKL-092"], "soc_13-2011_00", profile_education="Master's")
    assert low["score_breakdown"]["education_fit"] < 1.0  # requires Bachelor's
    assert high["score_breakdown"]["education_fit"] == 1.0
    with pytest.raises(ValueError, match="unknown education level"):
        rec.recommend(["SKL-092"], "soc_13-2011_00", profile_education="Hogwarts")


def test_pathway_prioritized_and_sourced(rec):
    out = rec.recommend(["SKL-092"], "soc_13-2011_00")
    prios = [p["priority_score"] for p in out["pathway"]]
    assert prios == sorted(prios, reverse=True)
    assert len(out["pathway"]) == len(out["missing_skills"])
    for p in out["pathway"]:
        sources = {s["source"] for s in p["next_steps"]}
        assert sources <= {"dataset", "heuristic_suggestion"}
        assert p["why"]  # every step explains itself


def test_no_invented_dataset_facts(rec):
    out = rec.recommend(["SKL-092"], "soc_13-2011_00")
    occ = out["target_occupation"]
    assert occ["salary_lpa_median"] == 11  # from dataset, not invented
    assert occ["education_required"] == "Bachelor's"
    assert occ["qualifying_exams"], "dataset exams must be surfaced"


def test_missing_columns_raise(tmp_path):
    bad = tmp_path / "bad.csv"
    with bad.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "title"])
        w.writerow(["x", "y"])
    with pytest.raises(ValueError, match="missing required columns"):
        TransitionRecommender.build(bad, PROCESSED)


def test_context_fit_with_extractor():
    """Code path for occupation-context fit, with a tiny stub vectorizer."""
    from sklearn.feature_extraction.text import TfidfVectorizer

    class StubExtractor:
        def __init__(self):
            self.vectorizer = TfidfVectorizer()
            docs = ["accounts finance audit tax", "nursing patient care health"]
            self._occ_matrix = self.vectorizer.fit_transform(docs)
            self.occ_ids = ["soc_13-2011_00", "soc_29-1141_00"]

    rec = TransitionRecommender.build(RAW, PROCESSED, extractor=StubExtractor())
    out = rec.recommend(["SKL-092", "SKL-002"], "soc_13-2011_00")
    assert "context_fit" in out["score_breakdown"]
    assert not any("context fit unavailable" in w for w in out["warnings"])


def test_module_level_recommend():
    out = recommend(["SKL-092"], "soc_13-2011_00")
    assert out["target_occupation"]["id"] == "soc_13-2011_00"
