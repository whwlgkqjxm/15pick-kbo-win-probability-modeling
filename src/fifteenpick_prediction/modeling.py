"""Model construction for the frozen 15Pick probability experiments."""

from __future__ import annotations

from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

RANDOM_SEED = 20260720


def build_l2_logistic(*, C: float, random_seed: int = RANDOM_SEED) -> Pipeline:
    """Build the authoritative median-impute, scale, L2-logistic pipeline.

    No solver is overridden. This intentionally preserves the scikit-learn
    default used by the authoritative V12 run and saved model binaries.
    """
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
                    max_iter=5000,
                    random_state=random_seed,
                ),
            ),
        ]
    )
