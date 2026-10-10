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
| — | Pilot labeling (n=30) | *pending* |
| — | Held-out claim run | *pending* |
