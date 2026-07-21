import numpy as np
import pandas as pd

from fifteenpick_prediction.modeling import build_l2_logistic


def test_authoritative_logistic_pipeline_fits_probabilities():
    x = pd.DataFrame({"a": [0.0, 1.0, 2.0, np.nan], "b": [1.0, 1.0, 0.0, 0.0]})
    y = np.array([0, 0, 1, 1])
    model = build_l2_logistic(C=0.1)
    model.fit(x, y)
    p = model.predict_proba(x)[:, 1]
    assert np.all((p > 0) & (p < 1))
    assert model.named_steps["model"].solver == "lbfgs"
