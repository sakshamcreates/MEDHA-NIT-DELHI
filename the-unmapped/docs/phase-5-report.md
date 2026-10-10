# Phase 5 — Report: Full-Stack Web Application

**Date:** 2026-10-10 · **Status:** implemented, integrated, tested; NOT deployed

---

## Technologies

- **Backend:** FastAPI 0.143 + uvicorn, Python 3.12 (`api/`). Thin layer over
  `engine/extract.py`, `engine/recommender.py`, and the dataset — no logic duplicated.
- **Frontend:** React 19 + TypeScript + Vite 8 + Tailwind CSS v4 + React Router 7 +
  Recharts 3 (`web/`). Dashboard code-split via `React.lazy` (284 kB initial,
  375 kB dashboard chunk).

## API endpoints (`api/main.py`)

| Endpoint | Notes |
|---|---|
| `GET /api/health` | Fast; reports `model_loaded`, 0 reviewed labels, evaluation note |
| `GET /api/occupations` | 820 records; `?domain=` / `?q=` filters |
| `GET /api/occupations/{id}` | Detail incl. salary, exams, demand; 404 on unknown |
| `GET /api/skills` | 241 canonical skills |
| `POST /api/skills/extract` | Validated `{text≤5000, top_k≤50}`; 400 on empty, 422 on bad shape |
| `POST /api/career/recommend` | 400 on unknown occupation/education; unknown skill IDs warned+excluded |
| `GET /api/market/signals` | Salary-by-domain (median/IQR of occupation medians) + demand counts by domain |

CORS restricted to `FRONTEND_ORIGIN` (default `http://localhost:5173`). Generic
500 handler logs server-side and never leaks stack traces or file paths.
`VITE_API_URL` configures the production API URL; dev uses the Vite `/api` proxy.

## Pages & journeys

1. **Landing (`/`)** — problem statement, how-it-works, Indian labour-market focus,
   "Discover my skills" CTA. No invented statistics.
2. **Discover (`/discover`)** — description form with validation + example text,
   optional skill chips (241-skill datalist), optional target occupation; loading
   state; accessible errors.
3. **Results (`/results`)** — real engine output: label + ID, direct verbatim
   evidence vs contextual inference, score labeled **uncalibrated**, confidence
   badges, ambiguity warnings, abstention state; carries skills into Career.
4. **Career (`/career`)** — real recommender output: matched/missing skills,
   heuristic score labeled **not a probability** with breakdown, prioritized pathway
   with dataset-vs-suggestion badges, education requirements, twelve-month
   feasibility shown as **unavailable** with reason, data-quality warnings.
5. **Dashboard (`/dashboard`)** — Component C from real fields only: salary-by-domain
   bars (median, IQR in tooltip), demand stacked bars with trend filters, domain
   search, source/unit/caveats panel stating cross-sectional (not time-series) nature.

## Scientific integrity

Footer + API responses carry the evaluation note (0/30 reviewed, performance
unvalidated). No F1 claims, no probabilities, no invented outcomes/salaries/stats.

## Tests

- `tests/test_api.py` (10): health, filters, 404/400/422 paths, real-engine
  extraction + recommendation integration, real market signals, CORS.
- Full suite: **102 passed** (`pytest tests/ -q`).
- Frontend: `tsc --noEmit` clean, `npm run build` succeeds (dist/ verified).
- Live E2E (`tests/test_e2e.py`, Playwright Firefox against local servers):
  **18/18 PASS** — landing, example submit, real extraction results with evidence
  and uncalibrated scores, skill carry-over into Career, real recommender output
  (matched/missing, heuristic-not-probability, pathway, 12-month unavailable),
  dashboard charts + caveats + filter, zero console errors.

## Deployment

- **Netlify:** base `web`, build `npm run build`, publish `dist`, SPA fallback in
  `netlify.toml`; set `VITE_API_URL` to the API URL.
- **Python host (Render/Railway/Fly):** Python 3.12, `pip install -r requirements.txt`,
  `uvicorn api.main:app --host 0.0.0.0 --port $PORT`, env `FRONTEND_ORIGIN`;
  ≥1 GB RAM (model builds in-memory on first extraction, ~60 s).

## Blockers / not done

- Not deployed or publicly accessible (no hosting accounts used).
- First extraction request takes ~60 s (model build); consider a warm-up or
  prebuilt joblib artifact for production.
- Human review still 0/30 — claim untested; dashboard signals are descriptive only.
