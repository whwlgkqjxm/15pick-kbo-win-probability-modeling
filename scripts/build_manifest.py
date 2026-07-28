#!/usr/bin/env python3
"""Build the SHA256 manifest for immutable research artifacts."""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts" / "RESEARCH_MANIFEST_SHA256.csv"
# Regenerated outputs are intentionally excluded. They are verified by schema,
# exact identifiers, and numeric tolerance in verify_research_artifacts.py.
INCLUDED_ROOTS = [
    ROOT / "configs",
    ROOT / "src",
    ROOT / "scripts",
    ROOT / "data" / "derived",
    ROOT / "data" / "schema",
    ROOT / "models" / "frozen",
    ROOT / "reports" / "frozen",
    ROOT / "research" / "authoritative",
    ROOT / "research_records",
    ROOT / "tests",
    ROOT / ".github" / "workflows",
]
INCLUDED_FILES = [
    ROOT / "pyproject.toml",
    ROOT / "requirements-reproduce-lock.txt",
    ROOT / "requirements-research-lock.txt",
    ROOT / "Makefile",
]
EXCLUDED_DIRECTORY_NAMES = {
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "build",
    "dist",
}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def is_portable_artifact(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    if any(part in EXCLUDED_DIRECTORY_NAMES for part in relative.parts):
        return False
    if any(part.endswith(".egg-info") for part in relative.parts):
        return False
    return path.suffix not in EXCLUDED_SUFFIXES


def collect_files() -> list[Path]:
    files = {
        path
        for base in INCLUDED_ROOTS
        if base.exists()
        for path in base.rglob("*")
        if path.is_file() and is_portable_artifact(path)
    }
    files.update(
        path for path in INCLUDED_FILES if path.is_file() and is_portable_artifact(path)
    )
    return sorted(files)


def main() -> None:
    files = collect_files()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["relative_path", "size_bytes", "sha256"])
        writer.writeheader()
        for path in files:
            writer.writerow(
                {
                    "relative_path": path.relative_to(ROOT).as_posix(),
                    "size_bytes": path.stat().st_size,
                    "sha256": sha256(path),
                }
            )
    print(f"PASS: wrote {len(files)} entries to {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
