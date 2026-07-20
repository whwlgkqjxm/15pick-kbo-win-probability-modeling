from pathlib import Path

import pandas as pd


def test_primary_result_ordering() -> None:
    root = Path(__file__).resolve().parents[1]
    results = pd.read_csv(root / "reports" / "primary_income_ablation.csv")
    dev = results.loc[results["protocol"] == "BEST_DEVELOPMENT"].set_index("model")
    assert dev.loc["ALL_PLAYER_INCOME", "log_loss"] < dev.loc["NO_PLAYER_INCOME", "log_loss"]
    assert dev.loc["ALL_PLAYER_INCOME", "brier"] < dev.loc["NO_PLAYER_INCOME", "brier"]
    assert dev.loc["ALL_PLAYER_INCOME", "roc_auc"] > dev.loc["NO_PLAYER_INCOME", "roc_auc"]
