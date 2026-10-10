"""Pydantic request/response schemas for the ARUNYA API."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    status: str
    version: str
    model: str
    model_loaded: bool
    reviewed_labels: int
    evaluation_note: str


class OccupationSummary(BaseModel):
    id: str
    title: str
    domain: str
    education_required: str
    demand_trend: str


class OccupationDetail(OccupationSummary):
    salary_lpa_median: int
    salary_percentiles: dict
    qualifying_exams: list[str]
    top_cities: list[str]
    bright_outlook: bool
    remote_friendly: bool
    n_required_skills: int


class SkillSummary(BaseModel):
    skill_id: str
    label: str


class ExtractRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
    top_k: int = Field(default=10, ge=1, le=50)


class SkillEvidence(BaseModel):
    type: str
    span: str | None = None
    note: str | None = None
    start: int | None = None
    end: int | None = None


class SkillPrediction(BaseModel):
    skill_id: str
    label: str
    score: float
    confidence: str
    method: str
    evidence: SkillEvidence
    occupation_context: list[dict]
    notes: list[str]


class ExtractResponse(BaseModel):
    model: dict
    skills: list[SkillPrediction]
    abstained: bool
    abstention_reason: str | None = None
    evaluation_note: str


class RecommendRequest(BaseModel):
    skill_ids: list[str] = Field(default_factory=list, max_length=241)
    target_occupation_id: str = Field(min_length=1)
    profile_education: str | None = None
    top_k_pathway: int = Field(default=10, ge=1, le=25)


class RecommendResponse(BaseModel):
    """Top-level recommender fields validated; nested detail passed through."""

    model_config = ConfigDict(extra="allow")

    target_occupation: dict
    matched_skills: list[dict]
    missing_skills: list[dict]
    skill_overlap: dict
    explanation: str
    pathway: list[dict]
    education: dict
    heuristic_rank_score: float
    score_breakdown: dict
    score_note: str
    twelve_month_feasibility: dict
    warnings: list[str]


class SalaryByDomain(BaseModel):
    domain: str
    n_occupations: int
    median_lpa: float
    p25_lpa: float
    p75_lpa: float


class DemandByDomain(BaseModel):
    domain: str
    trend: str
    n_occupations: int


class MarketSignalsResponse(BaseModel):
    n_occupations: int
    n_domains: int
    salary_by_domain: list[SalaryByDomain]
    demand_by_domain: list[DemandByDomain]
    source: str
    unit: str
    caveats: list[str]
