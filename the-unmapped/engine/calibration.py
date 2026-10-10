"""Twelve-month feasibility: calibration investigation (Phase 4, Part D).

HONEST CONCLUSION UP FRONT: the project has no observed transition-outcome
labels (did a real person achieve the transition within 12 months: yes/no).
Without such labels, a statistically valid calibrated probability CANNOT be
estimated. The Transition Recommender therefore exposes
twelve_month_feasibility.available=False instead of fabricating confidence.

What this module DOES provide:
1. A documented, versioned PROXY rubric (proxy_label) -- deterministic,
   disclosed, and explicitly NOT real outcomes.
2. A calibrator (logistic regression) + calibration metrics (ECE, Brier,
   reliability table) that can be evaluated on proxy labels to study the
   *mechanics*, and reused unchanged if real outcome labels ever exist.
3. proxy_feasibility_study(): runs the full pipeline on synthetic profiles and
   reports that calibration holds only with respect to the rubric.

Do not present proxy-calibrated numbers as real-world probabilities.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression

ROOT = Path(__file__).resolve().parent.parent

PROXY_RUBRIC_VERSION = "proxy-rubric-v0"
PROXY_RUBRIC = (
    "proxy-rubric-v0: label=1 iff education requirement met AND "
    "(skill Dice >= 0.60 with demand in {High Growth, Very High Growth, Emerging} "
    "OR missing skills <= 2 with demand in {High Growth, Very High Growth}); "
    "else 0. These are synthetic rubric outputs, NOT observed labour-market outcomes."
)
FAVORABLE_DEMAND = {"High Growth", "Very High Growth", "Emerging"}


def proxy_label(dice: float, education_met: bool, demand_trend: str,
                n_missing: int) -> int:
    """Deterministic proxy outcome under the documented rubric."""
    if not education_met:
        return 0
    if dice >= 0.60 and demand_trend in FAVORABLE_DEMAND:
        return 1
    if n_missing <= 2 and demand_trend in ("High Growth", "Very High Growth"):
        return 1
    return 0


def featurize(dice: float, education_met: bool, demand_weight: float,
              n_missing: int, context_fit: float | None) -> list[float]:
    return [dice, 1.0 if education_met else 0.0, demand_weight,
            float(n_missing), context_fit if context_fit is not None else 0.0]


def fit_calibrator(X: np.ndarray, y: np.ndarray) -> LogisticRegression:
    model = LogisticRegression(max_iter=1000)
    model.fit(X, y)
    return model


def expected_calibration_error(y_true: np.ndarray, y_prob: np.ndarray,
                               n_bins: int = 10) -> float:
    y_true = np.asarray(y_true, dtype=float)
    y_prob = np.asarray(y_prob, dtype=float)
    ece = 0.0
    for b in range(n_bins):
        lo, hi = b / n_bins, (b + 1) / n_bins
        mask = (y_prob > lo) & (y_prob <= hi) if b else (y_prob >= lo) & (y_prob <= hi)
        if mask.sum() == 0:
            continue
        ece += mask.sum() / len(y_prob) * abs(y_true[mask].mean() - y_prob[mask].mean())
    return float(ece)


def brier_score(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    y_true = np.asarray(y_true, dtype=float)
    y_prob = np.asarray(y_prob, dtype=float)
    return float(np.mean((y_prob - y_true) ** 2))


def reliability_table(y_true: np.ndarray, y_prob: np.ndarray,
                      n_bins: int = 10) -> list[dict]:
    y_true = np.asarray(y_true, dtype=float)
    y_prob = np.asarray(y_prob, dtype=float)
    rows = []
    for b in range(n_bins):
        lo, hi = round(b / n_bins, 2), round((b + 1) / n_bins, 2)
        mask = (y_prob > lo) & (y_prob <= hi) if b else (y_prob >= lo) & (y_prob <= hi)
        rows.append({"bin": f"({lo},{hi}]", "n": int(mask.sum()),
                     "mean_predicted": round(float(y_prob[mask].mean()), 4) if mask.sum() else None,
                     "observed_rate": round(float(y_true[mask].mean()), 4) if mask.sum() else None})
    return rows


def proxy_feasibility_study(n_profiles: int = 300, seed: int = 7) -> dict:
    """Mechanical study ONLY: can a calibrator fit the proxy rubric?

    Uses synthetic profiles x real occupations. Reports calibration metrics
    against proxy labels with the explicit limitation that this measures
    consistency with the rubric, not real-world calibration.
    """
    import sys
    sys.path.insert(0, str(ROOT))
    from engine.recommender import (DEMAND_WEIGHT, EDU_ORDER, TransitionRecommender)
    rng = np.random.default_rng(seed)
    rec = TransitionRecommender.build(ROOT / "data/raw/indian_skills_dataset.csv",
                                     ROOT / "data/processed")
    occ_ids = list(rec.occupations)
    skill_ids = list(rec.skill_id_to_label)
    X, y = [], []
    for _ in range(n_profiles):
        target = occ_ids[rng.integers(len(occ_ids))]
        occ = rec.occupations[target]
        required = rec.occ_skills[target]
        # plausible near-transition profiles: mostly required skills + some noise
        n_keep = rng.integers(0, len(required) + 1)
        n_noise = rng.integers(0, 5)
        profile = list(rng.choice(required, size=n_keep, replace=False)) + \
                  list(rng.choice(skill_ids, size=n_noise, replace=False))
        profile = list(dict.fromkeys(profile))
        matched = len(set(profile) & set(required))
        dice = 2 * matched / (len(profile) + len(required)) if (profile or required) else 0.0
        edu = rng.choice(list(EDU_ORDER))
        edu_met = EDU_ORDER[edu] >= EDU_ORDER.get(occ["education_required"], 0)
        n_missing = len(required) - matched
        y.append(proxy_label(dice, edu_met, occ["demand_trend"], n_missing))
        X.append(featurize(dice, edu_met, DEMAND_WEIGHT.get(occ["demand_trend"], 0.5),
                           n_missing, None))
    X, y = np.array(X), np.array(y)
    # deterministic 70/30 split
    split = int(0.7 * len(X))
    model = fit_calibrator(X[:split], y[:split])
    prob = model.predict_proba(X[split:])[:, 1]
    base_rate = float(y[:split].mean())
    base_prob = np.full_like(prob, base_rate)
    return {
        "n_profiles": n_profiles, "n_train": split, "n_test": len(X) - split,
        "proxy_rubric": PROXY_RUBRIC,
        "ece": round(expected_calibration_error(y[split:], prob), 4),
        "brier": round(brier_score(y[split:], prob), 4),
        "brier_base_rate": round(brier_score(y[split:], base_prob), 4),
        "reliability": reliability_table(y[split:], prob),
        "limitation": ("Calibrated ONLY to proxy-rubric-v0 labels (synthetic). "
                       "This demonstrates the mechanics, not real-world calibration. "
                       "Do not surface these probabilities to users."),
    }


if __name__ == "__main__":
    import json
    print(json.dumps(proxy_feasibility_study(), indent=2))
