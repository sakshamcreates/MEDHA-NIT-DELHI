"""Tests for the skill registry artifacts (scripts/build_registry.py)."""
from __future__ import annotations

import hashlib
import re
import subprocess
import sys
from pathlib import Path

import pytest

from .conftest import PROCESSED, ROOT

FILES = ["skill_registry.csv", "occupation_skill_map.csv", "skill_aliases.csv",
         "skill_review_queue.csv", "domain_skill_summary.csv"]


def test_all_artifact_files_exist():
    for name in FILES:
        assert (PROCESSED / name).exists(), f"missing {name}"


def test_canonical_ids_unique_and_sequential(registry):
    ids = [r["skill_id"] for r in registry]
    assert len(ids) == len(set(ids)) == 241, "IDs must be unique (241 skills)"
    assert all(re.fullmatch(r"SKL-\d{3}", i) for i in ids), "ID format SKL-NNN"
    assert sorted(ids) == [f"SKL-{i:03d}" for i in range(1, 242)]


def test_labels_unique(registry):
    labels = [r["label"] for r in registry]
    assert len(labels) == len(set(labels)) == 241


def test_ids_stable_across_runs(tmp_path):
    """Rebuilding into two fresh dirs must produce byte-identical files."""
    for d in ("a", "b"):
        subprocess.run([sys.executable, str(ROOT / "scripts" / "build_registry.py"),
                        "--output-dir", str(tmp_path / d)],
                       check=True, capture_output=True, text=True, cwd=ROOT)
    for name in FILES:
        a = (tmp_path / "a" / name).read_bytes()
        b = (tmp_path / "b" / name).read_bytes()
        assert a == b, f"{name} differs across runs"
        assert hashlib.md5(a).hexdigest() == hashlib.md5(
            (PROCESSED / name).read_bytes()).hexdigest(), f"{name} drifted from committed artifact"


def test_occupation_skill_map_valid(occupation_map, skill_ids, raw_occupation_ids):
    assert len(occupation_map) == 8200
    for row in occupation_map:
        assert row["skill_id"] in skill_ids, f"bad skill ref {row}"
        assert row["occupation_id"] in raw_occupation_ids, f"bad occupation ref {row}"
    from collections import Counter
    per_occ = Counter(r["occupation_id"] for r in occupation_map)
    assert len(per_occ) == 820
    assert set(per_occ.values()) == {10}, "every occupation must map to exactly 10 skills"


def test_alias_targets_valid(aliases, skill_ids):
    assert len(aliases) >= 1
    for row in aliases:
        assert row["skill_id"] in skill_ids, f"alias points nowhere: {row}"
        assert row["status"].strip().lower() == "approved"
        assert row["alias_type"].strip() in {"spelling_variant", "informal_variant"}
        assert row["notes"].strip(), "every alias needs a documented rationale"


def test_no_skill_invented(aliases, registry):
    labels = {r["label"] for r in registry}
    for row in aliases:
        assert row["canonical_label"] in labels


def test_review_queue_open_and_sourced(skill_ids):
    import csv
    with (PROCESSED / "skill_review_queue.csv").open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) >= 1
    for row in rows:
        assert row["skill_a_id"] in skill_ids and row["skill_b_id"] in skill_ids
        assert row["status"].strip().lower() == "open"
        assert "DO NOT auto-merge" in row["recommendation"]


def test_registry_source_traceability(registry, occupation_map):
    """example_occupations in the registry must exist in the occupation map."""
    occ_ids = {r["occupation_id"] for r in occupation_map}
    for row in registry:
        for occ in row["example_occupations"].split("|"):
            assert occ in occ_ids, f"untraceable example occupation {occ}"
        assert row["source"] == "indian_skills_dataset.csv"
