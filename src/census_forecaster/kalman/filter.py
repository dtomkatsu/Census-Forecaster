"""Kalman predict/update primitives for a 2D [log_level, log_growth] state."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# Damping coefficient matching the existing damped-trend asymptote.
PHI_DEFAULT: float = 0.85

# Observation row vectors (1D, applied as H @ x).
H_LEVEL: np.ndarray = np.array([1.0, 0.0])   # observes log_level
H_GROWTH: np.ndarray = np.array([0.0, 1.0])  # observes log_growth_rate


@dataclass
class KalmanState:
    mean: np.ndarray  # shape (2,): [log_level, log_growth]
    cov: np.ndarray   # shape (2, 2): posterior covariance
    year: int


def make_transition(phi: float = PHI_DEFAULT) -> np.ndarray:
    """Local linear trend transition:  level[t+1] = level[t] + growth[t];
    growth[t+1] = phi * growth[t]."""
    return np.array([[1.0, 1.0], [0.0, phi]], dtype=float)


def make_process_noise(q_level: float = 1e-6, q_growth: float = 4e-4) -> np.ndarray:
    """Diagonal process noise.  q_growth = (0.02)^2 ≈ 2% annual growth uncertainty."""
    return np.diag([q_level, q_growth]).astype(float)


def kalman_predict(state: KalmanState, F: np.ndarray, Q: np.ndarray) -> KalmanState:
    """One-step time update."""
    mean = F @ state.mean
    cov = F @ state.cov @ F.T + Q
    return KalmanState(mean=mean, cov=cov, year=state.year + 1)


def kalman_update(
    state: KalmanState, y: float, H: np.ndarray, R: float
) -> KalmanState:
    """Joseph-form scalar Kalman measurement update (numerically stable)."""
    innov_cov = float(H @ state.cov @ H) + R
    if innov_cov <= 0.0:
        return state
    K = (state.cov @ H) / innov_cov           # shape (2,), Kalman gain
    innov = y - float(H @ state.mean)
    mean = state.mean + K * innov
    I_KH = np.eye(2) - np.outer(K, H)
    # Joseph form: (I-KH)P(I-KH)^T + R*KK^T  (stays positive semi-definite)
    cov = I_KH @ state.cov @ I_KH.T + R * np.outer(K, K)
    return KalmanState(mean=mean, cov=cov, year=state.year)
