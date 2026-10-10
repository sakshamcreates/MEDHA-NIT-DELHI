#!/usr/bin/env python3
"""Human review workflow for the 30 pilot descriptions (Phases 4-6).

- Displays each description with its proposed skill labels, evidence spans,
  and canonical skill IDs (optionally with current model predictions).
- Reviewer may approve / correct / reject / skip each example.
- Decisions are recorded in data/evaluation/pilot_reviews.jsonl, SEPARATE from
  the original synthetic annotations (pilot_descriptions.jsonl is never mutated).
- Append-only versioned records: re-deciding an example requires --amend and
  creates a new version; history is never lost. Accidental overwrites are refused.
- Unreviewed examples stay "pending". Nothing is auto-marked as ground truth.

Usage:
    .venv/bin/python scripts/review_pilot.py --reviewer "Your Name"
    .venv/bin/python scripts/review_pilot.py --reviewer "x" --with-model
    .venv/bin/python scripts/review_pilot.py --reviewer "x" --batch decisions.json
    .venv/bin/python scripts/review_pilot.py --reviewer "x" --batch fixes.json --amend
    .venv/bin/python scripts/review_pilot.py --export-csv /tmp/pending.csv
    .venv/bin/python scripts/review_pilot.py --export-json /tmp/pending.json
    .venv/bin/python scripts/review_pilot.py --reviewer "x" --import-csv decisions.csv
    .venv/bin/python scripts/review_report.py        # status, validation, agreement
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

TOOL_VERSION = "review_pilot.py v0.2.0"
PILOT = ROOT / "data" / "evaluation" / "pilot_descriptions.jsonl"
REVIEWS = ROOT / "data" / "evaluation" / "pilot_reviews.jsonl"
REGISTRY = ROOT / "data" / "processed" / "skill_registry.csv"

DECISIONS = ("approved", "corrected", "rejected")


class DuplicateReviewError(Exception):
    """Raised when a decision already exists and --amend was not given."""


def utcnow() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_pilot() -> list[dict]:
    with PILOT.open(encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def load_registry() -> dict[str, str]:
    with REGISTRY.open(encoding="utf-8") as f:
        return {r["label"]: r["skill_id"] for r in csv.DictReader(f)}


def load_registry_by_id() -> dict[str, str]:
    with REGISTRY.open(encoding="utf-8") as f:
        return {r["skill_id"]: r["label"] for r in csv.DictReader(f)}


def load_reviews(path: Path) -> dict[tuple[str, str], dict]:
    """Latest record per (example_id, reviewer). Append-only log underneath."""
    out: dict[tuple[str, str], dict] = {}
    if not path.exists():
        return out
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                r = json.loads(line)
                out[(r["example_id"], r["reviewer"])] = r
    return out


def review_history(path: Path, example_id: str,
                   reviewer: str | None = None) -> list[dict]:
    """All versions for an example (oldest first); optionally one reviewer."""
    out = []
    if not path.exists():
        return out
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if r["example_id"] == example_id and (reviewer is None or r["reviewer"] == reviewer):
                out.append(r)
    return out


def save_review(path: Path, record: dict, allow_overwrite: bool = False) -> dict:
    """Append a versioned record. Refuses to silently overwrite.

    Returns the stored record (with version assigned). Raises
    DuplicateReviewError when a decision already exists for this
    (example_id, reviewer) and allow_overwrite is False.
    """
    key = (record["example_id"], record["reviewer"])
    existing = load_reviews(path).get(key)
    if existing is not None and not allow_overwrite:
        raise DuplicateReviewError(
            f"{record['example_id']} already decided by {record['reviewer']} "
            f"(version {existing.get('version', 1)}); re-run with --amend to "
            f"record a correction as a new version")
    record = dict(record)
    record["version"] = (existing.get("version", 0) + 1) if existing else 1
    record["supersedes"] = existing.get("version") if existing else None
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


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


def reviewed_label_set(pilot: list[dict], reviews: dict[tuple[str, str], dict],
                       reviewer: str | None = None) -> dict[str, list[dict]]:
    """example_id -> reviewed skill list. Excludes rejected/pending.

    With several reviewers in the log, `reviewer` must name whose decisions to
    use; otherwise a ValueError is raised (no silent adjudication).
    """
    reviewers = sorted({rev for (_, rev) in reviews})
    if reviewer is None:
        if len(reviewers) > 1:
            raise ValueError(
                f"reviews by {reviewers} present; specify reviewer= to select "
                f"whose decisions form the label set")
        reviewer = reviewers[0] if reviewers else None
    out = {}
    for ex in pilot:
        r = reviews.get((ex["example_id"], reviewer)) if reviewer else None
        if r and r["decision"] in ("approved", "corrected"):
            out[ex["example_id"]] = r["skills"]
    return out


def reviewers_in(path: Path) -> list[str]:
    return sorted({rev for (_, rev) in load_reviews(path)})


# ---------------------------------------------------------------------------
# export / import
# ---------------------------------------------------------------------------

def export_cases(pilot: list[dict], reviews: dict[tuple[str, str], dict],
                 path: Path, fmt: str, pending_only: bool = True) -> int:
    """Write review cases for offline work. Returns number exported."""
    reviewed_ids = {ex_id for (ex_id, _) in reviews}
    cases = []
    for ex in pilot:
        if pending_only and ex["example_id"] in reviewed_ids:
            continue
        cases.append({
            "example_id": ex["example_id"],
            "description": ex["description"],
            "target_occupation_id": ex["target_occupation_id"],
            "target_occupation_title": ex["target_occupation_title"],
            "proposed_skills": [
                {"skill_id": s["skill_id"], "skill_label": s["skill_label"],
                 "evidence_span": s["evidence_span"]}
                for s in ex["expected_skills"]],
            "status": "reviewed" if ex["example_id"] in reviewed_ids else "pending",
        })
    path.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "json":
        path.write_text(json.dumps(cases, indent=2, ensure_ascii=False), encoding="utf-8")
    else:
        with path.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(["example_id", "description", "target_occupation_title",
                        "proposed_skill_ids", "proposed_skill_labels", "status",
                        "decision", "notes"])
            for c in cases:
                w.writerow([c["example_id"], c["description"],
                            c["target_occupation_title"],
                            "|".join(s["skill_id"] for s in c["proposed_skills"]),
                            "|".join(s["skill_label"] for s in c["proposed_skills"]),
                            c["status"], "", ""])
    return len(cases)


def import_csv_decisions(csv_path: Path, pilot: list[dict], reviewer: str,
                         registry_by_id: dict[str, str]) -> list[dict]:
    """Build review records from a filled export CSV.

    CSV import supports approve/reject decisions (skill-level corrections need
    the JSON --batch format, which carries evidence spans). Every row is
    validated; problems raise ValueError before anything is written.
    """
    by_id = {ex["example_id"]: ex for ex in pilot}
    records = []
    with csv_path.open(encoding="utf-8", newline="") as f:
        for i, row in enumerate(csv.DictReader(f), start=2):
            ex_id = (row.get("example_id") or "").strip()
            decision = (row.get("decision") or "").strip().lower()
            notes = (row.get("notes") or "").strip()
            if ex_id not in by_id:
                raise ValueError(f"row {i}: unknown example_id {ex_id!r}")
            if decision not in ("approved", "rejected"):
                raise ValueError(
                    f"row {i} ({ex_id}): decision must be 'approved' or 'rejected' "
                    f"in CSV import (use JSON --batch for 'corrected'); got {decision!r}")
            if not decision:
                continue  # blank decision = not reviewed in this file
            records.append(apply_decision(by_id[ex_id], decision, [], notes, reviewer))
    # validate everything before returning (caller writes atomically)
    registry = {v: k for k, v in registry_by_id.items()}
    for rec in records:
        problems = validate_review(rec, by_id[rec["example_id"]], registry)
        if problems:
            raise ValueError(f"{rec['example_id']}: {problems}")
    return records


# ---------------------------------------------------------------------------
# interactive CLI
# ---------------------------------------------------------------------------

def _show_example(ex: dict, idx: int, total: int,
                  model_preds: list[dict] | None = None) -> None:
    print(f"\n{'='*70}\n[{idx}/{total}] {ex['example_id']} "
          f"(target: {ex['target_occupation_title']})")
    print(f"TEXT: {ex['description']}\nProposed skills:")
    for i, s in enumerate(ex["expected_skills"], 1):
        print(f"  {i}. {s['skill_id']} {s['skill_label']}\n"
              f"     evidence: {s['evidence_span']!r}")
    if model_preds is not None:
        print("Current model output (reference ONLY — not ground truth):")
        for p in model_preds[:10]:
            print(f"  - {p['skill_id']} {p['label']} "
                  f"score={p['score']:.3f} conf={p['confidence']} via {p['method']}")


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


def _model_predictions(text: str) -> list[dict]:
    from engine.extract import extract_skills
    return extract_skills(text, top_k=10)["skills"]


def review_interactive(pilot: list[dict], reviews: dict[tuple[str, str], dict],
                       reviewer: str, out_path: Path, with_model: bool) -> None:
    registry = load_registry()
    pending = [ex for ex in pilot if (ex["example_id"], reviewer) not in reviews]
    print(f"{len(pending)} of {len(pilot)} examples pending review for {reviewer}.")
    if with_model:
        print("Loading extraction model for reference predictions (one-time ~60 s)…")
    for i, ex in enumerate(pending, 1):
        preds = _model_predictions(ex["description"]) if with_model else None
        _show_example(ex, i, len(pending), preds)
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
    print(f"\nDone. {len(load_reviews(out_path))} decisions recorded total.")


def apply_batch(pilot: list[dict], decisions: list[dict], reviewer: str,
                out_path: Path, amend: bool = False) -> list[dict]:
    """Validate ALL decisions first, then write. Atomic: any invalid decision
    aborts the whole batch with nothing written. Duplicate (example_id,
    reviewer) decisions require amend=True."""
    by_id = {ex["example_id"]: ex for ex in pilot}
    registry = load_registry()
    records = []
    for d in decisions:
        if d["example_id"] not in by_id:
            raise ValueError(f"unknown example_id: {d['example_id']} -- nothing was written")
        ex = by_id[d["example_id"]]
        record = apply_decision(ex, d["decision"], d.get("skills", []),
                                d.get("notes", ""), reviewer)
        problems = validate_review(record, ex, registry)
        if problems:
            raise ValueError(
                f"invalid batch decision for {ex['example_id']}: {problems} "
                f"-- nothing was written")
        records.append(record)
    stored_records = []
    for rec in records:
        stored_records.append(save_review(out_path, rec, allow_overwrite=amend))
    return stored_records


def _write_batch(out_path: Path, records: list[dict], amend: bool) -> None:
    for rec in records:
        save_review(out_path, rec, allow_overwrite=amend)
        print(f"saved {rec['decision']} for {rec['example_id']}"
              f" (by {rec['reviewer']})")


def main() -> None:
    ap = argparse.ArgumentParser(description="Review pilot descriptions.")
    ap.add_argument("--reviewer", required=True, help="reviewer name")
    ap.add_argument("--output", default=str(REVIEWS))
    ap.add_argument("--batch", default=None,
                    help="JSON file with decisions for non-interactive use")
    ap.add_argument("--amend", action="store_true",
                    help="allow re-deciding already-reviewed examples (new version)")
    ap.add_argument("--with-model", action="store_true",
                    help="show current extractor predictions for reference")
    ap.add_argument("--export-csv", default=None, metavar="PATH")
    ap.add_argument("--export-json", default=None, metavar="PATH")
    ap.add_argument("--import-csv", default=None, metavar="PATH",
                    help="import approve/reject decisions from a filled export CSV")
    ap.add_argument("--pending-only", action="store_true", default=True)
    ap.add_argument("--all", dest="pending_only", action="store_false",
                    help="export all cases, not just pending")
    args = ap.parse_args()
    pilot = load_pilot()
    registry = load_registry()
    registry_by_id = load_registry_by_id()
    out_path = Path(args.output)

    if args.export_csv or args.export_json:
        reviews = load_reviews(out_path)
        if args.export_csv:
            n = export_cases(pilot, reviews, Path(args.export_csv), "csv",
                             args.pending_only)
            print(f"exported {n} cases to {args.export_csv}")
        if args.export_json:
            n = export_cases(pilot, reviews, Path(args.export_json), "json",
                             args.pending_only)
            print(f"exported {n} cases to {args.export_json}")
        return

    if args.import_csv:
        records = import_csv_decisions(Path(args.import_csv), pilot,
                                       args.reviewer, registry_by_id)
        try:
            _write_batch(out_path, records, args.amend)
        except DuplicateReviewError as e:
            raise SystemExit(f"REFUSED: {e} -- nothing was overwritten") from e
        return

    if args.batch:
        decisions = json.loads(Path(args.batch).read_text(encoding="utf-8"))
        try:
            records = apply_batch(pilot, decisions, args.reviewer, out_path, args.amend)
        except (ValueError, DuplicateReviewError) as e:
            raise SystemExit(str(e)) from e
        for rec in records:
            print(f"saved {rec['decision']} for {rec['example_id']} (by {rec['reviewer']})")
    else:
        review_interactive(pilot, load_reviews(out_path), args.reviewer, out_path,
                           args.with_model)


if __name__ == "__main__":
    main()
