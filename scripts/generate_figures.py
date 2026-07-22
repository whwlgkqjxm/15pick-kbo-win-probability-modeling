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
    data = data.set_index("model")

    baseline_log_loss = float(data.loc["BASELINE_NO_PLAYER_INDICES", "log_loss"])
    models = pd.DataFrame(
        {
            "display": [
                "Batter index",
                "Starting-pitcher index",
                "Batter + starting-pitcher indices",
            ],
            "log_loss": [
                data.loc["BATTER_INDEX_ONLY", "log_loss"],
                data.loc["STARTER_INDEX_ONLY", "log_loss"],
                data.loc["BATTER_PLUS_STARTER_INDICES", "log_loss"],
            ],
        }
    )
    models["improvement"] = baseline_log_loss - models["log_loss"]

    bootstrap = pd.read_csv(REPRODUCED / "player_index_ablation_bootstrap.csv")
    combined_bootstrap = bootstrap.loc[
        bootstrap["protocol"].eq("BEST_DEVELOPMENT")
    ].iloc[0]
    combined_ci_low = -float(combined_bootstrap["ci_high"])
    combined_ci_high = -float(combined_bootstrap["ci_low"])

    fig, ax = plt.subplots(figsize=(10.8, 5.2))
    y_positions = list(range(len(models)))
    colors = ["#4C78A8", "#F58518", "#54A24B"]
    bars = ax.barh(
        y_positions,
        models["improvement"],
        color=colors,
        height=0.58,
    )
    bars[-1].set_hatch("//")
    bars[-1].set_edgecolor("#2F4B35")
    bars[-1].set_linewidth(1.0)

    combined_value = float(models.iloc[-1]["improvement"])
    ax.errorbar(
        combined_value,
        y_positions[-1],
        xerr=[
            [combined_value - combined_ci_low],
            [combined_ci_high - combined_value],
        ],
        fmt="none",
        ecolor="#222222",
        elinewidth=1.8,
        capsize=5,
        capthick=1.8,
        zorder=4,
    )

    ax.set_yticks(y_positions, models["display"])
    ax.invert_yaxis()
    ax.axvline(0, color="#333333", linewidth=1.0)
    ax.set_xlim(0, max(combined_ci_high * 1.08, float(models["improvement"].max()) * 1.55))
    ax.set_xlabel(
        "Log-loss improvement over the conventional pregame model (higher is better)"
    )
    ax.set_title(
        "Incremental predictive value of role-specific player indices",
        pad=22,
        fontweight="bold",
    )
    ax.text(
        0.0,
        1.035,
        (
            f"Reference model Log loss: {baseline_log_loss:.6f}  |  "
            "2026 development evaluation: 416 games"
        ),
        transform=ax.transAxes,
        fontsize=9.5,
        color="#444444",
        va="bottom",
    )
    ax.grid(axis="x", alpha=0.22)
    ax.set_axisbelow(True)

    label_offset = ax.get_xlim()[1] * 0.012
    for index, (bar, row) in enumerate(zip(bars, models.itertuples(index=False), strict=True)):
        value = float(row.improvement)
        label_x = min(value + label_offset, ax.get_xlim()[1] * 0.86)
        label_y = bar.get_y() + bar.get_height() / 2
        if index == len(models) - 1:
            label_y -= 0.38
        ax.text(
            label_x,
            label_y,
            f"+{value:.6f}  |  Log loss {float(row.log_loss):.6f}",
            va="center",
            fontsize=9.3,
            fontweight="bold" if index == len(models) - 1 else "normal",
        )

    fig.text(
        0.5,
        0.015,
        (
            "Combined model 95% paired date-cluster bootstrap interval for improvement: "
            f"+{combined_ci_low:.6f} to +{combined_ci_high:.6f}."
        ),
        ha="center",
        fontsize=9,
        color="#444444",
    )
    plt.tight_layout(rect=(0, 0.06, 1, 0.97))
    plt.savefig(FIGURES / "main_model_comparison.png", dpi=220, bbox_inches="tight")
    plt.close()

    bullpen_2025 = pd.read_csv(
        ROOT / "research_records" / "key_results" / "V8_2025_PREDICTION_APPLICATION_RESULTS.csv"
    ).set_index("method")
    bullpen_2026 = pd.read_csv(
        ROOT / "research_records" / "key_results" / "V8_2026_POSTHOC_APPLICATION_RESULTS.csv"
    ).set_index("method")
    bullpen = pd.DataFrame(
        {
            "evaluation": [
                "2025 temporal OOF (698 games)\n0.669483 → 0.674253",
                "2026 post-hoc (416 games)\n0.667785 → 0.668898",
            ],
            "reference": [
                bullpen_2025.loc["LOGIT_STACK_V7_STARTER_C0.1", "log_loss"],
                bullpen_2026.loc["LOGIT_STACK_V7_STARTER_C0.1", "log_loss"],
            ],
            "plus_relief_index": [
                bullpen_2025.loc["LOGIT_STACK_V7_PLUS_BULLPEN_C0.01", "log_loss"],
                bullpen_2026.loc["LOGIT_STACK_V7_PLUS_BULLPEN_C0.01", "log_loss"],
            ],
        }
    )
    bullpen["delta"] = bullpen["plus_relief_index"] - bullpen["reference"]

    fig, ax = plt.subplots(figsize=(10.8, 4.6))
    y_positions = list(range(len(bullpen)))
    bars = ax.barh(
        y_positions,
        bullpen["delta"],
        color=["#E45756", "#F28E2B"],
        height=0.5,
    )
    ax.set_yticks(y_positions, bullpen["evaluation"])
    ax.invert_yaxis()
    ax.axvline(0, color="#333333", linewidth=1.1)
    ax.set_xlim(0, float(bullpen["delta"].max()) * 1.52)
    ax.set_xlabel(
        "Increase in Log loss after adding the relief-pitcher index (positive is worse)"
    )
    ax.set_title(
        "Player-level relief-pitcher index did not improve prediction",
        pad=22,
        fontweight="bold",
    )
    ax.text(
        0.0,
        1.04,
        "V8 evaluation results; each bar shows the performance change after adding the index.",
        transform=ax.transAxes,
        fontsize=9.5,
        color="#444444",
        va="bottom",
    )
    ax.grid(axis="x", alpha=0.22)
    ax.set_axisbelow(True)

    label_offset = ax.get_xlim()[1] * 0.015
    for bar, row in zip(bars, bullpen.itertuples(index=False), strict=True):
        delta = float(row.delta)
        ax.text(
            delta + label_offset,
            bar.get_y() + bar.get_height() / 2,
            f"Δ +{delta:.6f}  (worse)",
            va="center",
            fontsize=9.5,
            fontweight="bold",
        )

    fig.text(
        0.5,
        0.015,
        (
            "Reported separately because the historical V8 and V12 protocols are not "
            "directly comparable."
        ),
        ha="center",
        fontsize=9,
        color="#444444",
    )
    plt.tight_layout(rect=(0, 0.07, 1, 0.96))
    plt.savefig(FIGURES / "relief_index_negative_result.png", dpi=220, bbox_inches="tight")
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
