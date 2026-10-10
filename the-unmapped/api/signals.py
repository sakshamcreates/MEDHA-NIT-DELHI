"""Labour-market signals computed from the real dataset (Component C).

Only genuine fields are used: india_salary_lpa_median, india_demand_trend,
domain. Salary percentiles are per-occupation JSON; for domain aggregates we
use the occupation medians (cross-sectional snapshot, NOT a time series).
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import pandas as pd

EVALUATION_NOTE = (
    "Evaluation status: 0/30 pilot descriptions human-reviewed. "
    "Model performance is not yet validated; no accuracy claims are made."
)


@lru_cache(maxsize=1)
def compute_signals(raw_csv: str) -> dict:
    df = pd.read_csv(raw_csv, encoding="utf-8-sig")
    df["domain"] = df["domain"].str.strip()
    df["india_demand_trend"] = df["india_demand_trend"].str.strip()

    salary = (
        df.groupby("domain")["india_salary_lpa_median"]
        .agg(n_occupations="count",
             median_lpa="median",
             p25_lpa=lambda s: s.quantile(0.25),
             p75_lpa=lambda s: s.quantile(0.75))
        .reset_index()
        .sort_values("median_lpa", ascending=False)
    )
    salary_rows = [
        {"domain": r.domain, "n_occupations": int(r.n_occupations),
         "median_lpa": round(float(r.median_lpa), 2),
         "p25_lpa": round(float(r.p25_lpa), 2),
         "p75_lpa": round(float(r.p75_lpa), 2)}
        for r in salary.itertuples()
    ]

    demand = (
        df.groupby(["domain", "india_demand_trend"]).size()
        .reset_index(name="n_occupations")
        .sort_values(["domain", "n_occupations"], ascending=[True, False])
    )
    demand_rows = [
        {"domain": r.domain, "trend": r.india_demand_trend,
         "n_occupations": int(r.n_occupations)}
        for r in demand.itertuples()
    ]

    return {
        "n_occupations": int(len(df)),
        "n_domains": int(df["domain"].nunique()),
        "salary_by_domain": salary_rows,
        "demand_by_domain": demand_rows,
        "source": "Indian Skills Dataset supplied with the hackathon problem statement "
                  "(820 occupations, cross-sectional snapshot)",
        "unit": "Salary in LPA (lakh rupees per annum, INR). "
                "Domain medians aggregate occupation-level median salaries.",
        "caveats": [
            "Cross-sectional snapshot, not a historical time series: the dataset "
            "contains one salary figure per occupation, so no trend-over-time "
            "can be computed.",
            "india_demand_trend is a categorical label per occupation "
            "(e.g. 'High Growth'), not a measured growth rate.",
            "Domain aggregates are medians of occupation medians; they describe "
            "the mix of occupations in each domain, not worker-level earnings.",
            "No automation-exposure field exists in the dataset; nothing about "
            "automation risk is shown.",
        ],
    }
