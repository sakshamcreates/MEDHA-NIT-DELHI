#!/usr/bin/env python3
"""Apply approved near-duplicate pair decisions to the registry (Phase 4, Part A).

- Reads data/evaluation/pair_reviews.jsonl (human decisions only).
- keep_separate -> no change.
- alias  -> appends an approved alias row to skill_aliases.csv.
- merge  -> alias from the deprecated label to the canonical ID, PLUS a row in
            skill_deprecations.csv. Skill IDs are NEVER deleted: the deprecated
            ID stays in skill_registry.csv and occupation_skill_map.csv with
            full provenance, so every historical reference remains traceable.
- Idempotent: re-running --apply skips already-applied rows.
- Default is --dry-run (prints the plan, changes nothing).

After re-running scripts/build_registry.py (which regenerates CSVs from
scratch), re-run this script with --apply to restore approved decisions.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PROCESSED = ROOT / "data" / "processed"
PAIR_REVIEWS = ROOT / "data" / "evaluation" / "pair_reviews.jsonl"
PATCH_LOG = PROCESSED / "registry_patch_log.jsonl"


def _read(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def plan(processed_dir: Path = PROCESSED,
         reviews_path: Path = PAIR_REVIEWS) -> list[dict]:
    """Return the list of pending patch operations from approved reviews."""
    if not reviews_path.exists():
        return []
    reviews = [json.loads(l) for l in reviews_path.read_text(encoding="utf-8").splitlines()
               if l.strip()]
    aliases = _read(processed_dir / "skill_aliases.csv")
    have = {(r["alias"], r["skill_id"]) for r in aliases}
    ops = []
    for r in reviews:
        if r["decision"] == "keep_separate":
            continue
        canon = r["canonical_skill_id"]
        if r["decision"] == "alias":
            label = r["alias_text"]
        else:  # merge
            label = r["skill_b_label"] if canon == r["skill_a_id"] else r["skill_a_label"]
        if (label, canon) in have:
            continue  # already applied
        ops.append({"op": r["decision"], "alias": label, "skill_id": canon,
                    "pair_id": r["pair_id"], "reviewer": r["reviewer"],
                    "reviewed_at": r["reviewed_at"]})
    return ops


def apply(ops: list[dict], processed_dir: Path = PROCESSED) -> None:
    from scripts.review_pairs import utcnow
    patch_log = processed_dir / "registry_patch_log.jsonl"
    reg = {r["skill_id"]: r["label"] for r in _read(processed_dir / "skill_registry.csv")}
    # append aliases (never edit existing rows)
    with (processed_dir / "skill_aliases.csv").open("a", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        for op in ops:
            w.writerow([op["alias"], op["alias"].strip().lower(), op["skill_id"],
                        reg[op["skill_id"]],
                        "reviewer_approved", "approved",
                        f"pair {op['pair_id']} reviewed by {op['reviewer']} "
                        f"at {op['reviewed_at']}"])
    # deprecations for merges (IDs never deleted)
    dep_path = processed_dir / "skill_deprecations.csv"
    have_dep = set()
    if dep_path.exists():
        have_dep = {(r["deprecated_skill_id"], r["canonical_skill_id"])
                    for r in _read(dep_path)}
    else:
        with dep_path.open("w", encoding="utf-8", newline="") as f:
            csv.writer(f, lineterminator="\n").writerow(
                ["deprecated_skill_id", "deprecated_label", "canonical_skill_id",
                 "pair_id", "decided_by", "decided_at", "note"])
    with dep_path.open("a", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        for op in ops:
            if op["op"] != "merge":
                continue
            dep_id = next(sid for sid, lab in reg.items() if lab == op["alias"])
            if (dep_id, op["skill_id"]) in have_dep:
                continue
            w.writerow([dep_id, op["alias"], op["skill_id"], op["pair_id"],
                        op["reviewer"], op["reviewed_at"],
                        "ID retained for traceability; use canonical_skill_id going forward"])
    with patch_log.open("a", encoding="utf-8") as f:
        for op in ops:
            f.write(json.dumps({**op, "applied_at": utcnow(),
                                "tool": "apply_registry_patch.py"}) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser(description="Apply approved pair decisions.")
    ap.add_argument("--apply", action="store_true",
                    help="execute the patch (default: dry run)")
    args = ap.parse_args()
    ops = plan()
    if not ops:
        print("no pending patch operations (no approved merge/alias decisions, "
              "or all already applied)")
        return
    print(f"{'WOULD APPLY' if not args.apply else 'APPLYING'} {len(ops)} operations:")
    for op in ops:
        print(f"  [{op['op']}] {op['alias']!r} -> {op['skill_id']} "
              f"(pair {op['pair_id']}, by {op['reviewer']})")
    if args.apply:
        apply(ops)
        print("applied. IDs preserved; see skill_deprecations.csv for merges.")


if __name__ == "__main__":
    main()
