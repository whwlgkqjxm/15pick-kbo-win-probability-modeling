"""Probability-focused evaluation metrics."""

from __future__ import annotations

from typing import Iterable

import numpy as np
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss, roc_auc_score


def probability_metrics(y_true: Iterable[int], p_home: Iterable[float]) -> dict[str, float]:
    """Return the primary and secondary binary probability metrics."""

    y = np.asarray(list(y_true), dtype=int)
    p = np.clip(np.asarray(list(p_home), dtype=float), 1e-12, 1 - 1e-12)
    return {
        "log_loss": float(log_loss(y, p)),
        "brier": float(brier_score_loss(y, p)),
        "roc_auc": float(roc_auc_score(y, p)),
        "accuracy": float(accuracy_score(y, p >= 0.5)),
        "n": int(len(y)),
    }
