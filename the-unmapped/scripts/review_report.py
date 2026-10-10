#!/usr/bin/env python3
"""Review status, validation and agreement report (Phase 6).

- Validates every review record against the rubric (validate_review).
- Reports reviewed / pending / invalid counts per decision and per reviewer.
- Computes inter-reviewer agreement on doubly-reviewed examples
  (exact skill-set match rate + mean pairwise Jaccard).
- States honestly whether the 30-case target is met; never counts invalid
  or pending records as reviewed.
- Writes data/evaluation/reports/review_status.json.

Usage:
    .venv/bin/python scripts/review_report.py
    .venv/bin/python scripts/review_report.py --require 30   # exit 2 if unmet
"""
from __future__ import annotations

import argparse
import itertools
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.review_pilot import (load_pilot, load_registry, load_reviews,
                                  review_history, validate_review)

TOOL_VERSION = "review_report.py v0.1.0"
REVIEWS = ROOT / "data" / "evaluation" / "pilot_reviews.jsonl"
REPORTS = ROOT / "data" / "evaluation" / "reports"
TARGET = 30


def _jaccard(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if (a | b) else 1.0


def build_report(reviews_path: Path = REVIEWS) -> dict:
    pilot = load_pilot()
    by_id = {ex["example_id"]: ex for ex in pilot}
    registry = load_registry()
    reviews = load_reviews(reviews_path)

    per_example: dict[str, dict] = {}
    invalid: list[dict] = []
    for ex in pilot:
        recs = {(rev): r for (eid, rev), r in reviews.items() if eid == ex["example_id"]}
        entry: dict = {"example_id": ex["example_id"], "reviewers": {},
                       "status": "pending", "problems": []}
        for rev, r in sorted(recs.items()):
            problems = validate_review(r, ex, registry)
            entry["reviewers"][rev] = {"decision": r["decision"],
                                      "version": r.get("version", 1),
                                      "reviewed_at": r["reviewed_at"],
                                      "valid": not problems,
                                      "problems": problems}
            if problems:
                invalid.append({"example_id": ex["example_id"], "reviewer": rev,
                                "problems": problems})
        if entry["reviewers"]:
            entry["status"] = ("invalid" if any(not v["valid"] for v in entry["reviewers"].values())
                               else "reviewed")
        per_example[ex["example_id"]] = entry

    # counts (valid decisions only)
    decisions = [v["decision"] for e in per_example.values()
                 for v in e["reviewers"].values() if v["valid"]]
    by_reviewer: dict[str, dict] = {}
    for e in per_example.values():
        for rev, v in e["reviewers"].items():
            d = by_reviewer.setdefault(rev, {"approved": 0, "corrected": 0,
                                             "rejected": 0, "invalid": 0})
            d["invalid" if not v["valid"] else v["decision"]] += 1

    # agreement on doubly-reviewed examples (valid records only)
    agreement_examples = []
    for ex_id, e in per_example.items():
        sets = {rev: {s["skill_id"] for s in reviews[(ex_id, rev)]["skills"]}
                for rev, v in e["reviewers"].items() if v["valid"]
                and reviews[(ex_id, rev)]["decision"] in ("approved", "corrected")}
        if len(sets) >= 2:
            pairs = list(itertools.combinations(sorted(sets), 2))
            exact = sum(1 for a, b in pairs if sets[a] == sets[b]) / len(pairs)
            jac = sum(_jaccard(sets[a], sets[b]) for a, b in pairs) / len(pairs)
            agreement_examples.append({"example_id": ex_id,
                                       "reviewers": sorted(sets),
                                       "exact_match_rate": round(exact, 4),
                                       "mean_pairwise_jaccard": round(jac, 4)})

    n_valid = sum(1 for d in decisions if d in ("approved", "corrected"))
    n_pending = sum(1 for e in per_example.values() if e["status"] == "pending")
    report = {
        "tool": TOOL_VERSION,
        "target": TARGET,
        "n_pilot_examples": len(pilot),
        "n_valid_reviews": n_valid,
        "n_pending": n_pending,
        "n_invalid_records": len(invalid),
        "decisions": {d: decisions.count(d) for d in ("approved", "corrected", "rejected")},
        "by_reviewer": by_reviewer,
        "invalid_records": invalid,
        "agreement": {
            "n_doubly_reviewed": len(agreement_examples),
            "examples": agreement_examples,
            "note": ("Cohen's kappa territory: with 2 reviewers and categorical "
                     "skill-set decisions, exact-match rate and mean Jaccard are "
                     "reported; kappa can be derived from the exported records."),
        },
        "evaluation_ready": n_valid >= TARGET and not invalid,
        "status": ("READY: 30 valid reviews" if n_valid >= TARGET and not invalid
                   else f"INCOMPLETE: {n_valid}/{TARGET} valid reviews"
                        + (f"; {len(invalid)} invalid record(s) need correction"
                           if invalid else "")),
        "per_example": per_example,
    }
    return report


def main() -> None:
    ap = argparse.ArgumentParser(description="Review status and validation report.")
    ap.add_argument("--require", type=int, default=None,
                    help="exit 2 unless at least N valid reviews exist")
    ap.add_argument("--output", default=None)
    args = ap.parse_args()
    report = build_report()
    print(f"valid reviews: {report['n_valid_reviews']}/{report['target']}  "
          f"pending: {report['n_pending']}  invalid: {report['n_invalid_records']}")
    for rev, counts in sorted(report["by_reviewer"].items()):
        print(f"  reviewer {rev}: " +
              ", ".join(f"{k}={v}" for k, v in counts.items() if v))
    if report["agreement"]["n_doubly_reviewed"]:
        print(f"  agreement on {report['agreement']['n_doubly_reviewed']} doubly-reviewed examples:")
        for a in report["agreement"]["examples"]:
            print(f"    {a['example_id']}: exact={a['exact_match_rate']} "
                  f"jaccard={a['mean_pairwise_jaccard']}")
    print(report["status"])
    out = Path(args.output) if args.output else REPORTS / "review_status.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"wrote {out}")
    if args.require is not None and report["n_valid_reviews"] < args.require:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
