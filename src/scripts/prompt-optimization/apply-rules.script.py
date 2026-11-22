#!/usr/bin/env python3
"""Apply the deterministic coding rules (``rules.py``) to a finished coding run.

No model call: reads a results CSV, sets the rule-based values, writes a new CSV
with the suffix ``_rules`` and a column ``rules_applied``. First prints how well
each rule agrees with the expert coding on the train split.

Usage:
    python src/scripts/prompt-optimization/apply-rules.script.py results/baseline/retrieved_v2_test.csv
    # -> results/baseline/retrieved_v2_test_rules.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from rules import RULES_COLUMN, apply_rules, check_on_gold  # noqa: E402

DEFAULT_GOLD = REPO_ROOT / "data" / "processed" / "gold_standard_clean.csv"
DEFAULT_SPLIT_FILE = REPO_ROOT / "src" / "resources" / "train_test_split.csv"
ENCODING = "utf-8-sig"
TITLE = "Document_full_title"


def read_csv(path: Path) -> tuple[list[dict], list[str]]:
    with path.open(newline="", encoding=ENCODING) as handle:
        reader = csv.DictReader(handle)
        return list(reader), list(reader.fieldnames or [])


def main(argv: list[str] | None = None) -> Path:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("predictions", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--split-file", type=Path, default=DEFAULT_SPLIT_FILE)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    if args.gold.exists() and args.split_file.exists():
        gold, _ = read_csv(args.gold)
        split, _ = read_csv(args.split_file)
        train = {r["sheet_row"].strip() for r in split if r["split"].strip() == "train"}
        print("Evidence on the train split (expert coding):")
        for line in check_on_gold([r for r in gold if r["sheet_row"].strip() in train]):
            print("  " + line)

    rows, columns = read_csv(args.predictions)
    if RULES_COLUMN not in columns:
        columns.append(RULES_COLUMN)
    counts: Counter = Counter()
    out_rows = []
    for row in rows:
        if row.get("model_error"):
            row[RULES_COLUMN] = ""
            out_rows.append(row)
            continue
        new, applied = apply_rules(row, row.get(TITLE, ""))
        new[RULES_COLUMN] = "; ".join(applied)
        counts.update(applied)
        out_rows.append(new)

    output = args.output or args.predictions.with_name(args.predictions.stem + "_rules.csv")
    with output.open("w", newline="", encoding=ENCODING) as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(out_rows)
    print(f"Rows changed: R1 (NDC) {counts['R1_ndc']}, R2 (Framework instrument type) {counts['R2_framework']} "
          f"of {len(rows)}")
    print(f"Wrote {output}")
    return output


if __name__ == "__main__":
    main()
