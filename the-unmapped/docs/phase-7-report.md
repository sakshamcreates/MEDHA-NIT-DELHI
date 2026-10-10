# Phase 7 — Evaluation Closure & Claim Verification (2026-10-10)

## Scope

Product rebrand MEDHA → **ARUNYA** (public-facing product name only; the
competition remains MEDHA), followed by the Phase 7 evaluation-closure audit.
No engine, API-route, threshold, label, or held-out changes.

## Part A — ARUNYA rebrand

### Audit result

`MEDHA` occurred in exactly 4 places, all competition references — kept:
- `docs/phase-1-dataset-audit.md`, `docs/phase-1-architecture.md`,
  `docs/phase-1-evaluation-plan.md`: "THE UNMAPPED (MEDHA Hackathon, PS-02…)"
- `card.md`: "Event: MEDHA Hackathon"

`THE UNMAPPED` (old product name) rebranded to ARUNYA in:
- `web/index.html` — `<title>`, meta description, new `web/public/favicon.svg`
  (forest-green rounded square, ivory "A", restrained amber accent)
- `web/src/App.tsx` — nav brand → ARUNYA
- `web/src/pages/Landing.tsx` — hero now carries the tagline
  "Discover Your Skills. Find Your Path." and "AI-assisted career intelligence"
- `web/src/api.ts`, `api/main.py` (FastAPI title → "ARUNYA API"),
  `api/__init__.py`, `api/schemas.py`, `engine/__init__.py`,
  `netlify.toml`, `requirements.txt` — comments/docstrings
- `README.md` — product-facing rebrand + tagline; keeps
  "Built for the MEDHA Hackathon (PS-02)"; example URLs updated to arunya-*
- `tests/test_e2e.py` — branding assertion updated to "ARUNYA"

Deliberately NOT renamed (technical identifiers / historical records):
- `the-unmapped/` directory and repo identity
- `scripts/make_heldout.py --salt` default `the-unmapped-heldout`
  (changing it would alter split hashes)
- `THE_UNMAPPED_DATA` env var
- `card.md`, `docs/phase-*.md` (historical provenance)
- model name `tfidf-skill-extractor v0.1.0`

### Rebrand verification

- `pytest`: **119/119 passed**
- `npm run build` (production): clean
- `tests/test_e2e.py` against live API + frontend: **18/18 PASS**,
  zero console errors (initial E2E timeouts were environment issues —
  duplicate API processes on :8000, vite proxy `localhost`→`::1` refused,
  CORS origin — resolved by running one API with
  `FRONTEND_ORIGIN=http://127.0.0.1:5173`; no product code changed)

No domain or trademark availability is claimed.

## Part B — Phase 7 evaluation closure

### Workstream 1 — Readiness audit (verified from actual files)

- Review workflow (`scripts/review_pilot.py` v0.2.0, `review_report.py`,
  `ANNOTATION_GUIDE.md`) present and functional; Phase 6 report matches
  implementation.
- Evaluation harness (`scripts/evaluate_extractor.py`) refuses comparison
  with zero reviewed labels (exit 2); held-out locking
  (`scripts/make_heldout.py`) exists but correctly not yet run.
- Preregistered criteria unchanged: micro-F1 ≥ 0.50, ≥ +0.10 over keyword
  baseline.

### Workstream 2 — Review completion (genuine counts only)

Fresh run of `scripts/review_report.py --require 30`:
- **Valid description reviews: 0/30** (30 pending, 0 invalid)
- **Pair decisions: 0/41** (no `pair_decisions` records exist)
- No review records were generated, guessed, or auto-filled.

### Workstream 3 — Evaluation integrity: BLOCKED

Per protocol, held-out locking and the preregistered comparison require
completed genuine reviews. Neither was run; the harness's own refusal
(exit 2 at 0 reviews) was not overridden.

### Workstream 4 — Claim verification

- **Verdict: BLOCKED.** The preregistered claim (micro-F1 ≥ 0.50,
  ≥ +0.10 over the keyword baseline) remains **untested**.
- No baseline-vs-candidate results exist. No accuracy, probability, or
  employment-outcome claims are made. Heuristic recommender scores remain
  explicitly distinguished from calibrated probabilities.

### Workstream 5 — Tests and regression safety

- Full pytest suite: **119/119 passed** (post-rebrand).
- Frontend production build: clean (post-rebrand).
- E2E: **18/18 PASS** (post-rebrand).
- Held-out leakage protections preserved (no held-out exists to leak;
  refusal logic intact).
- No tests weakened: the single test change was the branding assertion
  (`THE UNMAPPED` → `ARUNYA`), a required rebrand fix.
- Engine behavior unchanged: `engine/extract.py`, `engine/recommender.py`,
  `engine/calibration.py` untouched (only a docstring in
  `engine/__init__.py`).

## Remaining blockers and next justified phase

1. **Human review (the single blocker):** a genuine reviewer must complete
   30 description reviews and 41 pair decisions:
   ```
   cd ~/workspace/the-unmapped
   .venv/bin/python scripts/review_pilot.py --reviewer "<name>"
   .venv/bin/python scripts/review_pairs.py --reviewer "<name>"
   ```
2. Then, and only then: `scripts/review_report.py --require 30`,
   `scripts/make_heldout.py` (lock + checksum manifest), and the
   preregistered `scripts/evaluate_extractor.py --reviewer "<name>"`
   comparison against the baseline.
3. No model tuning, no fabricated labels, no public deployment.
