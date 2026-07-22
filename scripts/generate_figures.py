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
    order = [
        "CONSTANT_0_5",
        "BASELINE_NO_PLAYER_INDICES",
        "BATTER_INDEX_ONLY",
        "STARTER_INDEX_ONLY",
        "BATTER_PLUS_STARTER_INDICES",
    ]
    label_map = {
        "CONSTANT_0_5": "Constant p(home)=0.50",
        "BASELINE_NO_PLAYER_INDICES": "Conventional pregame variables",
        "BATTER_INDEX_ONLY": "+ batter index",
        "STARTER_INDEX_ONLY": "+ starting-pitcher index",
        "BATTER_PLUS_STARTER_INDICES": "+ batter and starting-pitcher indices",
    }
    data = data.set_index("model").loc[order].reset_index()
    data["display"] = data["model"].map(label_map)
    constant = float(data.loc[data["model"].eq("CONSTANT_0_5"), "log_loss"].iloc[0])
    data["improvement"] = constant - data["log_loss"]

    fig, ax = plt.subplots(figsize=(10, 5.4))
    bars = ax.barh(data["display"], data["improvement"])
    bars[-1].set_hatch("//")
    ax.invert_yaxis()
    ax.set_xlim(0, float(data["improvement"].max()) * 1.28)
    ax.set_xlabel("Log-loss improvement over constant p(home)=0.50 (higher is better)")
    ax.set_title("Role-specific model comparison", pad=12)
    ax.grid(axis="x", alpha=0.25)
    for bar, raw, improvement in zip(
        bars, data["log_loss"], data["improvement"], strict=True
    ):
        ax.text(
            float(improvement) + 0.00035,
            bar.get_y() + bar.get_height() / 2,
            f"Log loss {raw:.6f}",
            va="center",
            fontsize=9,
        )
    fig.text(
        0.5,
        0.01,
        (
            "Best-observed model: trained on the most recent 720 pre-2026 games; "
            "evaluated on 416 decision games in 2026."
        ),
        ha="center",
        fontsize=9,
    )
    plt.tight_layout(rect=(0, 0.04, 1, 1))
    plt.savefig(FIGURES / "main_model_comparison.png", dpi=200, bbox_inches="tight")
    plt.close()

    bullpen_2025 = pd.read_csv(
        ROOT / "research_records" / "key_results" / "V8_2025_PREDICTION_APPLICATION_RESULTS.csv"
    ).set_index("method")
    bullpen_2026 = pd.read_csv(
        ROOT / "research_records" / "key_results" / "V8_2026_POSTHOC_APPLICATION_RESULTS.csv"
    ).set_index("method")
    bullpen = pd.DataFrame(
        {
            "evaluation": ["2025 temporal OOF (698 games)", "2026 post-hoc (416 games)"],
            "starter_stack": [
                bullpen_2025.loc["LOGIT_STACK_V7_STARTER_C0.1", "log_loss"],
                bullpen_2026.loc["LOGIT_STACK_V7_STARTER_C0.1", "log_loss"],
            ],
            "plus_player_relief_index": [
                bullpen_2025.loc["LOGIT_STACK_V7_PLUS_BULLPEN_C0.01", "log_loss"],
                bullpen_2026.loc["LOGIT_STACK_V7_PLUS_BULLPEN_C0.01", "log_loss"],
            ],
        }
    )

    fig, ax = plt.subplots(figsize=(10, 4.2))
    for idx, row in bullpen.iterrows():
        ax.plot(
            [row["starter_stack"], row["plus_player_relief_index"]],
            [idx, idx],
            marker="o",
            linewidth=2.5,
        )
        delta = row["plus_player_relief_index"] - row["starter_stack"]
        ax.text(
            float(row["starter_stack"]) - 0.00012,
            idx - 0.12,
            f"{row['starter_stack']:.6f}",
            ha="right",
            fontsize=9,
        )
        ax.text(
            float(row["plus_player_relief_index"]) + 0.00012,
            idx - 0.12,
            f"{row['plus_player_relief_index']:.6f}",
            ha="left",
            fontsize=9,
        )
        ax.text(
            (float(row["starter_stack"]) + float(row["plus_player_relief_index"])) / 2,
            idx + 0.18,
            f"worse by {delta:+.6f}",
            ha="center",
            fontsize=9,
        )
    ax.set_yticks(range(len(bullpen)), bullpen["evaluation"])
    ax.set_ylim(1.45, -0.45)
    ax.set_xlim(0.6665, 0.6758)
    ax.set_xlabel("Log loss (lower is better)")
    ax.set_title("Player-level relief-pitcher index was tested and not retained", pad=18)
    ax.grid(axis="x", alpha=0.25)
    fig.text(
        0.5,
        0.01,
        (
            "Historical V8 protocol; displayed separately from V12 to avoid an "
            "invalid cross-protocol ranking."
        ),
        ha="center",
        fontsize=9,
    )
    plt.tight_layout(rect=(0, 0.08, 1, 0.98))
    plt.savefig(FIGURES / "relief_index_negative_result.png", dpi=200, bbox_inches="tight")
    plt.close()


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
