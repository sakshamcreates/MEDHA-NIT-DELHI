# Phase 6 — Report: Human Review & Evaluation Validation

**Date:** 2026-10-10 · **Status:** workflow hardened and validated; genuine reviews: **0/30**

---

## 1. Audit findings

**How the 30 cases flow today:** `scripts/build_pilot.py` generated 30 synthetic
descriptions (14 domains) → `pilot_descriptions.jsonl` (all `pending`, immutable) →
`scripts/review_pilot.py` presents description + proposed skill IDs/labels/spans →
decisions recorded in `pilot_reviews.jsonl` → `scripts/evaluate_extractor.py` builds
the label set (refuses at 0) → `scripts/make_heldout.py` locks splits.

**Gaps found (all addressed below unless noted):**

1. `ANNOTATION_GUIDE.md` described direct JSONL editing + `review_status` mutation —
   contradicting the implemented separate-decisions workflow. **Rewritten.**
2. `save_review` silently overwrote prior decisions; batch mode too. No history,
   no duplicate protection. **Fixed: append-only versioned records.**
3. No export for offline/spreadsheet reviewers; import was JSON-only.
   **Added CSV+JSON export, CSV import (approve/reject), JSON batch (full fidelity).**
4. No status/validation/agreement reporting. **Added `scripts/review_report.py`.**
5. Reviewer never saw current model output. **Added opt-in `--with-model`
   (reference only, never labels).**
6. Multi-reviewer agreement contemplated by the guide (kappa) but unsupported;
   silent last-wins would have been dishonest. **Records are per-(example,
   reviewer); evaluation requires naming `--reviewer` when several exist.**
7. Held-out leakage protection, refusal paths, and patch gating already existed
   and remain; covered by tests.

**Not changed:** recommendation engine, extractor, frontend, API (no new
routes/screens — the review workflow needs no account system), preregistered
claim and thresholds.

## 2. Files created / modified

- **Created:** `scripts/review_report.py`, `tests/test_review_ops.py` (19 tests),
  `docs/phase-6-report.md`.
- **Modified:** `scripts/review_pilot.py` (v0.2.0: versioned append-only records,
  `DuplicateReviewError`, `--amend`, atomic batch, `--export-csv/--export-json`,
  `--import-csv`, `--with-model`, per-reviewer keys), `scripts/review_report.py`
  (new), `scripts/evaluate_extractor.py` + `scripts/make_heldout.py`
  (`--reviewer` selection; multi-reviewer without selection refuses),
  `data/evaluation/ANNOTATION_GUIDE.md` (rewritten to the implemented workflow),
  `tests/test_review.py` (updated to the v2 record model).

## 3. Reviewer instructions (summary; full text in ANNOTATION_GUIDE.md)

1. Run `.venv/bin/python scripts/review_pilot.py --reviewer "Your Name"`.
2. For each of the 30 cases: check realism, skill labels, verbatim spans, target
   occupation; then **approve / correct / reject / skip**.
3. Ambiguous near-duplicates: most specific supportable skill; never both per span.
4. Offline option: `--export-csv`, fill `decision`/`notes`, `--import-csv`
   (corrections need `--batch` JSON).
5. Re-decisions need `--amend` (new version; history kept).
6. Check `.venv/bin/python scripts/review_report.py` when done.

## 4. Commands

```bash
# generate/retrieve the 30 cases (deterministic regeneration available)
.venv/bin/python scripts/build_pilot.py          # regenerates pilot_descriptions.jsonl
# interactive review / export / import / amend
.venv/bin/python scripts/review_pilot.py --reviewer "Name"
.venv/bin/python scripts/review_pilot.py --reviewer "Name" --export-csv /tmp/pending.csv
.venv/bin/python scripts/review_pilot.py --reviewer "Name" --import-csv /tmp/decisions.csv
.venv/bin/python scripts/review_pilot.py --reviewer "Name" --batch /tmp/fixes.json --amend
# status, validation, agreement
.venv/bin/python scripts/review_report.py
.venv/bin/python scripts/review_report.py --require 30
# evaluation (only after 30 valid reviews)
.venv/bin/python scripts/make_heldout.py --created-by "Name" --reviewer "Name"
.venv/bin/python scripts/evaluate_extractor.py --manifest data/evaluation/heldout_v1/manifest.json --reviewer "Name"
```

## 5. Tests & results

- New `tests/test_review_ops.py`: 17 tests (versioning, duplicates, amend history,
  batch atomicity, fabricated-label rejection, export/import round trips,
  multi-reviewer guards, report counts/invalid/agreement, honest empty state).
- Updated `tests/test_review.py` (14) and existing `test_eval_integrity.py` (5).
- Full suite: **119 passed** (`pytest tests/ -q`); frontend `npm run build` clean.
- Workflow smoke-tested end-to-end on temp files: export 30 → import 2 →
  report 1/30 INCOMPLETE → duplicate refused → amend → version 2 with history.
  Real `data/evaluation/` untouched (no `pilot_reviews.jsonl` exists).

## 6. Genuine review count

**0 / 30.** No human review has been performed. No labels invented, inferred, or
auto-filled. The planned evaluation is incomplete and the preregistered claim
remains untested.

## 7. Blockers & exact next step

**Blocker:** a human must complete the 30 reviews — this cannot be automated
without violating evaluation integrity.

**Exact next step:** Saksham (or a designated reviewer) runs
`.venv/bin/python scripts/review_pilot.py --reviewer "<name>"` and works through
the 30 cases per `data/evaluation/ANNOTATION_GUIDE.md`. Then:
1. `.venv/bin/python scripts/review_report.py --require 30` (must pass),
2. decide the 41 review-queue pairs (`scripts/review_pairs.py`),
3. lock the held-out set and run the claim comparison.
