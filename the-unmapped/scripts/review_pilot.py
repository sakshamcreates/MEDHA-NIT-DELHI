#!/usr/bin/env python3
"""Human review workflow for the 30 pilot descriptions (Phase 4, Part A).

- Displays each description with its proposed skill labels, evidence spans,
  and canonical skill IDs.
- Reviewer may approve / correct / reject / skip each example.
- Decisions are recorded in data/evaluation/pilot_reviews.jsonl, SEPARATE from
  the original synthetic annotations (pilot_descriptions.jsonl is never mutated).
- Unreviewed examples stay "pending". Nothing is auto-marked as ground truth.

Usage:
    .venv/bin/python scripts/review_pilot.py --reviewer "Your Name"
    .venv/bin/python scripts/review_pilot.py --reviewer "x" --batch decisions.json
    .venv/bin/python scripts/review_pilot.py --reviewer "x" --output /tmp/rev.jsonl
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

TOOL_VERSION = "review_pilot.py v0.1.0"
PILOT = ROOT / "data" / "evaluation" / "pilot_descriptions.jsonl"
REVIEWS = ROOT / "data" / "evaluation" / "pilot_reviews.jsonl"
REGISTRY = ROOT / "data" / "processed" / "skill_registry.csv"

DECISIONS = ("approved", "corrected", "rejected")


def utcnow() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_pilot() -> list[dict]:
    with PILOT.open(encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def load_registry() -> dict[str, str]:
    with REGISTRY.open(encoding="utf-8") as f:
        return {r["label"]: r["skill_id"] for r in csv.DictReader(f)}


def load_reviews(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    out = {}
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                r = json.loads(line)
                out[r["example_id"]] = r
    return out


def save_review(path: Path, record: dict) -> None:
    reviews = load_reviews(path)
    reviews[record["example_id"]] = record
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for ex_id in sorted(reviews):
            f.write(json.dumps(reviews[ex_id], ensure_ascii=False) + "\n")


def validate_review(record: dict, example: dict, registry: dict[str, str]) -> list[str]:
    """Return a list of problems (empty = valid). Pure function, tested."""
    problems = []
    if record["example_id"] != example["example_id"]:
        problems.append("example_id mismatch")
    if record["decision"] not in DECISIONS:
        problems.append(f"bad decision: {record['decision']}")
    if not record.get("reviewer"):
        problems.append("reviewer name required")
    seen = set()
    for s in record.get("skills", []):
        sid = s.get("skill_id")
        if sid in seen:
            problems.append(f"duplicate skill {sid}")
        seen.add(sid)
        if sid not in set(registry.values()):
            problems.append(f"unknown skill_id {sid}")
        span = s.get("evidence_span", "")
        if span and span not in example["description"]:
            problems.append(f"span not verbatim: {span!r}")
        if s.get("change") not in {"kept", "added", "dropped", "span_edited"}:
            problems.append(f"bad change marker for {sid}")
    if record["decision"] == "rejected" and record.get("skills"):
        problems.append("rejected examples must carry no skills")
    return problems


def apply_decision(example: dict, decision: str, corrected_skills: list[dict],
                   notes: str, reviewer: str) -> dict:
    """Build a review record from a decision. Pure function, tested."""
    if decision not in DECISIONS:
        raise ValueError(f"bad decision: {decision}")
    if decision == "approved":
        skills = [{**s, "change": "kept"} for s in example["expected_skills"]]
    elif decision == "rejected":
        skills = []
    else:
        skills = corrected_skills
    return {
        "example_id": example["example_id"],
        "reviewer": reviewer,
        "reviewed_at": utcnow(),
        "decision": decision,
        "skills": skills,
        "notes": notes or "",
        "tool": TOOL_VERSION,
    }


def reviewed_label_set(pilot: list[dict], reviews: dict[str, dict]
                       ) -> dict[str, list[dict]]:
    """example_id -> reviewed skill list. Excludes rejected/pending."""
    out = {}
    for ex in pilot:
        r = reviews.get(ex["example_id"])
        if r and r["decision"] in ("approved", "corrected"):
            out[ex["example_id"]] = r["skills"]
    return out


# ---------------------------------------------------------------------------
# interactive CLI
# ---------------------------------------------------------------------------

def _show_example(ex: dict, idx: int, total: int) -> None:
    print(f"\n{'='*70}\n[{idx}/{total}] {ex['example_id']} "
          f"(target: {ex['target_occupation_title']})")
    print(f"TEXT: {ex['description']}\nProposed skills:")
    for i, s in enumerate(ex["expected_skills"], 1):
        print(f"  {i}. {s['skill_id']} {s['skill_label']}\n"
              f"     evidence: {s['evidence_span']!r}")


def _search_skills(registry: dict[str, str], query: str) -> list[tuple[str, str]]:
    q = query.casefold()
    hits = [(label, sid) for label, sid in registry.items() if q in label.casefold()]
    return sorted(hits)[:10]


def _correct_flow(ex: dict, registry: dict[str, str]) -> tuple[list[dict], str]:
    kept = []
    for s in ex["expected_skills"]:
        ans = input(f"  keep {s['skill_id']} {s['skill_label']}? [Y/n/e(dit span)/d(rop)] ").strip().lower()
        if ans in ("", "y"):
            kept.append({**s, "change": "kept"})
        elif ans == "e":
            new_span = input("  new verbatim span: ").strip()
            if new_span not in ex["description"]:
                print("  !! not a verbatim substring -- skill dropped instead")
                continue
            kept.append({"skill_id": s["skill_id"], "skill_label": s["skill_label"],
                         "evidence_span": new_span, "change": "span_edited"})
        # 'd' or anything else drops
    while True:
        q = input("  add skill (search text, empty to finish): ").strip()
        if not q:
            break
        hits = _search_skills(registry, q)
        if not hits:
            print("  no matches"); continue
        for i, (label, sid) in enumerate(hits, 1):
            print(f"    {i}. {sid} {label}")
        try:
            pick = int(input("  pick number (0=cancel): ").strip())
        except ValueError:
            continue
        if not 1 <= pick <= len(hits):
            continue
        label, sid = hits[pick - 1]
        span = input(f"  verbatim evidence span for {label}: ").strip()
        if span not in ex["description"]:
            print("  !! not a verbatim substring -- not added"); continue
        kept.append({"skill_id": sid, "skill_label": label,
                     "evidence_span": span, "change": "added"})
    notes = input("  reviewer notes: ").strip()
    return kept, notes


def review_interactive(pilot: list[dict], reviews: dict[str, dict],
                       reviewer: str, out_path: Path) -> None:
    registry = load_registry()
    pending = [ex for ex in pilot if ex["example_id"] not in reviews]
    print(f"{len(pending)} of {len(pilot)} examples pending review.")
    for i, ex in enumerate(pending, 1):
        _show_example(ex, i, len(pending))
        while True:
            ans = input("[a]pprove / [c]orrect / [r]eject / [s]kip / [q]uit: ").strip().lower()
            if ans in ("a", "c", "r", "s", "q"):
                break
        if ans == "q":
            break
        if ans == "s":
            continue
        if ans == "r":
            notes = input("  reason for rejection: ").strip()
            record = apply_decision(ex, "rejected", [], notes, reviewer)
        elif ans == "a":
            notes = input("  notes (optional): ").strip()
            record = apply_decision(ex, "approved", [], notes, reviewer)
        else:
            skills, notes = _correct_flow(ex, registry)
            record = apply_decision(ex, "corrected", skills, notes, reviewer)
        problems = validate_review(record, ex, registry)
        if problems:
            print("  !! invalid review, not saved:", problems)
            continue
        save_review(out_path, record)
        print(f"  saved {record['decision']} for {ex['example_id']}")
    print(f"\nDone. {len(load_reviews(out_path))} examples reviewed total.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Review pilot descriptions.")
    ap.add_argument("--reviewer", required=True, help="reviewer name")
    ap.add_argument("--output", default=str(REVIEWS))
    ap.add_argument("--batch", default=None,
                    help="JSON file with decisions for non-interactive use")
    args = ap.parse_args()
    pilot = load_pilot()
    registry = load_registry()
    out_path = Path(args.output)
    if args.batch:
        decisions = json.loads(Path(args.batch).read_text(encoding="utf-8"))
        by_id = {ex["example_id"]: ex for ex in pilot}
        for d in decisions:
            ex = by_id[d["example_id"]]
            record = apply_decision(ex, d["decision"], d.get("skills", []),
                                    d.get("notes", ""), args.reviewer)
            problems = validate_review(record, ex, registry)
            if problems:
                raise SystemExit(f"invalid batch decision for {ex['example_id']}: {problems}")
            save_review(out_path, record)
            print(f"saved {record['decision']} for {ex['example_id']}")
    else:
        review_interactive(pilot, load_reviews(out_path), args.reviewer, out_path)


if __name__ == "__main__":
    main()
