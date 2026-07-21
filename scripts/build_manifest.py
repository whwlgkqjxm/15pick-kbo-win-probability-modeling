#!/usr/bin/env python3
"""Build the repository research-artifact SHA256 manifest."""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts" / "RESEARCH_MANIFEST_SHA256.csv"
INCLUDED_ROOTS = [
    ROOT / "configs",
    ROOT / "src",
    ROOT / "scripts",
    ROOT / "data" / "derived",
    ROOT / "models" / "frozen",
    ROOT / "reports" / "frozen",
    ROOT / "research" / "authoritative",
    ROOT / "research_records",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    files = sorted(
        path
        for base in INCLUDED_ROOTS
        for path in base.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.suffix not in {".pyc", ".pyo"}
    )
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
    print(f"wrote {len(files)} entries to {OUTPUT}")


if __name__ == "__main__":
    main()
