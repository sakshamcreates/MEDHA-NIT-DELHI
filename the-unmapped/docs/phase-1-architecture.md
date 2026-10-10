# Phase 1 — MVP Architecture

**Project:** THE UNMAPPED (MEDHA Hackathon, PS-02)
**Date:** 2026-10-10
**Scope:** Components A (Skills Signal Engine) + B (Transition Recommender). Component C optional/later.
**Guiding rule:** smallest reliable system that can be built, demoed, and defended in a hackathon. No component exists unless a concrete requirement justifies it.

---

## 1. Architecture decision

```
┌──────────────┐      HTTP/JSON       ┌─────────────────────────┐
│  web/        │  ─────────────────►  │  api/ (FastAPI)         │
│  React+TS+   │  ◄─────────────────  │  ┌───────────────────┐  │
│  Vite+       │                      │  │ engine/ (Python)  │  │
│  Tailwind    │                      │  │ extract → match   │  │
└──────────────┘                      │  │ → recommend       │  │
                                      │  └───────────────────┘  │
                                      │  dataset loaded in      │
                                      │  memory from CSV        │
                                      └─────────────────────────┘
```

**Why a separate FastAPI backend (justified, not default):**
1. The extraction/matching/calibration logic is Python (pandas + scikit-learn TF-IDF) and is also the code under test by pytest — one implementation serves both the API and the evaluation harness.
2. It keeps the 820-row dataset and the skill registry server-side, so the frontend stays a thin client and the matching algorithm isn't duplicated in TypeScript.
3. `/evaluate` endpoints let judges re-run the card.md claim check live.

**Explicitly rejected for the MVP:**
| Rejected | Reason |
|---|---|
| Database (Postgres/SQLite) | 820 rows / 2.3 MB load into memory in milliseconds; zero write requirements |
| LLM API | Cost, latency, offline-demo risk, and non-determinism would undermine the falsifiable claim; rule-based + TF-IDF is sufficient and fully testable |
| Vector database | TF-IDF vectors for 820 documents fit in memory; no ANN index needed |
| O*NET/ESCO ingestion in MVP | No skill-level IDs in the Indian dataset; occupation-level SOC crosswalk is sufficient and already present |
| Auth / user accounts | No requirement; profiles are session-local |

**Dependencies (minimal):** Python: `fastapi`, `uvicorn`, `pandas`, `scikit-learn` (TF-IDF only), `pytest`. Frontend: `react`, `typescript`, `vite`, `tailwindcss`, `recharts` (only when Component C is built), `vitest`.

---

## 2. Data flow

### Component A — Skills Signal Engine
```
free-text description (e.g. Divya: "ran accounts for father's
textile business for 2 years, taught myself Excel, Tally, Python
from YouTube")
        │
        ▼
1. normalize: lowercase, strip, sentence-split          [engine/normalize.py]
        │
        ▼
2. candidate extraction (TWO channels, union):
   a. gazetteer match: alias-expanded skill registry
      ("tally" → Financial Accounting; "excel" → Data Analysis…)
   b. TF-IDF cosine: text vs 241 skill pseudo-documents
      (skill name + alias terms + co-occurring chunk_text windows)
        │
        ▼
3. evidence linking: every candidate keeps {matched_span,
   source_channel, score} — no skill without a pointer back
   to the input text
        │
        ▼
4. confidence gating: score ≥ τ_high → accepted;
   τ_low ≤ score < τ_high → "uncertain, needs review";
   below τ_low → dropped. Unknown phrases → "unmapped"
   bucket, never force-fit to a skill.
        │
        ▼
structured profile: { skills: [{skill_id, label, evidence,
confidence}], unmapped_phrases: [...], occupation_hints: [...] }
```

**Occupation matching** (profile → roles): weighted score =
`0.5 × skill_overlap (Dice on skill sets)` + `0.3 × TF-IDF cosine(text, chunk_text)` + `0.2 × education/segment compatibility`.
The text channel exists because skill sets are templated (~41 distinct sets for 820 occupations — see dataset audit L2); skill overlap alone cannot discriminate within a domain. Weights are tuned on the pilot set in Phase 2, not hardcoded as truth.

### Component B — Transition Recommender
```
structured profile + target_occupation_id
        │
        ▼
1. gap analysis: required_skills(target) − profile.skills
   → matched[], missing[] (each missing skill keeps the
     target-occupation evidence: which role requires it)
        │
        ▼
2. pathway builder: order missing skills by
   priority = (frequency across reachable occupations)
            × (demand weight of target domain)
            × (1 / estimated learning effort from segment_relevance)
   attach per-skill actions from india_qualifying_exams /
   education_required of the target
        │
        ▼
3. scoring — TWO numbers, never conflated:
   a. heuristic rank score (0–1): transparent weighted sum,
      labeled "ranking score, not a probability"
   b. calibrated probability P(achievable in 12 months):
      logistic regression on features
      [skill_overlap, education_met, demand_trend_encoded,
       n_missing, riasec_distance],
      Platt-style fit on labeled transition examples,
      reported WITH reliability curve + ECE on held-out set
```

---

## 3. Module and folder structure

```
the-unmapped/
├── card.md
├── docs/                        # phase-1-*.md, later phase docs
├── data/
│   ├── raw/
│   │   └── indian_skills_dataset.csv      # committed (2.3 MB)
│   └── processed/               # generated by scripts/build_registry.py
│       ├── skill_registry.json  # 241 skills: id, label, aliases, idf stats
│       ├── occupation_index.json # 820 occupations, cleaned fields
│       └── domain_rollup.json   # 41 raw domains → clean rollup
├── scripts/
│   ├── build_registry.py        # CSV → processed artifacts (pandas)
│   └── make_pilot_template.py   # generates blank labeling CSV for eval set
├── engine/                      # pure-Python package, no web deps
│   ├── normalize.py
│   ├── registry.py              # load skill_registry.json
│   ├── extract.py               # Component A extraction
│   ├── match.py                 # profile → occupations
│   ├── recommend.py             # Component B gaps + pathway
│   ├── calibrate.py             # logistic fit, ECE, reliability data
│   └── evaluate.py              # F1 + calibration harness (used by tests & API)
├── api/
│   ├── main.py                  # FastAPI app, loads CSV once at startup
│   ├── schemas.py               # Pydantic models (flat error envelope)
│   └── routes/
│       ├── extract.py           # POST /api/extract
│       ├── recommend.py         # POST /api/recommend
│       └── signals.py           # GET /api/signals/* (Component C, later)
├── web/                         # Vite + React + TS + Tailwind
│   └── src/
│       ├── components/          # ProfileForm, SkillChips, GapView, PathwayList
│       └── lib/api.ts           # typed API client
├── tests/
│   ├── test_extract.py          # pytest: extraction incl. unknown-skill cases
│   ├── test_recommend.py        # pytest: gap logic, envelope shape
│   └── test_evaluate.py         # pytest: runs claim check on held-out set
└── notebooks/
    └── 01_dataset_audit.ipynb   # (optional) audit walkthrough
```

**Error envelope convention** (all API errors, one flat shape):
`{ "success": false, "message": str, "code": str }` — e.g. `UNKNOWN_OCCUPATION`, `EMPTY_INPUT`, `TEXT_TOO_LONG`.

---

## 4. Preprocessing strategy (`scripts/build_registry.py`)

1. Read CSV (utf-8-sig). Validate: 820 rows, 21 columns, 0 duplicate ids — fail loudly otherwise.
2. Parse JSON columns (`required_skills`, `india_salary_percentiles`, `riasec_scores`, arrays). Coerce failures to explicit errors, not silent nulls.
3. Build skill registry: normalize the 241 unique skill strings (strip, collapse whitespace); assign stable IDs `SKL-001`…`SKL-241`; record document frequency for IDF weighting. Flag near-duplicates (`Communication`/`Business Communication`, `Collaboration`/`Team Collaboration`) for a manual alias decision in Phase 2 (merge vs keep — affects F1 labels).
4. Build domain rollup: map 41 raw domains → ~20 clean families (document mapping).
5. Emit `skill_registry.json`, `occupation_index.json`, `domain_rollup.json`. All downstream code reads processed artifacts, never the raw CSV directly.

---

## 5. Taxonomy-mapping strategy

- **Closed-world grounding:** every extracted skill must resolve to one of the 241 registry IDs. Output schema forbids free-text skill labels.
- **Aliases:** hand-curated informal → canonical map seeded from Indian context (`tally`→`Financial Accounting`, `excel`→`Data Analysis`, `stitching`→`Sewing`, …), extended during pilot labeling. Aliases are versioned in `skill_registry.json`.
- **Occupation-level crosswalk:** `onet_soc_code` is preserved on every occupation record, enabling an optional later join to O*NET 31.0 skills/abilities without changing the API.
- **Unknown handling:** phrases matching nothing above τ_low are returned in `unmapped_phrases` with the verbatim span — visible to the user, never silently dropped, never force-fit.

---

## 6. Recommendation-ranking approach

- **Ranking score (heuristic, transparent):** `0.4·skill_overlap + 0.25·education_fit + 0.2·demand_weight + 0.15·riasec_fit`, each term 0–1 with a documented formula. Used only to *order* suggestions. Labeled in UI as "match score (heuristic)".
- **Feasibility probability (calibrated):** logistic regression → P(12-month achievable). Features listed in §2. Trained on rubric-labeled transition examples (see evaluation plan §4); validated with reliability diagram + ECE on a held-out split. The UI shows the probability **with** its calibration note ("calibrated on N labeled examples; proxy labels, not observed outcomes") and never shows it as a percentage without that context.
- **Pathway:** missing skills ordered by priority formula (§2); each step names the skill, why it matters (which target-role requirement it satisfies), and a concrete next action (exam/course/segment-appropriate resource from dataset fields).

---

## 7. Error handling and input validation

- API: Pydantic validation on all inputs (text length 1–5,000 chars; occupation id must exist → `UNKNOWN_OCCUPATION`, never a 500).
- Engine functions return `(result, warnings)` — low-confidence extractions surface as warnings, not silent drops.
- Startup: missing/corrupt CSV or registry → fail fast with a clear message; no partial boot.
- Frontend: empty input, over-long input, and API-unreachable states each have a designed empty/error state; unmapped phrases render as "we couldn't map these — help us improve" rather than an error.

## 8. Testing strategy

- **pytest** (`tests/`): unit tests for normalize/extract/match/recommend; property tests for gap logic (missing ∪ matched = required); envelope-shape tests for every error path; `test_evaluate.py` executes the card.md claim against the locked held-out set and fails CI if the threshold is missed.
- **Frontend:** `vitest` for lib/api + component smoke tests; `tsc` + `vite build` as build gates.
- **Pilot labeling:** double-label a 10% overlap sample; report inter-annotator agreement (Cohen's κ) before locking the held-out set.

## 9. Deployment approach (hackathon)

- **Demo:** `uvicorn api.main:app` + `vite preview` (or `vite build` served statically) on one machine; no cloud dependency during judging.
- **If hosted:** single Render/Railway web service running both (FastAPI serves `web/dist` statically) — one deployable, free tier sufficient.
- **Reproducibility:** `data/raw` committed; `data/processed` rebuildable via one script; held-out eval set stored with a checksum and never used in development.
