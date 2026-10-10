# Phase 1 — Evaluation Plan

**Project:** THE UNMAPPED (MEDHA Hackathon, PS-02)
**Date:** 2026-10-10
**Status:** DRAFT — thresholds are *proposed*, pending the pilot labeling round. No experimental outcomes exist yet; nothing below is presented as an observed result.

---

## 1. What is being evaluated (and why this design)

The dataset contains **no informal-text → skill labels** and **no observed transition outcomes** (audit L3, L4). Therefore both evaluations require team-constructed labeled sets. The plan is designed so that:

- the **claim test** (extraction F1) is fully pre-registered before any model tuning,
- the **calibration test** measures honesty of probabilities, not just ranking quality,
- every threshold below is marked **PROPOSED** until the pilot justifies or revises it.

---

## 2. Claim experiment — skill extraction F1

### 2.1 Intervention vs control

- **Intervention:** taxonomy-grounded extraction = alias-expanded gazetteer ∪ TF-IDF cosine against the 241-skill registry and occupation `chunk_text`s, with confidence gating (τ_low / τ_high) as specified in `phase-1-architecture.md` §2.
- **Control (keyword baseline):** case-insensitive exact/lemma substring match of each of the 241 skill labels (no aliases, no TF-IDF, no gating) against the input text. Deterministic, no tunable parameters.

### 2.2 Metric

- **Primary:** micro-averaged F1 over the 241-skill multi-label task on the locked held-out set.
- **Secondary:** macro-averaged F1 (penalizes ignoring rare skills), and per-skill precision/recall for the 20 most frequent skills.

### 2.3 Proposed threshold (NOT an observed result)

> **PROPOSED:** intervention achieves **micro-F1 ≥ 0.50** **and** a margin of **≥ +0.10 absolute over the keyword baseline** on the held-out set.

**Justification for proposing (not proving) this threshold:**
- The label space is coarse (241 labels) but the gold labels are templated (~41 distinct occupation skill sets), so a well-built extractor should substantially beat naive substring matching, which cannot handle paraphrase ("ran the accounts" → `Financial Accounting`) and is swamped by generic skills (`Communication` in 48% of occupations).
- The +0.10 margin requirement ensures the win is practically meaningful, not noise on a small set.
- **The absolute 0.50 figure is provisional.** A pilot round (n=30 descriptions) will establish the baseline's actual level; if the baseline lands far from expectations, the absolute threshold will be revised *before* the held-out set is locked, and the revision recorded here. The margin requirement (≥ +0.10) is the stable part of the claim.

### 2.4 Held-out methodology

1. **Corpus construction:** team writes 100–120 informal work descriptions (40–120 words each) in the voice of personas like Divya — informal jobs, family-business work, self-taught skills. Stratified across ≥10 domains; no description may copy `chunk_text` phrasing verbatim.
2. **Labeling:** two independent annotators label each description against the 241-skill registry (multi-label). Disagreements adjudicated by a third pass. Report Cohen's κ on a 10% overlap sample; proceed only if κ ≥ 0.60, else revise the annotation guide.
3. **Locking:** split 70/30 stratified by domain → dev set / held-out set. The held-out set is checksummed and **never inspected during development** (no error analysis on it until the final run).
4. **Execution:** `tests/test_evaluate.py` runs intervention and baseline on the held-out set exactly once for the official result; reruns are permitted only to verify reproducibility, not to tune.
5. **Rejection conditions:** the hypothesis is **rejected** if micro-F1 < 0.50 (post-pilot final value) **or** margin over baseline < +0.10. A rejection is reported as-is in `card.md` — a falsified claim with a diagnosis still earns the card's credibility; a hidden one earns nothing.

### 2.5 Expected mechanism (why the intervention should win)

1. **Alias expansion** recovers paraphrased informal phrasing the baseline misses ("did accounts" → `Financial Accounting`; "taught village kids" → `Teaching`/`Mentoring`).
2. **TF-IDF downweighting** discounts ubiquitous generic skills that inflate baseline false positives.
3. **Occupation-text channel** (`chunk_text` cosine) provides evidence for skills implied by context but not named literally.

---

## 3. Calibration evaluation — the 12-month probability

The problem statement scores calibration explicitly: constant "high match" outputs score 0; a system saying "0.62" that is right 62% of the time scores well. Our plan:

### 3.1 Labels (proxy outcomes — honesty first)

- Construct 150–200 (profile, target-occupation) pairs from the pilot-labeled profiles × plausible targets.
- Each pair labeled **achievable-in-12-months: yes/no** by rubric: skill overlap ≥ 60% AND education requirement met AND (demand ∈ {High Growth, Very High Growth, Emerging} OR skill gap ≤ 3). The rubric is documented, versioned, and **disclosed in the UI** as the calibration basis.
- Split 70/30; fit the logistic model on the train split only.

### 3.2 Metrics

- **Expected Calibration Error (ECE)** with 10 bins on the held-out split. **PROPOSED bar:** ECE ≤ 0.10.
- **Reliability diagram** (predicted vs observed rate per bin) shipped in the demo for judges to inspect.
- **Brier score** reported alongside; compared against a constant base-rate predictor (must beat it).
- **Sharpness check:** probabilities must actually spread across [0,1] — a model outputting 0.5±0.05 everywhere fails even with good ECE (resolution component reported).

### 3.3 What the UI may and may not say

- MAY: "Estimated 0.62 probability of achieving this transition within 12 months — calibrated on 60 labeled examples (ECE 0.08). Labels follow our documented rubric; these are not observed labour-market outcomes."
- MAY NOT: bare percentages, "high match" labels, or any presentation implying statistical reliability beyond what the held-out ECE supports.

---

## 4. Acceptance criteria

### Component A — Skills Signal Engine
- [ ] AC-A1: Given an informal work description (10–5,000 chars, English), returns a structured profile with ≥1 skill candidate for typical inputs.
- [ ] AC-A2: Every returned skill resolves to a registry ID from the 241-skill vocabulary (closed world; no free-text skill labels).
- [ ] AC-A3: Every skill candidate carries evidence: the verbatim input span and the matching channel (gazetteer / TF-IDF / occupation-text).
- [ ] AC-A4: Inputs with no matchable content return an explicit `unmapped_phrases` list and zero fabricated skills (tested with adversarial inputs: emojis, non-English text, empty string → `EMPTY_INPUT`, 5,001 chars → `TEXT_TOO_LONG`).
- [ ] AC-A5: Low-confidence matches (τ_low ≤ score < τ_high) are flagged "uncertain", never presented as certain.
- [ ] AC-A6: Claim experiment (§2) executed on the locked held-out set with results recorded in `card.md`, pass or fail.

### Component B — Transition Recommender
- [ ] AC-B1: Accepts a structured profile + valid target occupation id; returns matched skills, missing skills, and an ordered pathway. Unknown occupation id → `UNKNOWN_OCCUPATION` (flat envelope), never a 500.
- [ ] AC-B2: Missing skills are explained (which target requirement each satisfies) and pathway steps are actionable (named skill + why + next action from dataset fields).
- [ ] AC-B3: Response contains **both** a heuristic rank score (labeled as heuristic) **and** a calibrated probability (labeled with its calibration basis) — never a single ambiguous "match %".
- [ ] AC-B4: Calibration evaluated on held-out proxy labels: ECE ≤ 0.10 (proposed), reliability diagram available, beats base-rate Brier.
- [ ] AC-B5: 12-month feasibility is defined operationally (rubric version recorded) and its proxy nature is disclosed wherever the probability is shown.

### Component C — Aggregate Signals Dashboard (OPTIONAL — deferred)
- Status: **not in MVP scope.** May be built only after A+B acceptance.
- Entry requirement: exactly the two genuine signals from the audit — (1) salary distribution by domain/occupation, (2) demand trend + bright outlook by domain.
- Explicit non-requirements: no automation-exposure chart (no data), no time-series trends (snapshot only), no live APIs.

---

## 6. Phase 2 results (actual, 2026-10-10)

Implementation: `scripts/build_registry.py`, `scripts/build_pilot.py`, `engine/keyword_baseline.py`.
Tests: **28 passed** (`pytest tests/`).

### 6.1 Registry (built from the real dataset)

- **241 canonical skills**, IDs `SKL-001`–`SKL-241`, assigned by sorting normalized labels —
  deterministic and stable across runs (verified byte-identical rebuilds).
- **820 occupations, 8,200 occupation→skill relationships** (10 per occupation), all references validated.
- **6 approved aliases** (1 spelling variant: *Experiment Design* → *Experimental Design*;
  5 informal variants: *tally*, *excel*, *ms excel*, *spreadsheet(s)* → canonical skills),
  each with a documented rationale. Every alias target is a valid registry ID.
- **41 near-duplicate pairs** in `skill_review_queue.csv`, all `open`, all marked
  "DO NOT auto-merge" — awaiting human decision (keep separate / merge / alias).
- **41 domains** summarized (occupation counts, salary, demand trends, top skills).

**Adaptations from Phase 1 (documented):** registry artifacts are CSV, not JSON, for human
auditability; pilot descriptions are 30–45 words (not 40–120) — brevity is realistic for
form inputs and spans remain the evidence unit.

### 6.2 Pilot dataset

- `data/evaluation/pilot_descriptions.jsonl`: **30 examples, 117 skill annotations**,
  spanning **14 domains** (family-business accounting, retail, BPO, admin, godown,
  self-taught Python/web, tutoring, home care, dhaba, electrical, farming, parlour,
  mobile repair, hotel, security, data entry, video editing, GST, pharmacy, school office,
  masonry, carpentry, social media, bank CSP, health volunteer, warehouse, writing, cashier, waiter).
- **All 30 `review_status: pending`, all `"synthetic": true`.** Annotation guide at
  `data/evaluation/ANNOTATION_GUIDE.md`. The pilot is not the final held-out set.

### 6.3 Keyword baseline — provisional measurement (NOT the claim test)

Baseline run over the 30 pilot descriptions against the *unreviewed* synthetic labels:

| Metric | Value |
|---|---|
| micro-precision | 0.750 |
| micro-recall | 0.077 |
| **micro-F1** | **0.140** (tp=9, fp=3, fn=108) |

Read this as a pilot signal only: labels are synthetic and pending review, and the pilot
is not the locked held-out set. What it already shows is the expected mechanism —
high precision when the baseline fires, near-zero recall on paraphrased informal phrasing
("did the accounts", "ran the accounts" never match literally). On these provisional
numbers the **absolute 0.50 bar is the binding constraint** (baseline + 0.10 = 0.24).

Sample (PILOT-001, Divya-like): baseline predicts *Financial Accounting* ← "Tally"
(alias) and *Excel/Spreadsheets* ← "Excel" (alias); it misses *Data Entry*, *Taxation*,
*Record Keeping* — all paraphrased. Evidence spans verified exact on all 12 predictions
across the 30 descriptions.

### 6.4 Remaining steps before final evaluation

1. Human review of the 30 pilot descriptions (guide provided) + Cohen's κ on overlap.
2. Human decisions on the 41 review-queue pairs (may change registry IDs → rebuild + relabel).
3. Finalize the absolute F1 threshold in light of reviewed pilot numbers (margin ≥ +0.10 fixed).
4. Build the 100–120-description held-out set, lock with checksum.
5. Implement the TF-IDF intervention engine (Phase 3+) and run the claim test once.

## 5. Pending decisions (to resolve in Phase 2)

1. Final absolute F1 threshold after the n=30 pilot (margin ≥ +0.10 is fixed).
2. τ_low / τ_high values for confidence gating (tuned on dev set).
3. Matching weights (0.5/0.3/0.2 proposed) — tuned on dev set, frozen before held-out run.
4. Near-duplicate skill merges (`Communication` vs `Business Communication`) — decision affects registry IDs and all labels; must precede pilot labeling.
5. Rubric version for proxy transition labels (v0 drafted in §3.1).
