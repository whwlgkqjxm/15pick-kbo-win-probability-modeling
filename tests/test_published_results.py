from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def test_player_indices_improve_primary_metrics() -> None:
    results = pd.read_csv(ROOT / "reports/reproduced/player_index_ablation.csv")
    dev = results.loc[results["protocol"] == "BEST_DEVELOPMENT"].set_index("model")
    full = dev.loc["BATTER_PLUS_STARTER_INDICES"]
    baseline = dev.loc["BASELINE_NO_PLAYER_INDICES"]
    assert full["log_loss"] < baseline["log_loss"]
    assert full["brier"] < baseline["brier"]
    assert full["roc_auc"] > baseline["roc_auc"]


def test_relief_pitcher_index_did_not_improve_domain_log_loss() -> None:
    results = pd.read_csv(
        ROOT / "research_records/key_results/V8_DOMAIN_BASELINE_AND_LEGACY_COMPARISON.csv"
    ).set_index("candidate")
    assert results.loc["BULLPEN_SELECTED", "log_loss"] > results.loc["TEAM_BASELINE", "log_loss"]
