# THE UNMAPPED — Project Card

**Track:** Social Upliftment (PS-02) · **Event:** MEDHA Hackathon
**Status:** Phase 1 — foundation, dataset audit & technical planning (no implementation yet)

## The problem

Divya is 23, from Hoshiarpur, Punjab. Class 12, no college, two years running accounts for her father's textile business, self-taught Excel, Tally, and Python from YouTube. She applies for "Accounts Executive" roles and is rejected — no formal credential. To resume parsers she doesn't exist. She is not noise; the system just can't read her.

## What we are building

A career-skill intelligence system for the Indian labour market:

- **Component A — Skills Signal Engine:** converts informal work descriptions into structured skill profiles grounded in a real occupational dataset (820 Indian-context role profiles, 241-skill controlled vocabulary).
- **Component B — Transition Recommender:** given a skill profile + target occupation, returns skill gaps, a prioritized retraining pathway, and a *calibrated* 12-month feasibility probability (not a label).
- **Component C — Aggregate Signals Dashboard:** optional; two genuine pre-packaged signals (salary distributions, demand trends by domain).

## Tech

React + TypeScript + Vite + Tailwind frontend · FastAPI + Python engine (pandas, scikit-learn TF-IDF) · pytest/vitest · no database, no LLM API, no vector DB (see `docs/phase-1-architecture.md`).

---

## Falsifiable claim (pre-registered before implementation)

> **We hypothesize that taxonomy-grounded skill extraction from informal work descriptions will achieve higher skill-mapping F1 than a keyword-matching baseline on a held-out test set.**
>
> - **Intervention:** alias-expanded gazetteer + TF-IDF cosine matching against the 241-skill registry and occupation texts, with confidence gating.
> - **Control:** case-insensitive exact/lemma substring match of skill labels (no aliases, no TF-IDF, no gating).
> - **Metric:** micro-averaged F1 over the 241-skill multi-label task.
> - **Threshold (PROPOSED, pending pilot):** micro-F1 **≥ 0.50** **and** margin **≥ +0.10** absolute over the baseline, on a locked, team-labeled held-out set (n≈30–36 descriptions, stratified by domain, checksummed, never used in development).
> - **Mechanism:** alias expansion recovers paraphrased informal phrasing ("ran the accounts" → *Financial Accounting*); TF-IDF downweights ubiquitous generic skills (*Communication* appears in 48% of occupations) that inflate baseline false positives.
> - **Rejection:** the claim is **rejected** if micro-F1 < 0.50 (final pilot-adjusted value) **or** the margin over baseline < +0.10. A rejection will be reported here with a diagnosis — a falsified claim honestly reported.

**Calibration claim (Component B):** the 12-month feasibility probability will achieve **ECE ≤ 0.10** (proposed) on held-out rubric-labeled transition pairs, with a published reliability diagram. Probabilities are calibrated against documented proxy labels, *not* observed labour-market outcomes, and the UI will say so.

Full methodology: `docs/phase-1-evaluation-plan.md`. Dataset findings: `docs/phase-1-dataset-audit.md`.

## Experiment log

| Date | Event | Result |
|---|---|---|
| 2026-10-10 | Phase 1 complete: dataset audited, architecture & evaluation plan written, claim pre-registered | No experimental outcomes yet |
| 2026-10-10 | Phase 2 complete: registry (241 canonical skills, 8,200 occupation relations, 6 aliases, 41 review pairs), 30-description pilot (all pending review), keyword baseline, 28/28 tests passing | Provisional baseline micro-F1 0.140 on unreviewed pilot labels — pilot signal only, NOT the claim test; claim thresholds unchanged |
| 2026-10-10 | Phase 3 complete: TF-IDF Skills Signal Engine (`engine/extract.py`, char 3–5gram + maxpool occupation context, phrase floor, confidence gates, abstention, ambiguity flagging), config comparison on evidence, evaluation harness (refuses without reviewed labels), 53/53 tests passing | Provisional TF-IDF micro-F1 0.333 vs baseline 0.140 on unreviewed labels — engineering diagnostics only, NOT the claim test; claim thresholds unchanged; 0 reviewed labels so hypothesis remains untested |
| 2026-10-10 | Phase 4 complete: human-review workflow (`review_pilot.py`, `review_pairs.py`, `apply_registry_patch.py` — decisions separate, IDs never deleted), evaluation integrity (harness reads human reviews only, locked held-out generator with leakage prevention), Transition Recommender (`engine/recommender.py` — gaps, explained pathway, heuristic score, no invented data), calibration investigation (`engine/calibration.py` — proxy rubric, honest infeasibility exposed), 92/92 tests passing | 0/30 descriptions and 0/41 pairs reviewed — human review NOT complete; no valid baseline-vs-TFIDF comparison possible; claim thresholds unchanged; 12-month probability not feasible (no outcome labels) |
| 2026-10-10 | Phase 5 complete: full-stack app — FastAPI thin layer (`api/`, 7 endpoints) + React/TS/Vite/Tailwind frontend (`web/`, 5 pages: landing, skill discovery, analysis results, career transition, labour-market dashboard with Recharts); `netlify.toml` + backend hosting docs + README; 102/102 pytest passing; production build clean; live Playwright E2E 18/18 PASS | Not deployed or publicly accessible; 0/30 reviewed so claim untested; first extraction request ~60 s (model build); no accuracy/probability claims in UI |
| 2026-10-10 | Phase 6 complete: hardened human-review workflow — append-only versioned records (`--amend`, duplicate refusal, full history), CSV/JSON export + CSV/JSON import (atomic, validated), per-reviewer label sets (multi-reviewer requires explicit `--reviewer`), `scripts/review_report.py` (validation, counts, agreement, honest INCOMPLETE status), ANNOTATION_GUIDE rewritten to the implemented workflow; 119/119 pytest passing; frontend build clean | Genuine reviews: 0/30 — human review NOT started; claim untested; next step is a human running `scripts/review_pilot.py --reviewer "<name>"` |
| — | Pilot labeling (n=30) | *pending* |
| — | Held-out claim run | *pending* |
