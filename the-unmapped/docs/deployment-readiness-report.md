# ARUNYA — Deployment Readiness Report (2026-10-10)

## 1. Changes made in this release

- **ARUNYA rebrand** (public-facing product name; competition remains MEDHA):
  `web/index.html` (title, meta, favicon), `web/public/favicon.svg` (new),
  `web/src/App.tsx` (nav), `web/src/pages/Landing.tsx` (tagline
  "Discover Your Skills. Find Your Path."), `web/src/api.ts`,
  `api/main.py` (FastAPI title "ARUNYA API"), `api/__init__.py`,
  `api/schemas.py`, `engine/__init__.py`, `netlify.toml`, `requirements.txt`,
  `README.md`, `tests/test_e2e.py` (branding assertion).
- **`.python-version`** (new): pins Python 3.12 for the Render runtime.
- **`docs/phase-7-report.md`** (new): evaluation-closure audit record.
- No engine, threshold, label, held-out, or evaluation-protocol changes.

## 2. Git status

- Local `~/workspace/the-unmapped/` is **not a git repository**.
- GitHub `sakshamcreates/MEDHA-NIT-DELHI`, branch `main`, latest commit
  `3858721` ("phase 5&6", pushed 2026-10-10T08:03:19Z).
- **Local branding does NOT match GitHub `main`**: remote still serves the
  old `<title>THE UNMAPPED — Career skill intelligence for India</title>`.
  The ARUNYA rebrand, favicon, `.python-version`, and phase-7 report exist
  only locally. Every file on remote exists locally; nothing on remote is
  missing locally. Local-only meaningful files: `docs/phase-7-report.md`,
  `web/public/favicon.svg`, `.python-version` (+ rebrand edits).
- Do NOT commit `__pycache__/`, `.pytest_cache/`, `.venv/`,
  `web/node_modules/`, `web/dist/`.

## 3. Verification results (all run 2026-10-10, local)

| Check | Result |
|---|---|
| `pytest tests/ -q` | **119/119 passed** |
| `npm run typecheck` (`tsc --noEmit`) | clean |
| `npm run build` (production) | clean |
| Playwright E2E `tests/test_e2e.py` (live API + Vite) | **18/18 PASS**, zero console errors |
| API smoke, all 7 endpoints | all 200 (see §5) |

## 4. Deployment configuration

### A. Netlify (frontend)

`the-unmapped/netlify.toml` is correct as-is. In the Netlify site settings
(UI), set:

- **Base directory:** `the-unmapped`
- **Build command:** `npm run build`
- **Publish directory:** `dist`
- **Environment variable:** `VITE_API_URL` = `https://<your-render-service>.onrender.com`
  (set only after the backend URL is known; then trigger a redeploy)
- The repo-root has no `netlify.toml`; the one inside `the-unmapped/` is
  read because the UI base directory points there. SPA fallback
  (`/* → /index.html`, 200) is configured. Netlify never executes Python.

### B. Render (backend)

Create a **Python Web Service** with:

- **Root directory:** `the-unmapped`
- **Runtime:** Python 3.12 (pinned by `.python-version`)
- **Build command:** `pip install -r requirements.txt`
- **Start command:** `uvicorn api.main:app --host 0.0.0.0 --port $PORT`
- **Environment:** `FRONTEND_ORIGIN` = `https://<your-netlify-site>.netlify.app`
  (exact origin, no trailing slash; comma-separated list also supported)
- Optional: `THE_UNMAPPED_DATA` only if the dataset moves; default
  `data/raw/indian_skills_dataset.csv` resolves relative to the code and
  ships with the repo.

Optional `render.yaml` Blueprint — place at the **repository root**
(`MEDHA-NIT-DELHI/render.yaml`, not inside `the-unmapped/`):

```yaml
services:
  - type: web
    name: arunya-api
    runtime: python
    rootDir: the-unmapped
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn api.main:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: FRONTEND_ORIGIN
        sync: false   # set in the Render dashboard after Netlify URL is known
```

Cold start: the TF-IDF model builds lazily on the first extract request
(~30 s on this VM); `/api/health` reports `model_loaded: false` until then
and never falsely claims readiness. On a free plan with sleeping, expect
the first request after idle to take ~30–60 s; the UI shows its
"Running the extraction engine…" loading state meanwhile. No database,
no external AI APIs.

### C. Deployment order

1. Commit and push (exact commands in §8).
2. Deploy backend on Render; wait for build success.
3. `curl https://<render-url>/api/health` → `status: ok`; then one real
   `POST /api/skills/extract` → 200 with `skills[]`.
4. Set `VITE_API_URL` in Netlify to the real backend URL; redeploy frontend.
5. Deploy frontend on Netlify.
6. Set `FRONTEND_ORIGIN` on Render to the exact Netlify origin; redeploy backend.
7. Run the production smoke checklist (§9).

## 5. API smoke-test results (live, 2026-10-10)

- `GET /api/health` → 200 (`model_loaded` flag + evaluation disclaimer accurate)
- `GET /api/occupations` → 200
- `GET /api/occupations/soc_13-2011_00` → 200
- `GET /api/skills` → 200
- `POST /api/skills/extract` → 200 (real extraction: SKL-092 Financial
  Accounting, score 0.218, evidence spans)
- `POST /api/career/recommend` → 200 (pathway + warnings; heuristic score
  labeled "NOT a probability"; `twelve_month_feasibility.available: false`)
- `GET /api/market/signals` → 200

## 6. Evaluation status (verified against actual files)

- Human-reviewed descriptions: **0/30** (30 pending, 0 invalid)
- Skill-pair decisions: **0/41**
- Held-out manifest: **not created** (correct — protocol requires reviews first)
- Preregistered claim (micro-F1 ≥ 0.50, ≥ +0.10 over keyword baseline):
  **untested, verdict BLOCKED**
- No labels fabricated; UI and API carry the 0/30 disclaimer; scores are
  never presented as calibrated probabilities.

To complete genuine reviews (manual, by a human):

```bash
cd ~/workspace/the-unmapped
.venv/bin/python scripts/review_pilot.py --reviewer "<name>"
.venv/bin/python scripts/review_pairs.py --reviewer "<name>"
.venv/bin/python scripts/review_report.py --require 30
```

## 7. Remaining blockers

1. **Push**: ARUNYA changes are local-only; GitHub `main` still has old
   branding. Nothing is deployed anywhere yet.
2. **Human review**: 0/30 + 0/41 — the single blocker for any model
   validation claim.
3. **Hosting accounts/credentials**: Render + Netlify setup needs Saksham's
   manual actions (§8–9). No URLs invented; placeholders used throughout.

## 8. Exact commands to commit and push

Run on a machine with the GitHub remote (do NOT run blindly — review the
file list first):

```bash
# fresh clone, then overlay the verified local tree (excluding caches)
git clone https://github.com/sakshamcreates/MEDHA-NIT-DELHI.git
rsync -a --delete \
  --exclude='.venv' --exclude='__pycache__' --exclude='.pytest_cache' \
  --exclude='node_modules' --exclude='dist' --exclude='*.pyc' \
  ~/workspace/the-unmapped/ MEDHA-NIT-DELHI/the-unmapped/
cd MEDHA-NIT-DELHI
cat > the-unmapped/.gitignore <<'EOF'
__pycache__/
*.pyc
.pytest_cache/
.venv/
web/node_modules/
web/dist/
EOF
git add the-unmapped
git status --short   # review before committing
git commit -m "ARUNYA rebrand + phase 7: deployment readiness"
git push origin main
```

## 9. Production verification checklist

- [ ] `GET <render>/api/health` → `{"status":"ok", ...}`
- [ ] `POST <render>/api/skills/extract` with a real description → 200, `skills[]` non-empty
- [ ] Frontend loads at the Netlify URL with ARUNYA title and favicon
- [ ] Landing → Discover → example → Results shows skills with SKL- IDs and evidence
- [ ] Career page shows pathway, heuristic-not-probability label, 12-month unavailable
- [ ] Dashboard renders charts; direct URL visit + refresh on `/dashboard` works (SPA fallback)
- [ ] Browser console shows zero errors during the journey
- [ ] Footer/API still display the 0/30 evaluation disclaimer
