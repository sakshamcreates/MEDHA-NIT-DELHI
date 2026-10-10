"""Shared fixtures for Phase 2 tests."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PROCESSED = ROOT / "data" / "processed"
RAW_CSV = ROOT / "data" / "raw" / "indian_skills_dataset.csv"
PILOT = ROOT / "data" / "evaluation" / "pilot_descriptions.jsonl"


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


@pytest.fixture(scope="session")
def registry() -> list[dict]:
    return read_csv(PROCESSED / "skill_registry.csv")


@pytest.fixture(scope="session")
def skill_ids(registry) -> set[str]:
    return {r["skill_id"] for r in registry}


@pytest.fixture(scope="session")
def occupation_map() -> list[dict]:
    return read_csv(PROCESSED / "occupation_skill_map.csv")


@pytest.fixture(scope="session")
def aliases() -> list[dict]:
    return read_csv(PROCESSED / "skill_aliases.csv")


@pytest.fixture(scope="session")
def raw_occupation_ids() -> set[str]:
    ids = set()
    with RAW_CSV.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            ids.add(row["id"].strip())
    return ids


@pytest.fixture(scope="session")
def pilot() -> list[dict]:
    with PILOT.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


@pytest.fixture(scope="session")
def terms():
    from engine.keyword_baseline import load_terms
    return load_terms(PROCESSED)
