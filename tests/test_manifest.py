from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def test_manifest_contains_only_portable_repository_artifacts():
    manifest = pd.read_csv(ROOT / "artifacts/RESEARCH_MANIFEST_SHA256.csv")
    paths = manifest["relative_path"].astype(str)
    assert not paths.duplicated().any()
    assert not paths.str.contains(r"(?:^|/)[^/]+\.egg-info(?:/|$)", regex=True).any()
    assert not paths.str.contains(r"(?:^|/)__pycache__(?:/|$)", regex=True).any()
    assert not paths.str.contains(r"(?:^|/)\.pytest_cache(?:/|$)", regex=True).any()
    assert not paths.str.startswith("reports/reproduced/").any()
    assert "src/fifteenpick_prediction/reproduction.py" in set(paths)
    assert "reports/frozen/V12_REPRODUCIBILITY_AND_LEAKAGE_AUDIT.json" in set(paths)
    assert "reports/frozen/V11_1_REPRODUCIBILITY_AUDIT.json" in set(paths)
    assert "data/schema/modeling_dataset_schema.csv" in set(paths)
