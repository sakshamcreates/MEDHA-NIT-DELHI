"""Tests for the calibration investigation (engine/calibration.py)."""
from __future__ import annotations

import numpy as np
import pytest

from engine.calibration import (PROXY_RUBRIC, brier_score,
                                expected_calibration_error, fit_calibrator,
                                proxy_feasibility_study, proxy_label,
                                reliability_table)


def test_proxy_label_rubric():
    assert proxy_label(0.7, True, "High Growth", 3) == 1
    assert proxy_label(0.7, False, "High Growth", 3) == 0, "education gate"
    assert proxy_label(0.5, True, "Stable", 5) == 0
    assert proxy_label(0.5, True, "High Growth", 2) == 1, "few missing + hot demand"
    assert proxy_label(0.9, True, "Stable", 1) == 0, "stable demand not favorable"
    # deterministic
    assert proxy_label(0.7, True, "High Growth", 3) == proxy_label(0.7, True, "High Growth", 3)


def test_ece_perfect_calibration():
    y = np.array([0, 0, 1, 1])
    p = np.array([0.0, 0.0, 1.0, 1.0])
    assert expected_calibration_error(y, p) == pytest.approx(0.0)


def test_ece_known_miscalibration():
    y = np.array([0, 0, 0, 0])
    p = np.array([0.5, 0.5, 0.5, 0.5])
    assert expected_calibration_error(y, p, n_bins=10) == pytest.approx(0.5)


def test_brier():
    assert brier_score(np.array([0, 1]), np.array([0.0, 1.0])) == pytest.approx(0.0)
    assert brier_score(np.array([0, 1]), np.array([0.5, 0.5])) == pytest.approx(0.25)


def test_reliability_table_structure():
    rows = reliability_table(np.array([0, 1, 1]), np.array([0.1, 0.8, 0.9]), n_bins=5)
    assert len(rows) == 5
    assert all({"bin", "n", "mean_predicted", "observed_rate"} <= set(r) for r in rows)


def test_fit_calibrator_mechanics():
    rng = np.random.default_rng(0)
    X = rng.normal(size=(60, 3))
    y = (X[:, 0] > 0).astype(int)
    model = fit_calibrator(X, y)
    prob = model.predict_proba(X)[:, 1]
    assert ((prob > 0.5) == (X[:, 0] > 0)).mean() > 0.9


def test_proxy_study_reports_limitation():
    study = proxy_feasibility_study(n_profiles=60, seed=1)
    assert study["n_profiles"] == 60
    assert "proxy_rubric" in study and PROXY_RUBRIC in study["proxy_rubric"]
    assert "NOT observed labour-market outcomes" in study["proxy_rubric"]
    assert "limitation" in study and "not real-world calibration" in study["limitation"]
    assert study["brier"] < study["brier_base_rate"], "calibrator should beat base rate"
    assert 0.0 <= study["ece"] <= 1.0
