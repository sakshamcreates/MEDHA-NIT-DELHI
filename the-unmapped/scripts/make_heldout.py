#!/usr/bin/env python3
"""Generate a locked, versioned held-out split from reviewed labels (Phase 4, Part B).

- Source of labels: data/evaluation/pilot_reviews.jsonl (human decisions ONLY).
- Deterministic split by md5(salt + example_id); dev/test are disjoint by
  construction and membership is recorded in manifest.json.
- Refuses to run when fewer than --min-reviewed examples are reviewed.
- The manifest records data/registry/reviews checksums so any later change is
  detectable (leakage/version integrity).

Generate ONLY after the evaluation protocol and annotation criteria are final.
Usage:
    .venv/bin/python scripts/make_heldout.py --created-by "Your Name"
    .venv/bin/python scripts/make_heldout.py --created-by "x" --version v2 --test-ratio 0.25
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.review_pilot import load_pilot, load_reviews, reviewed_label_set

TOOL_VERSION = "make_heldout.py v0.1.0"
RAW_CSV = ROOT / "data" / "raw" / "indian_skills_dataset.csv"
REGISTRY = ROOT / "data" / "processed" / "skill_registry.csv"
PILOT = ROOT / "data" / "evaluation" / "pilot_descriptions.jsonl"
REVIEWS = ROOT / "data" / "evaluation" / "pilot_reviews.jsonl"


def _md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def _split_ids(ids: list[str], salt: str, test_ratio: float) -> tuple[list[str], list[str]]:
    ranked = sorted(ids, key=lambda i: hashlib.md5(f"{salt}:{i}".encode()).hexdigest())
    n_test = max(1, round(len(ranked) * test_ratio))
    return ranked[n_test:], ranked[:n_test]  # dev, test


def make_heldout(version: str, created_by: str, salt: str, test_ratio: float,
                 min_reviewed: int, out_dir: Path) -> dict:
    pilot = load_pilot()
    by_id = {r["example_id"]: r for r in pilot}
    labeled = reviewed_label_set(pilot, load_reviews(REVIEWS))
    if len(labeled) < min_reviewed:
        raise SystemExit(
            f"REFUSAL: only {len(labeled)} reviewed examples; "
            f"--min-reviewed={min_reviewed} required. Complete human review first.")
    dev_ids, test_ids = _split_ids(sorted(labeled), salt, test_ratio)
    assert not set(dev_ids) & set(test_ids), "split leakage!"
    manifest = {
        "version": version,
        "tool": TOOL_VERSION,
        "created_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "created_by": created_by,
        "salt": salt,
        "test_ratio": test_ratio,
        "data_checksum": _md5(RAW_CSV),
        "registry_checksum": _md5(REGISTRY),
        "pilot_checksum": _md5(PILOT),
        "reviews_checksum": _md5(REVIEWS),
        "n_dev": len(dev_ids), "n_test": len(test_ids),
        "dev_ids": dev_ids, "test_ids": test_ids,
        "note": "Locked split. Do not tune on the test split. "
                "Regenerating with a different salt/version creates a NEW locked split.",
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    for split, ids in (("dev", dev_ids), ("test", test_ids)):
        with (out_dir / f"{split}.jsonl").open("w", encoding="utf-8") as f:
            for ex_id in ids:
                f.write(json.dumps({
                    "example_id": ex_id,
                    "description": by_id[ex_id]["description"],
                    "target_occupation_id": by_id[ex_id]["target_occupation_id"],
                    "expected_skills": labeled[ex_id],
                }, ensure_ascii=False) + "\n")
    return manifest


def main() -> None:
    ap = argparse.ArgumentParser(description="Lock a held-out evaluation split.")
    ap.add_argument("--version", default="v1")
    ap.add_argument("--created-by", required=True)
    ap.add_argument("--salt", default="the-unmapped-heldout")
    ap.add_argument("--test-ratio", type=float, default=0.3)
    ap.add_argument("--min-reviewed", type=int, default=10)
    ap.add_argument("--out-dir", default=None)
    args = ap.parse_args()
    out_dir = Path(args.out_dir) if args.out_dir else \
        ROOT / "data" / "evaluation" / f"heldout_{args.version}"
    if out_dir.exists():
        raise SystemExit(f"REFUSAL: {out_dir} already exists -- held-out splits are "
                         f"immutable; use a new --version.")
    m = make_heldout(args.version, args.created_by, args.salt, args.test_ratio,
                     args.min_reviewed, out_dir)
    print(f"locked {out_dir}: dev={m['n_dev']} test={m['n_test']}")


if __name__ == "__main__":
    main()
