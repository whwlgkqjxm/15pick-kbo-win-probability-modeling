"""Model construction for the primary probability experiments."""

from __future__ import annotations

from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


def build_l2_logistic(*, C: float, random_seed: int = 20260720) -> Pipeline:
    """Create the frozen median-impute, scale, and L2-logistic pipeline."""

    if C <= 0:
        raise ValueError("C must be positive")
    return Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
            ("scaler", StandardScaler()),
            (
                "model",
                LogisticRegression(
                    C=C,
                    penalty="l2",
                    solver="liblinear",
                    max_iter=5000,
                    random_state=random_seed,
                ),
            ),
        ]
    )
