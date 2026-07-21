#!/usr/bin/env python3
"""Generate publication-ready summary figures from frozen research tables."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
FROZEN = REPORTS / "frozen"
REPRODUCED = REPORTS / "reproduced"
FIGURES = REPORTS / "figures"
FIGURES.mkdir(parents=True, exist_ok=True)


def save_current(name: str) -> None:
    plt.tight_layout()
    plt.savefig(FIGURES / name, dpi=180, bbox_inches="tight")
    plt.close()


def _dot_plot(
    data: pd.DataFrame,
    *,
    label_col: str,
    value_col: str,
    title: str,
    xlabel: str,
    name: str,
) -> None:
    ordered = data.sort_values(value_col, ascending=False).reset_index(drop=True)
    y = range(len(ordered))
    plt.figure(figsize=(9, max(4.5, 0.38 * len(ordered))))
    plt.scatter(ordered[value_col], y, s=55)
    plt.yticks(list(y), ordered[label_col])
    span = float(ordered[value_col].max() - ordered[value_col].min())
    margin = max(span * 0.20, 0.0008)
    plt.xlim(float(ordered[value_col].min()) - margin, float(ordered[value_col].max()) + margin)
    for index, value in enumerate(ordered[value_col]):
        plt.text(
            float(value) + margin * 0.04,
            index,
            f"{float(value):.6f}",
            va="center",
            fontsize=8,
        )
    plt.xlabel(xlabel)
    plt.title(title)
    save_current(name)


def ablation_plot() -> None:
    data = pd.read_csv(REPRODUCED / "player_index_ablation.csv")
    data = data[data["protocol"].eq("BEST_DEVELOPMENT")].copy()
    label_map = {
        "BASELINE_NO_PLAYER_INDICES": "Conventional pregame only",
        "BATTER_INDEX_ONLY": "+ Batter index",
        "STARTER_INDEX_ONLY": "+ Starting-pitcher index",
        "BATTER_PLUS_STARTER_INDICES": "+ Batter and starter indices",
    }
    data["display"] = data["model"].map(label_map)
    _dot_plot(
        data,
        label_col="display",
        value_col="log_loss",
        title="Role-specific player-index ablation — 2026 development evaluation",
        xlabel="Log loss (lower is better)",
        name="player_index_ablation_logloss.png",
    )


def model_family_plot() -> None:
    data = pd.read_csv(FROZEN / "V12_MODEL_FAMILY_TEMPORAL_CV.csv").nsmallest(15, "log_loss")
    _dot_plot(
        data,
        label_col="model_id",
        value_col="log_loss",
        title="Top model configurations under 2024–2025 temporal CV",
        xlabel="Temporal-CV Log loss (lower is better)",
        name="model_family_temporal_cv.png",
    )


def strategy_plot() -> None:
    data = pd.read_csv(
        FROZEN / "V12_2026_ALL_LEARNING_METHOD_RESULTS.csv"
    ).nsmallest(18, "log_loss")
    data["display"] = data["model_id"].astype(str) + " / " + data["training_strategy"].astype(str)
    _dot_plot(
        data,
        label_col="display",
        value_col="log_loss",
        title="Best observed learning strategies",
        xlabel="2026 development Log loss (lower is better)",
        name="training_strategy_comparison.png",
    )


def calibration_plot() -> None:
    data = pd.read_csv(FROZEN / "V12_2026_CALIBRATION_DECILES.csv")
    plt.figure(figsize=(6, 6))
    plt.plot([0, 1], [0, 1], linestyle="--", label="Perfect calibration")
    for model_id, group in data.groupby("model_id"):
        ordered = group.sort_values("predicted_mean")
        plt.plot(ordered["predicted_mean"], ordered["actual_rate"], marker="o", label=model_id)
    plt.xlabel("Mean predicted probability")
    plt.ylabel("Observed home-win rate")
    plt.title("Reliability diagram — 2026 development evaluation")
    plt.legend(fontsize=8)
    save_current("calibration_reliability.png")


def importance_plot() -> None:
    data = pd.read_csv(FROZEN / "V12_2026_PERMUTATION_IMPORTANCE_CV_CHAMPION.csv")
    data = data.sort_values("importance_mean_neg_logloss")
    plt.figure(figsize=(8, 5.5))
    plt.barh(data["feature"], data["importance_mean_neg_logloss"], xerr=data["importance_sd"])
    plt.xlabel("Permutation importance (decrease in negative Log loss)")
    plt.title("Feature importance — CV-selected model evaluated on 2026")
    save_current("permutation_importance.png")


def main() -> None:
    ablation_plot()
    model_family_plot()
    strategy_plot()
    calibration_plot()
    importance_plot()
    print(f"wrote figures to {FIGURES}")


if __name__ == "__main__":
    main()
