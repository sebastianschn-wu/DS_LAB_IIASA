"""Read and write the results CSV (resumable: completed rows are skipped next run)."""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

from constants import (
    COL_FALLBACK_REASON,
    COL_MODEL_ERROR,
    COL_OMIT_REASON,
    COL_SHEET_ROW,
    COL_SOURCE_USED,
    COMPLETE_SOURCES,
    CSV_ENCODING,
    IDENTITY_COLUMNS,
    MODEL_FIELDS,
    RUN_COLUMNS,
)


def result_columns() -> list[str]:
    return IDENTITY_COLUMNS + RUN_COLUMNS + MODEL_FIELDS


def load_existing(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    with path.open(newline="", encoding=CSV_ENCODING) as handle:
        return {row[COL_SHEET_ROW]: row for row in csv.DictReader(handle) if row.get(COL_SHEET_ROW)}


def is_complete(row: dict[str, str]) -> bool:
    return row.get(COL_SOURCE_USED) in COMPLETE_SOURCES and not row.get(COL_MODEL_ERROR)


def write_results(path: Path, rows: list[dict[str, str]]) -> None:
    """Write atomically (temp file + rename), so an interrupted run never leaves a broken CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", newline="", encoding=CSV_ENCODING) as handle:
        writer = csv.DictWriter(handle, fieldnames=result_columns(), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def run_summary(rows: list[dict[str, str]]) -> str:
    """Short overview: how many rows used the document, the summary, or were left out."""
    sources = Counter(row.get(COL_SOURCE_USED, "") or "-" for row in rows)
    reasons = Counter(
        row.get(COL_FALLBACK_REASON) or row.get(COL_OMIT_REASON)
        for row in rows
        if row.get(COL_FALLBACK_REASON) or row.get(COL_OMIT_REASON)
    )
    errors = sum(1 for row in rows if row.get(COL_MODEL_ERROR))
    lines = [f"Rows in output: {len(rows)}"]
    lines += [f"  source_used={name}: {count}" for name, count in sorted(sources.items())]
    lines += [f"  reason={name}: {count}" for name, count in sorted(reasons.items())]
    lines.append(f"  model errors: {errors}")
    return "\n".join(lines)
