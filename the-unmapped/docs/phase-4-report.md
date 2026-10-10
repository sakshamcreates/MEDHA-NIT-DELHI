# Phase 4 — Report: Review Workflow, Evaluation Integrity & Transition Recommender

**Date:** 2026-10-10 · **Status:** workflow + recommender implemented and tested; human review NOT done; no valid claim comparison yet

---

## Part A — Human-review workflow (built, 0 reviews recorded)

| Tool | Purpose | Decisions file |
|---|---|---|
| `scripts/review_pilot.py` | Interactive CLI over the 30 pilot descriptions: shows text, proposed skill IDs/labels/spans, target occupation; approve / correct / reject / skip | `data/evaluation/pilot_reviews.jsonl` |
| `scripts/review_pairs.py` | Interactive CLI over the 41 near-duplicate pairs: shows both skills' occupation counts and shared tokens; default KEEP SEPARATE; merge/alias only on explicit approval | `data/evaluation/pair_reviews.jsonl` |
| `scripts/apply_registry_patch.py` | Applies approved merge/alias decisions: append-only alias rows + `skill_deprecations.csv`; IDs never deleted; dry-run by default; idempotent | `data/processed/skill_aliases.csv` (append), `skill_deprecations.csv` (new) |

**Integrity rules enforced and tested:** decisions live separately from
`pilot_descriptions.jsonl` (never mutated; all 30 still `pending`); spans must be
verbatim substrings; skill IDs must exist in the registry; pair decisions require a
rationale; merges preserve both IDs with provenance.

**Actual reviewed counts: 0 / 30 descriptions, 0 / 41 pairs.** No claim of completed
human review is made. Batch mode (`--batch`) verified end-to-end in tests.

## Part B — Evaluation integrity

- `scripts/evaluate_extractor.py` now sources labels **only** from `pilot_reviews.jsonl`
  (approved/corrected). With 0 reviews it **refuses** (exit 2) — verified.
- `--diagnostics` remains for engineering smoke tests, clearly labeled non-claim.
- `scripts/make_heldout.py` locks versioned dev/test splits (deterministic
  md5(salt:id) ordering, disjoint by construction, manifest with data/registry/
  reviews checksums). Refuses below `--min-reviewed` and refuses to overwrite an
  existing version. **Not run yet** — generating the locked set before annotation
  criteria are final would violate the protocol.
- `evaluate_extractor.py --manifest <manifest.json> --split test` evaluates only the
  locked split and warns on checksum drift (leakage/version detection).
- Claim and thresholds in `card.md` unchanged.

## Part C — Transition Recommender (`engine/recommender.py`)

**Methodology (explainable, no invented data):**
- Inputs: profile skill IDs (validated, deduped; unknown IDs warned and excluded) +
  target occupation ID (must exist) + optional profile education.
- Gap analysis: matched/missing partition the occupation's required skills.
- Heuristic rank score = 0.55·Dice overlap + 0.25·education fit + 0.20·occupational-context
  fit (TF-IDF cosine of profile skill labels vs role chunk_text), renormalized over
  available components. Explicitly labeled heuristic, never a probability.
- Pathway: missing skills ordered by priority = 0.5·transferability (share of domain
  occupations requiring the skill) + 0.3·demand weight + 0.2·learnability; each step
  explains *why* and lists next steps tagged `dataset` (qualifying exams) vs
  `heuristic_suggestion` (generic, never invented course names).
- Data-quality warnings: templated skill sets (e.g. Accountants and Auditors shares its
  set with 49 others — overlap alone cannot distinguish them), missing context, etc.

**Representative output** (Divya-like profile → Accountants and Auditors, 12th Pass):
heuristic 0.2024; 1/10 matched (Excel/Spreadsheets); missing 9 incl. Accounting,
Compliance, Financial Analysis; pathway top items Data Interpretation / Accounting /
Compliance (priority 0.8182, transferability-driven); education fit 0.33
(Bachelor's required); `twelve_month_feasibility.available: false` with reason.

## Part D — Twelve-month feasibility and calibration

**Investigation conclusion: honest calibration is not feasible with current data.**
No observed transition outcomes exist. The recommender therefore returns
`twelve_month_feasibility.available: false` with the reason and what would be needed —
no heuristic score is presented as a probability anywhere.

`engine/calibration.py` provides the reusable scaffold: versioned proxy rubric
(`proxy-rubric-v0`, deterministic, disclosed), logistic calibrator, ECE / Brier /
reliability-table metrics. A mechanical study (300 synthetic profiles, proxy labels)
yields ECE 0.096 and Brier 0.038 vs base-rate 0.117 — demonstrating the *mechanics*
calibrate to the rubric, explicitly **not** real-world calibration. Do not surface
proxy-calibrated numbers to users.

## Tests

New: `test_review.py` (14), `test_eval_integrity.py` (5), `test_recommender.py` (13),
`test_calibration.py` (7) — covering invalid/unknown/duplicate/empty inputs,
determinism, explanation consistency, score/probability separation, review-status
integrity, split disjointness/determinism/leakage, ECE/Brier correctness, and the
refusal paths. Full suite: **92 passed**.

## Limitations

1. 0 human reviews → no valid baseline-vs-TFIDF comparison; claim untested.
2. Recommender context fit needs the extractor (60 s build); without it the warning fires.
3. Pathway priority is heuristic (transferability/demand/learnability weights untuned).
4. Proxy calibration is mechanical only; real calibration needs real outcome labels.
5. English-only input; generic-skill dominance only partially mitigated.

## Next steps before submission-ready

1. Human review of 30 pilot descriptions + 41 pairs (tools ready).
2. Re-tune extractor gates on reviewed labels; finalize the 0.50 absolute threshold.
3. Lock held-out set (`make_heldout.py`), run the claim comparison.
4. Build Component B UI + Component C dashboard (2 genuine signals); frontend.
