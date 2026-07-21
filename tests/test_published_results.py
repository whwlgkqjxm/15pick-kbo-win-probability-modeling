from pathlib import Path

import pandas as pd


def test_player_indices_improve_primary_metrics() -> None:
    root = Path(__file__).resolve().parents[1]
    results = pd.read_csv(root / "reports" / "player_index_ablation.csv")
    dev = results.loc[results["protocol"] == "BEST_DEVELOPMENT"].set_index("model")
    full = dev.loc["BATTER_PLUS_STARTER_INDICES"]
    baseline = dev.loc["BASELINE_NO_PLAYER_INDICES"]
    assert full["log_loss"] < baseline["log_loss"]
    assert full["brier"] < baseline["brier"]
    assert full["roc_auc"] > baseline["roc_auc"]


def test_relief_pitcher_index_did_not_improve_log_loss() -> None:
    root = Path(__file__).resolve().parents[1]
    results = pd.read_csv(root / "reports" / "relief_pitcher_index_ablation.csv")
    assert (
        results["relief_pitcher_index_log_loss"] > results["reference_log_loss"]
    ).all()
