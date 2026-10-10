"""THE UNMAPPED API — thin FastAPI layer over the Python engine.

Calls engine/extract.py, engine/recommender.py and the dataset directly;
no logic is duplicated here. Run with:
    uvicorn api.main:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api import schemas
from api.signals import EVALUATION_NOTE, compute_signals

log = logging.getLogger("unmapped.api")

ROOT = Path(__file__).resolve().parent.parent
RAW_CSV = Path(os.environ.get("THE_UNMAPPED_DATA",
                              ROOT / "data" / "raw" / "indian_skills_dataset.csv"))
PROCESSED = ROOT / "data" / "processed"

API_VERSION = "0.1.0"

app = FastAPI(title="THE UNMAPPED API", version=API_VERSION,
              docs_url="/api/docs", openapi_url="/api/openapi.json")

origins = [o.strip() for o in os.environ.get(
    "FRONTEND_ORIGIN", "http://localhost:5173").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

_extractor = None
_recommender = None


def get_extractor():
    global _extractor
    if _extractor is None:
        from engine.extract import ExtractorConfig, SkillExtractor
        log.info("building TF-IDF extractor (one-time cost)")
        _extractor = SkillExtractor.build(str(RAW_CSV), str(PROCESSED),
                                         ExtractorConfig())
    return _extractor


def get_recommender():
    global _recommender
    if _recommender is None:
        from engine.recommender import TransitionRecommender
        _recommender = TransitionRecommender.build(RAW_CSV, PROCESSED,
                                                  extractor=get_extractor())
    return _recommender


@app.exception_handler(Exception)
async def _internal_error(request, exc):  # noqa: ANN001, ANN202
    log.exception("unhandled error")
    return JSONResponse(status_code=500,
                        content={"detail": "internal error; administrators have been notified"})


@app.get("/api/health", response_model=schemas.HealthResponse)
def health():
    return {
        "status": "ok",
        "version": API_VERSION,
        "model": "tfidf-skill-extractor v0.1.0",
        "model_loaded": _extractor is not None,
        "reviewed_labels": 0,
        "evaluation_note": EVALUATION_NOTE,
    }


@app.get("/api/occupations", response_model=list[schemas.OccupationSummary])
def list_occupations(domain: str | None = Query(default=None),
                     q: str | None = Query(default=None, max_length=100)):
    rec = get_recommender()
    out = []
    for occ_id, occ in rec.occupations.items():
        if domain and occ["domain"].casefold() != domain.casefold():
            continue
        if q and q.casefold() not in occ["title"].casefold():
            continue
        out.append({"id": occ_id, "title": occ["title"], "domain": occ["domain"],
                    "education_required": occ["education_required"],
                    "demand_trend": occ["demand_trend"]})
    return sorted(out, key=lambda o: o["title"])


@app.get("/api/occupations/{occ_id}", response_model=schemas.OccupationDetail)
def occupation_detail(occ_id: str):
    rec = get_recommender()
    occ = rec.occupations.get(occ_id)
    if occ is None:
        raise HTTPException(status_code=404, detail=f"unknown occupation: {occ_id}")
    return {**{k: occ[k] for k in ("id", "title", "domain", "education_required",
                                   "demand_trend", "salary_lpa_median",
                                   "salary_percentiles", "qualifying_exams",
                                   "top_cities", "bright_outlook", "remote_friendly")},
            "n_required_skills": len(rec.occ_skills[occ_id])}


@app.get("/api/skills", response_model=list[schemas.SkillSummary])
def list_skills():
    rec = get_recommender()
    return [{"skill_id": sid, "label": label}
            for sid, label in sorted(rec.skill_id_to_label.items(),
                                    key=lambda kv: kv[1])]


@app.post("/api/skills/extract", response_model=schemas.ExtractResponse)
def extract_skills(req: schemas.ExtractRequest):
    text = req.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="text must not be empty")
    try:
        out = get_extractor().extract_skills(text, top_k=req.top_k)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    out["evaluation_note"] = EVALUATION_NOTE
    return out


@app.post("/api/career/recommend", response_model=schemas.RecommendResponse)
def recommend(req: schemas.RecommendRequest):
    try:
        return get_recommender().recommend(
            req.skill_ids, req.target_occupation_id,
            profile_education=req.profile_education,
            top_k_pathway=req.top_k_pathway)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except TypeError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.get("/api/market/signals", response_model=schemas.MarketSignalsResponse)
def market_signals():
    if not RAW_CSV.exists():
        raise HTTPException(status_code=500, detail="dataset unavailable")
    return compute_signals(str(RAW_CSV))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0",
                port=int(os.environ.get("PORT", "8000")))
