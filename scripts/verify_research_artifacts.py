#!/usr/bin/env python3
"""Fail-closed verification of linked audits, reproduced results, and artifact hashes."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd

from build_manifest import collect_files
from fifteenpick_prediction.audit import build_v11_audit, build_v12_audit
from fifteenpick_prediction.validation import validate_modeling_dataset

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "derived" / "V12_MODELING_DATASET.csv"
FROZEN = ROOT / "reports" / "frozen"
REPRODUCED = ROOT / "reports" / "reproduced"
MODELS = ROOT / "models" / "frozen"
MANIFEST = ROOT / "artifacts" / "RESEARCH_MANIFEST_SHA256.csv"

EXPECTED = {
    ("CV_SELECTED", "BATTER_PLUS_STARTER_INDICES"): {
        "log_loss": 0.6673896327657686,
        "brier": 0.2370343931469793,
        "roc_auc": 0.6315679733110926,
        "accuracy": 0.59375,
    },
    ("BEST_DEVELOPMENT", "BATTER_PLUS_STARTER_INDICES"): {
        "log_loss": 0.6661347844671042,
        "brier": 0.23649786240497755,
        "roc_auc": 0.635274766008711,
        "accuracy": 0.5961538461538461,
    },
    ("BEST_DEVELOPMENT", "BASELINE_NO_PLAYER_INDICES"): {
        "log_loss": 0.6839421791444644,
        "brier": 0.24531296565005117,
        "roc_auc": 0.575780743211936,
        "accuracy": 0.5432692307692307,
    },
    ("BEST_DEVELOPMENT", "CONSTANT_0_5"): {
        "log_loss": 0.6931471805599453,
        "brier": 0.25,
        "roc_auc": 0.5,
        "accuracy": 0.5240384615384616,
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_manifest() -> dict[str, int]:
    manifest = pd.read_csv(MANIFEST)
    paths = manifest["relative_path"].astype(str)
    if paths.duplicated().any():
        raise SystemExit("FAIL duplicate path in SHA256 manifest")
    forbidden = paths.str.contains(
        r"(?:^|/)(?:__pycache__|\.pytest_cache|\.ruff_cache|[^/]+\.egg-info)(?:/|$)",
        regex=True,
    )
    if forbidden.any():
        raise SystemExit(f"FAIL non-portable manifest entries: {paths[forbidden].tolist()}")

    manifest_paths = set(paths)
    expected_paths = {
        path.relative_to(ROOT).as_posix()
        for path in collect_files()
    }
    missing_from_manifest = sorted(expected_paths - manifest_paths)
    unexpected_manifest_entries = sorted(manifest_paths - expected_paths)
    if missing_from_manifest or unexpected_manifest_entries:
        raise SystemExit(
            "FAIL manifest coverage mismatch: "
            f"missing={missing_from_manifest}, unexpected={unexpected_manifest_entries}"
        )

    for row in manifest.itertuples(index=False):
        path = ROOT / row.relative_path
        if not path.is_file():
            raise SystemExit(f"FAIL missing manifest file: {row.relative_path}")
        if path.stat().st_size != int(row.size_bytes):
            raise SystemExit(f"FAIL size mismatch: {row.relative_path}")
        if sha256(path) != row.sha256:
            raise SystemExit(f"FAIL SHA mismatch: {row.relative_path}")
    return {"entries_verified": int(len(manifest))}


def verify_reproduction() -> dict[str, int]:
    with tempfile.TemporaryDirectory() as directory:
        target = Path(directory)
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "reproduce_core_results.py"),
                "--data",
                str(DATA),
                "--output-dir",
                str(target),
                "--bootstrap-reps",
                "20000",
            ],
            check=True,
        )
        results = pd.read_csv(target / "player_index_ablation.csv").set_index(
            ["protocol", "model"]
        )
        for key, metrics in EXPECTED.items():
            for metric, expected in metrics.items():
                actual = float(results.loc[key, metric])
                if not math.isclose(actual, expected, rel_tol=0, abs_tol=1e-12):
                    raise SystemExit(
                        f"FAIL reproduction {key} {metric}: {actual} != {expected}"
                    )

        generated_dataset_audit = json.loads(
            (target / "dataset_validation.json").read_text(encoding="utf-8")
        )
        committed_dataset_audit = json.loads(
            (REPRODUCED / "dataset_validation.json").read_text(encoding="utf-8")
        )
        if generated_dataset_audit != committed_dataset_audit:
            raise SystemExit("FAIL reproduced dataset_validation.json is stale")

        bootstrap = pd.read_csv(target / "player_index_ablation_bootstrap.csv").set_index(
            "protocol"
        )
        expected_boot = {
            "CV_SELECTED": (
                -0.0161267523384099,
                -0.0320656558113629,
                0.0004246983726018,
                0.97165,
            ),
            "BEST_DEVELOPMENT": (
                -0.0178073946773601,
                -0.0331539101136537,
                -0.0021136959864507,
                0.9869,
            ),
        }
        for protocol, expected in expected_boot.items():
            actual = bootstrap.loc[protocol]
            for column, value in zip(
                [
                    "delta_log_loss_indices_minus_baseline",
                    "ci_low",
                    "ci_high",
                    "improvement_probability",
                ],
                expected,
                strict=True,
            ):
                if not math.isclose(float(actual[column]), value, rel_tol=0, abs_tol=1e-12):
                    raise SystemExit(f"FAIL bootstrap {protocol} {column}")
    return {"metric_specifications_verified": len(EXPECTED), "bootstrap_protocols_verified": 2}


def _relative_evidence(payload: dict[str, object]) -> dict[str, object]:
    evidence = payload.get("evidence")
    if isinstance(evidence, dict):
        payload["evidence"] = {
            key: Path(str(value)).resolve().relative_to(ROOT).as_posix()
            for key, value in evidence.items()
        }
    return payload


def verify_linked_audits() -> dict[str, int]:
    frame = pd.read_csv(DATA)
    expected_dataset = validate_modeling_dataset(frame)
    expected_v12 = _relative_evidence(
        build_v12_audit(
            data_path=DATA,
            predictions_path=FROZEN / "V12_2026_ALL_PREDICTIONS.csv",
            cv_model_path=MODELS / "V12_CV_SELECTED_MODEL_REFIT_2024_2025.joblib",
            development_model_path=MODELS / "V12_2026_BEST_OBSERVED_RECENT720_MODEL.joblib",
            model_schema_path=FROZEN / "V12_MODEL_SCHEMA.json",
            selection_decision_path=FROZEN / "V12_MODEL_SELECTION_DECISION.json",
        )
    )
    expected_v11 = _relative_evidence(
        build_v11_audit(
            comparison_path=FROZEN / "V11_1_ROBUST_CANDIDATE_COMPARISON.csv",
            bootstrap_path=FROZEN / "V11_1_ROBUST_CANDIDATE_BOOTSTRAP.csv",
            decision_path=FROZEN / "V11_1_PROSPECTIVE_CANDIDATE_DECISION.json",
            model_schema_path=FROZEN / "V11_1_PROSPECTIVE_MODEL_SCHEMA.json",
            formula_path=FROZEN / "V11_1_SELECTED_BATTER_INCOME_FORMULA.json",
            model_path=MODELS / "V11_1_PROSPECTIVE_REFIT_MODEL_2024_2025.joblib",
        )
    )

    audits = {
        REPRODUCED / "dataset_validation.json": expected_dataset,
        FROZEN / "V12_REPRODUCIBILITY_AND_LEAKAGE_AUDIT.json": expected_v12,
        FROZEN / "V11_1_REPRODUCIBILITY_AUDIT.json": expected_v11,
    }
    stale = []
    for path, expected in audits.items():
        committed = json.loads(path.read_text(encoding="utf-8"))
        if committed != expected:
            stale.append(path.relative_to(ROOT).as_posix())
    if stale:
        raise SystemExit(
            f"FAIL stale linked audit files: {stale}; run scripts/rebuild_linked_audits.py"
        )
    return {"linked_audits_verified": len(audits)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-manifest", action="store_true")
    args = parser.parse_args()

    linked = verify_linked_audits()
    reproduction = verify_reproduction()
    manifest = {"skipped": 1} if args.skip_manifest else verify_manifest()
    print(
        json.dumps(
            {
                "status": "PASS",
                "linked_audits": linked,
                "reproduction": reproduction,
                "manifest": manifest,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
