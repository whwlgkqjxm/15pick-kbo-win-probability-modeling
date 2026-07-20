#!/usr/bin/env python3
"""Refit the primary feature-group ablation on a local modeling dataset."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from mypick_rq1.metrics import probability_metrics
from mypick_rq1.modeling import build_l2_logistic

CONVENTIONAL = [
    "elo_diff",
    "prior_win_pct_diff",
    "prior_run_diff_per_game_diff",
    "prior_rank_advantage",
    "bullpen_strength_diff",
    "PS_R20_RA_G_diff",
]
STARTER = [
    "K10_starter_value_diff",
    "K10_starter_count_diff",
    "K10_starter_reliability_diff",
    "K10_both_starters_covered",
]
BATTER = ["mean", "coverage", "count_mean", "coverage_min"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument(
        "--protocol",
        choices=["cv-selected", "best-development"],
        default="best-development",
    )
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    frame = pd.read_csv(args.data)
    frame["game_date"] = pd.to_datetime(frame["game_date"].astype(str))
    target = "home_win"

    if args.protocol == "best-development":
        C = 0.1
        cutoff = pd.Timestamp("2026-03-28")
        train = frame.loc[frame["game_date"] < cutoff].sort_values("game_date").tail(720)
    else:
        C = 0.03
        train = frame.loc[frame["game_date"] < pd.Timestamp("2026-03-28")].copy()

    test = frame.loc[
        (frame["game_date"] >= pd.Timestamp("2026-03-28"))
        & (frame["game_date"] <= pd.Timestamp("2026-07-09"))
    ].copy()

    groups = {
        "NO_PLAYER_INCOME": CONVENTIONAL,
        "STARTER_INCOME_ONLY": CONVENTIONAL + STARTER,
        "BATTER_INCOME_ONLY": CONVENTIONAL + BATTER,
        "ALL_PLAYER_INCOME": CONVENTIONAL + STARTER + BATTER,
    }

    rows = []
    for model_id, features in groups.items():
        model = build_l2_logistic(C=C)
        model.fit(train[features], train[target])
        probability = model.predict_proba(test[features])[:, 1]
        rows.append(
            {
                "protocol": args.protocol,
                "model": model_id,
                "feature_count": len(features),
                **probability_metrics(test[target], probability),
            }
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(args.output, index=False)
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
