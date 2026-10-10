"""API integration tests (Phase 5). Uses the real engine via TestClient."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app, raise_server_exceptions=False)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["model_loaded"] is False  # lazy; must stay fast
    assert "0/30" in body["evaluation_note"]


def test_occupations_list_and_filters():
    r = client.get("/api/occupations")
    assert r.status_code == 200
    assert len(r.json()) == 820
    r = client.get("/api/occupations", params={"domain": "Healthcare & Medical"})
    assert r.status_code == 200 and all(
        o["domain"] == "Healthcare & Medical" for o in r.json())
    r = client.get("/api/occupations", params={"q": "nurse"})
    assert r.status_code == 200 and r.json()


def test_occupation_detail_and_404():
    r = client.get("/api/occupations/soc_13-2011_00")
    assert r.status_code == 200
    assert r.json()["title"] == "Accountants and Auditors"
    assert r.json()["n_required_skills"] == 10
    r = client.get("/api/occupations/nope")
    assert r.status_code == 404
    assert "detail" in r.json()


def test_skills_list():
    r = client.get("/api/skills")
    assert r.status_code == 200
    assert len(r.json()) == 241


def test_market_signals_real_data():
    r = client.get("/api/market/signals")
    assert r.status_code == 200
    body = r.json()
    assert body["n_occupations"] == 820
    assert body["n_domains"] > 10
    medians = [s["median_lpa"] for s in body["salary_by_domain"]]
    assert medians == sorted(medians, reverse=True)
    assert body["caveats"] and "time series" in " ".join(body["caveats"])
    assert "LPA" in body["unit"]


def test_extract_validation():
    assert client.post("/api/skills/extract", json={"text": ""}).status_code == 422
    assert client.post("/api/skills/extract",
                       json={"text": "   "}).status_code == 400
    assert client.post("/api/skills/extract",
                       json={"text": "x", "top_k": 0}).status_code == 422
    assert client.post("/api/skills/extract",
                       json={"text": "x" * 5001}).status_code == 422


@pytest.mark.slow
def test_extract_real_engine():
    r = client.post("/api/skills/extract",
                    json={"text": "I did the accounts for my father's shop in Tally "
                                  "and made bills in Excel.", "top_k": 5})
    assert r.status_code == 200
    body = r.json()
    assert body["skills"], "real engine should find skills"
    labels = {s["label"] for s in body["skills"]}
    assert "Financial Accounting" in labels or "Excel/Spreadsheets" in labels
    s0 = body["skills"][0]
    assert {"skill_id", "label", "score", "confidence",
            "method", "evidence"} <= set(s0)
    assert "0/30" in body["evaluation_note"]


@pytest.mark.slow
def test_recommend_real_engine():
    r = client.post("/api/career/recommend", json={
        "skill_ids": ["SKL-092", "SKL-089"],
        "target_occupation_id": "soc_13-2011_00",
        "profile_education": "12th Pass"})
    assert r.status_code == 200
    body = r.json()
    assert body["target_occupation"]["title"] == "Accountants and Auditors"
    assert body["heuristic_rank_score"] >= 0
    assert "NOT a probability" in body["score_note"]
    assert body["twelve_month_feasibility"]["available"] is False
    assert body["pathway"]


def test_recommend_errors():
    r = client.post("/api/career/recommend", json={
        "skill_ids": [], "target_occupation_id": "nope"})
    assert r.status_code == 400
    r = client.post("/api/career/recommend", json={
        "skill_ids": [], "target_occupation_id": "soc_13-2011_00",
        "profile_education": "Hogwarts"})
    assert r.status_code == 400


def test_cors_headers():
    r = client.options("/api/health",
                       headers={"Origin": "http://localhost:5173",
                                "Access-Control-Request-Method": "GET"})
    assert r.status_code == 200
    assert "access-control-allow-origin" in {k.lower() for k in r.headers}
