"""Tests for the pilot dataset (data/evaluation/pilot_descriptions.jsonl)."""
from __future__ import annotations

REQUIRED_KEYS = {"example_id", "description", "target_occupation_id",
                 "target_occupation_title", "target_domain", "expected_skills",
                 "review_status", "reviewer_notes", "synthetic"}


def test_exactly_30_examples(pilot):
    assert len(pilot) == 30
    ids = [r["example_id"] for r in pilot]
    assert ids == [f"PILOT-{i:03d}" for i in range(1, 31)], "stable sequential IDs"


def test_schema(pilot):
    for rec in pilot:
        assert REQUIRED_KEYS <= set(rec), f"missing keys in {rec.get('example_id')}"
        assert isinstance(rec["description"], str) and rec["description"].strip()
        assert isinstance(rec["expected_skills"], list) and 3 <= len(rec["expected_skills"]) <= 7
        for s in rec["expected_skills"]:
            assert {"skill_id", "skill_label", "evidence_span"} <= set(s)


def test_all_pending_and_synthetic(pilot):
    for rec in pilot:
        assert rec["review_status"] == "pending", \
            f"{rec['example_id']} must stay pending until human-reviewed"
        assert rec["synthetic"] is True, "pilot must never be presented as real user data"
        assert rec["reviewer_notes"] == ""


def test_evidence_spans_are_verbatim_substrings(pilot):
    for rec in pilot:
        for s in rec["expected_skills"]:
            assert s["evidence_span"] in rec["description"], \
                f"{rec['example_id']}: span not verbatim: {s['evidence_span']!r}"


def test_skill_ids_in_registry(pilot, skill_ids):
    for rec in pilot:
        for s in rec["expected_skills"]:
            assert s["skill_id"] in skill_ids, \
                f"{rec['example_id']}: unknown skill {s['skill_id']}"


def test_target_occupations_exist(pilot, raw_occupation_ids):
    for rec in pilot:
        assert rec["target_occupation_id"] in raw_occupation_ids, \
            f"{rec['example_id']}: unknown occupation"


def test_description_length_bounds(pilot):
    for rec in pilot:
        n = len(rec["description"].split())
        assert 30 <= n <= 130, f"{rec['example_id']}: {n} words"


def test_domain_coverage(pilot):
    domains = {r["target_domain"] for r in pilot}
    assert len(domains) >= 10, f"pilot should span >=10 domains, got {len(domains)}"
