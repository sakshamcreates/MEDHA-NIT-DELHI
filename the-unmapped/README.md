# ARUNYA — Discover Your Skills. Find Your Path.

AI-assisted Career Intelligence Platform for the Indian labour market.

Turns plain-language descriptions of informal work into structured skill profiles
(TF-IDF extraction over a 241-skill canonical registry), maps profiles onto 820
Indian occupations (transition recommender with explained learning pathways), and
shows real labour-market signals (salary distributions, demand trends by domain).

Built for the MEDHA Hackathon (PS-02 — Social Upliftment); MEDHA remains the name
of the competition.

**Scientific-integrity note:** 0/30 pilot descriptions are human-reviewed, so model
performance is not validated and no accuracy claims are made. Scores are uncalibrated
model scores, never probabilities; twelve-month outcome prediction is unavailable.

## Project layout

```
the-unmapped/
├── api/            # FastAPI thin layer over engine/ (no duplicated logic)
├── engine/         # extract.py (TF-IDF), keyword_baseline.py, recommender.py, calibration.py
├── web/            # React + TypeScript + Vite + Tailwind frontend
├── scripts/        # registry, pilot, review workflow, evaluation harness
├── tests/          # pytest suite (102 tests)
├── data/           # raw dataset, processed registry, evaluation
├── docs/           # phase reports, architecture, evaluation plan
├── requirements.txt
└── netlify.toml    # frontend deployment (Netlify)
```

## Local development

Prerequisites: Python 3.12, Node 24, npm.

```bash
# 1. Python environment
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install pytest httpx          # dev/test only

# 2. Start the API (http://localhost:8000)
FRONTEND_ORIGIN=http://localhost:5173 .venv/bin/uvicorn api.main:app --port 8000
# First /api/skills/extract call builds the TF-IDF model (~60 s, one-time).

# 3. Start the frontend (http://localhost:5173, proxies /api to :8000)
cd web && npm install && npm run dev
```

Run tests: `.venv/bin/python -m pytest tests/ -q` (from project root).
Frontend typecheck/build: `cd web && npm run build`.

## API

| Method & path              | Description                                              |
|----------------------------|----------------------------------------------------------|
| `GET /api/health`          | Status, model version, evaluation note                   |
| `GET /api/occupations`     | 820 occupations (`?domain=`, `?q=` filters)               |
| `GET /api/occupations/{id}`| Occupation detail (salary, exams, demand, …)              |
| `GET /api/skills`          | 241 canonical skills                                      |
| `POST /api/skills/extract` | `{text, top_k}` → skill predictions with evidence        |
| `POST /api/career/recommend`| `{skill_ids, target_occupation_id, profile_education?}` → gaps + pathway |
| `GET /api/market/signals`  | Salary by domain + demand by domain (real dataset fields)|

Error responses are JSON `{detail: ...}`; stack traces are never exposed.

## Deployment

**Frontend → Netlify** (static hosting only — it does NOT run the Python API):
- Base directory: `web`
- Build command: `npm run build`
- Publish directory: `dist`
- Environment variable: `VITE_API_URL` = your deployed API URL
  (e.g. `https://arunya-api.onrender.com`). If unset, same-origin `/api` is used.
- `netlify.toml` in the repo root already configures the above plus SPA fallback.

**Backend → any Python host (Render / Railway / Fly.io):**
- Runtime: Python 3.12; install: `pip install -r requirements.txt`
- Start command: `uvicorn api.main:app --host 0.0.0.0 --port $PORT`
- Environment: `FRONTEND_ORIGIN` = your Netlify site URL
  (e.g. `https://arunya.netlify.app`); `THE_UNMAPPED_DATA` optionally
  overrides the dataset path.
- No database required. The model builds in-memory on first extraction
  request (~60 s); provision ≥1 GB RAM.

## Evaluation status

`card.md` holds the pre-registered claim (extraction micro-F1 ≥ 0.50 and
≥ +0.10 over the keyword baseline). It is **untested**: human review of the
pilot set has not been completed (`scripts/review_pilot.py`). Provisional
numbers in `docs/phase-3-model-report.md` are engineering diagnostics on
unreviewed labels, not results.
