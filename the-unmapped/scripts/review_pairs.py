#!/usr/bin/env python3
"""Human review workflow for the 41 near-duplicate skill pairs (Phase 4, Part A).

- Displays each pair with both skills' registry data (occupation counts,
  example occupations, shared tokens).
- Default recommendation: KEEP SEPARATE. A merge or alias happens ONLY on
  explicit human approval.
- Decisions recorded in data/evaluation/pair_reviews.jsonl, separate from
  data/processed/skill_review_queue.csv (never mutated).
- Canonical-ID traceability: merges/aliases never delete skill IDs; the
  patch applier (scripts/apply_registry_patch.py) records them in
  skill_deprecations.csv with full provenance.

Usage:
    .venv/bin/python scripts/review_pairs.py --reviewer "Your Name"
"""
from __future__ import annotations

import argparse
import csv
import datetime
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TOOL_VERSION = "review_pairs.py v0.1.0"
QUEUE = ROOT / "data" / "processed" / "skill_review_queue.csv"
PAIR_REVIEWS = ROOT / "data" / "evaluation" / "pair_reviews.jsonl"
REGISTRY = ROOT / "data" / "processed" / "skill_registry.csv"

DECISIONS = ("keep_separate", "merge", "alias")


def utcnow() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_queue() -> list[dict]:
    with QUEUE.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_registry() -> dict[str, dict]:
    with REGISTRY.open(encoding="utf-8") as f:
        return {r["skill_id"]: r for r in csv.DictReader(f)}


def load_pair_reviews(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    out = {}
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                r = json.loads(line)
                out[r["pair_id"]] = r
    return out


def save_pair_review(path: Path, record: dict) -> None:
    reviews = load_pair_reviews(path)
    reviews[record["pair_id"]] = record
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for pid in sorted(reviews):
            f.write(json.dumps(reviews[pid], ensure_ascii=False) + "\n")


def validate_pair_review(record: dict, pair: dict, registry: dict[str, dict]) -> list[str]:
    problems = []
    if record["pair_id"] != pair["pair_id"]:
        problems.append("pair_id mismatch")
    if record["decision"] not in DECISIONS:
        problems.append(f"bad decision: {record['decision']}")
    if not record.get("reviewer"):
        problems.append("reviewer name required")
    if not record.get("rationale", "").strip():
        problems.append("rationale required for every pair decision")
    if record["decision"] in ("merge", "alias"):
        canon = record.get("canonical_skill_id")
        valid = {pair["skill_a_id"], pair["skill_b_id"]}
        if canon not in valid:
            problems.append(f"canonical_skill_id must be one of {sorted(valid)}")
        if record["decision"] == "alias" and not record.get("alias_text", "").strip():
            problems.append("alias_text required for alias decisions")
        if record.get("alias_text") and record["alias_text"] not in {
                pair["skill_a_label"], pair["skill_b_label"]}:
            problems.append("alias_text must be one of the two pair labels")
    return problems


def apply_pair_decision(pair: dict, decision: str, canonical_skill_id: str,
                        alias_text: str, rationale: str, reviewer: str) -> dict:
    if decision not in DECISIONS:
        raise ValueError(f"bad decision: {decision}")
    return {
        "pair_id": pair["pair_id"],
        "skill_a_id": pair["skill_a_id"],
        "skill_a_label": pair["skill_a_label"],
        "skill_b_id": pair["skill_b_id"],
        "skill_b_label": pair["skill_b_label"],
        "reviewer": reviewer,
        "reviewed_at": utcnow(),
        "decision": decision,
        "canonical_skill_id": canonical_skill_id or "",
        "alias_text": alias_text or "",
        "rationale": rationale,
        "tool": TOOL_VERSION,
    }


def _show_pair(pair: dict, registry: dict[str, dict], idx: int, total: int) -> None:
    print(f"\n{'='*70}\n[{idx}/{total}] {pair['pair_id']} "
          f"(relation: {pair['relation']}, shared: {pair['shared_tokens']})")
    for side in ("a", "b"):
        sid = pair[f"skill_{side}_id"]
        reg = registry[sid]
        print(f"  {sid} {pair[f'skill_{side}_label']}\n"
              f"    occupations: {reg['occupation_count']} "
              f"e.g. {reg['example_occupations']}")


def review_interactive(pairs: list[dict], reviews: dict[str, dict],
                       reviewer: str, out_path: Path) -> None:
    registry = load_registry()
    pending = [p for p in pairs if p["pair_id"] not in reviews]
    print(f"{len(pending)} of {len(pairs)} pairs pending review. "
          f"Default: KEEP SEPARATE unless you explicitly approve otherwise.")
    for i, pair in enumerate(pending, 1):
        _show_pair(pair, registry, i, len(pending))
        while True:
            ans = input("[k]eep separate / [m]erge / [a]lias / [s]kip / [q]uit: "
                        ).strip().lower()
            if ans in ("k", "m", "a", "s", "q"):
                break
        if ans == "q":
            break
        if ans == "s":
            continue
        rationale = input("  rationale (required): ").strip()
        canon, alias_text = "", ""
        if ans in ("m", "a"):
            print(f"  1. {pair['skill_a_id']} {pair['skill_a_label']}")
            print(f"  2. {pair['skill_b_id']} {pair['skill_b_label']}")
            pick = input("  canonical skill (1/2): ").strip()
            canon = pair["skill_a_id"] if pick == "1" else pair["skill_b_id"]
            if ans == "a":
                alias_text = pair["skill_b_label"] if pick == "1" else pair["skill_a_label"]
                print(f"  alias: {alias_text!r} -> {canon}")
            else:
                print(f"  WARNING: merge keeps BOTH IDs; {pair['skill_a_id'] if pick=='2' else pair['skill_b_id']}"
                      f" will be deprecated (traceable) in favor of {canon}.")
                confirm = input("  type MERGE to confirm: ").strip()
                if confirm != "MERGE":
                    print("  cancelled"); continue
        decision = {"k": "keep_separate", "m": "merge", "a": "alias"}[ans]
        record = apply_pair_decision(pair, decision, canon, alias_text, rationale, reviewer)
        problems = validate_pair_review(record, pair, registry)
        if problems:
            print("  !! invalid review, not saved:", problems)
            continue
        save_pair_review(out_path, record)
        print(f"  saved {decision} for {pair['pair_id']}")
    print(f"\nDone. {len(load_pair_reviews(out_path))} pairs reviewed total.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Review near-duplicate skill pairs.")
    ap.add_argument("--reviewer", required=True)
    ap.add_argument("--output", default=str(PAIR_REVIEWS))
    args = ap.parse_args()
    review_interactive(load_queue(), load_pair_reviews(Path(args.output)),
                       args.reviewer, Path(args.output))


if __name__ == "__main__":
    main()
