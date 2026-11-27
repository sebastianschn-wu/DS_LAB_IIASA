#!/usr/bin/env python3
"""Is the difference between two coding runs real, or noise?

``compare.script.py`` reports agreement per run. It does not say whether a gap
between two runs is larger than chance, and it compares each run on its own
document rows -- which are not the same policies in every run, because a link
that fails in one run can succeed in the next.

This script closes both gaps:

1. It reports how far the ``document`` subsets of the runs overlap and
   evaluates them on the policies that were coded from the document in *every*
   run, so the comparison is like for like.
2. For every pair of runs it runs McNemar's test. Both runs code the same
   policies, so the predictions are paired: per field it counts the policies
   that only run A got right (b) and that only run B got right (c) and reports
   the exact two-sided binomial p-value on those discordant pairs. Policies
   both runs get right or wrong carry no information about the difference.

The pooled line adds the discordant pairs over all fields. Fields of one policy
are correlated, so read it as a direction, not as a clean test.

Usage:
    python src/scripts/benchmark/significance.script.py \
        --run "zero-shot=results/first_loop_coding.csv" \
        --run "one-shot=results/shots1_test_coding.csv" \
        --run "three-shot=results/shots3_test_coding.csv"
"""

from __future__ import annotations

import argparse
import math
import sys
from itertools import combinations
from pathlib import Path

import pandas as pd

_SCRIPT_DIR = str(Path(__file__).resolve().parent)
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from constants import (  # noqa: E402
    CORE_FIELDS,
    CSV_ENCODING,
    DEFAULT_COMPARISON_DIR,
    DEFAULT_GOLD,
    DEFAULT_SPLIT_FILE,
    GOLD_RENAME,
    KEY,
    MULTI_FIELDS,
    SINGLE_FIELDS,
    SOURCE,
    SUBSET_DOCUMENT,
)
from metrics import label_set, single_label  # noqa: E402

FIELDS = SINGLE_FIELDS + MULTI_FIELDS
OUTPUT_NAME = "significance.md"


def normalise(field: str, value) -> object:
    """The comparable form the benchmark uses: a set for multi-value fields."""
    return label_set(value) if field in MULTI_FIELDS else single_label(value)


def exact_binomial_two_sided(b: int, c: int) -> float:
    """Exact McNemar p-value for b and c discordant pairs (no SciPy needed).

    Why McNemar's test fits this comparison: every run codes the same policies
    with the same model, temperature and seed, so the predictions are paired.
    Policies that both runs get right, or both get wrong, say nothing about
    which run is better; only the discordant pairs carry information about the
    difference, and that is exactly what this test conditions on
    (McNemar 1947).

    Dietterich (1998) compares five tests for deciding whether one classifier
    outperforms another and finds McNemar's test the only one with an
    acceptable Type I error rate when each algorithm can be run only once --
    which is our situation. A run here is a full pass of a local LLM over the
    test split, so repeated resampling or 5x2 cross-validation is not
    affordable.

    The exact binomial form is used rather than the chi-square approximation
    because b + c is small for several fields (single digits), where the
    approximation is unreliable.

    References:
        McNemar, Q. (1947). Note on the sampling error of the difference
            between correlated proportions or percentages. Psychometrika,
            12(2), 153-157. https://doi.org/10.1007/BF02295996
        Dietterich, T. G. (1998). Approximate statistical tests for comparing
            supervised classification learning algorithms. Neural Computation,
            10(7), 1895-1923. https://doi.org/10.1162/089976698300017197
    """
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def read_runs(specs: list[str]) -> dict[str, Path]:
    runs: dict[str, Path] = {}
    for spec in specs:
        if "=" not in spec:
            raise SystemExit(f'--run needs the form "name=path", got: {spec}')
        name, path = spec.split("=", 1)
        runs[name.strip()] = Path(path.strip())
    if len(runs) < 2:
        raise SystemExit("Give at least two --run arguments.")
    return runs


def load_run(path: Path, gold: pd.DataFrame, keys: set[str] | None) -> tuple[dict, dict]:
    """Return (correct[field][sheet_row], source_used[sheet_row]) for one run."""
    if not path.exists():
        raise SystemExit(f"Run not found: {path}")
    pred = pd.read_csv(path, dtype=str, encoding=CSV_ENCODING)
    pred[KEY] = pred[KEY].astype(str).str.strip()
    if keys is not None:
        pred = pred[pred[KEY].isin(keys)]
    gold_by_key = gold.set_index(KEY)
    rows = [row for row in pred.to_dict("records") if row[KEY] in gold_by_key.index]
    correct = {
        field: {
            row[KEY]: normalise(field, row.get(field)) == normalise(field, gold_by_key.at[row[KEY], field])
            for row in rows
        }
        for field in FIELDS
    }
    return correct, {row[KEY]: row.get(SOURCE) for row in rows}


def agreement_table(correct: dict, runs: list[str], keys: list[str], title: str) -> list[str]:
    lines = [f"### {title} (n = {len(keys)})", "", "| Field | " + " | ".join(runs) + " |",
             "|---|" + "---|" * len(runs)]
    core = {run: [] for run in runs}
    for field in FIELDS:
        cells = []
        for run in runs:
            share = sum(correct[run][field][key] for key in keys) / len(keys) if keys else 0.0
            cells.append(f"{share:.0%}")
            if field in CORE_FIELDS:
                core[run].append(share)
        lines.append(f"| {field} | " + " | ".join(cells) + " |")
    means = [f"**{sum(core[run]) / len(core[run]):.0%}**" for run in runs]
    lines += ["| **Mean of core fields** | " + " | ".join(means) + " |", ""]
    return lines


def mcnemar_table(correct: dict, a: str, b: str, keys: list[str], title: str) -> list[str]:
    lines = [f"### McNemar: {a} vs {b} -- {title} (n = {len(keys)})", "",
             f"| Field | only {a} | only {b} | p (exact) |", "|---|---|---|---|"]
    total_b = total_c = 0
    for field in FIELDS:
        only_a = sum(correct[a][field][key] and not correct[b][field][key] for key in keys)
        only_b = sum(correct[b][field][key] and not correct[a][field][key] for key in keys)
        total_b += only_a
        total_c += only_b
        lines.append(f"| {field} | {only_a} | {only_b} | {exact_binomial_two_sided(only_a, only_b):.3f} |")
    pooled = exact_binomial_two_sided(total_b, total_c)
    lines += [f"| **All fields pooled** | **{total_b}** | **{total_c}** | **{pooled:.3f}** |", ""]
    return lines


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run", action="append", required=True, metavar='"name=path"')
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--split-file", type=Path, default=DEFAULT_SPLIT_FILE)
    parser.add_argument("--only-split", default="test", help="test, train or none. Default: test")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_COMPARISON_DIR)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    runs = read_runs(args.run)
    if not args.gold.exists():
        raise SystemExit(
            f"Gold standard not found: {args.gold}\n"
            "Create it first: python src/scripts/data-cleaning/data-cleaning.script.py"
        )
    gold = pd.read_csv(args.gold, dtype=str, encoding=CSV_ENCODING).rename(columns=GOLD_RENAME)
    gold[KEY] = gold[KEY].astype(str).str.strip()

    keys = None
    if args.only_split and args.only_split != "none":
        split = pd.read_csv(args.split_file, dtype=str, encoding=CSV_ENCODING)
        keys = set(split.loc[split["split"].str.strip() == args.only_split, KEY].str.strip())

    correct, source = {}, {}
    for name, path in runs.items():
        correct[name], source[name] = load_run(path, gold, keys)

    names = list(runs)
    paired = sorted(set.intersection(*[set(source[name]) for name in names]))
    documents = {name: {k for k, v in source[name].items() if v == SUBSET_DOCUMENT} for name in names}
    common = sorted(set.intersection(*documents.values()))
    union = set.union(*documents.values())

    lines = ["# Significance of the differences between runs", "",
             f"- Split: {args.only_split}", f"- Policies coded by every run: {len(paired)}", ""]
    lines += ["## Which policies were coded from the document", "",
              "| Run | document rows | summary rows |", "|---|---|---|"]
    for name in names:
        docs = len(documents[name])
        lines.append(f"| {name} | {docs} | {len(source[name]) - docs} |")
    lines += ["",
              f"Document rows common to every run: **{len(common)}** of {len(union)} policies that any run "
              "read as a document. A link that fails in one run can succeed in another, so the per-run "
              "document subsets are not the same policies. Only the common subset is a like-for-like "
              "comparison, and the difference in subset size says nothing about the prompt.", ""]
    if set(common) != union:
        extra = ", ".join(f"{name}: {sorted(documents[name] - set(common))}" for name in names
                          if documents[name] - set(common))
        lines += [f"Rows read as a document in some runs only -- {extra}", ""]

    lines += ["## Agreement", ""]
    lines += agreement_table(correct, names, common, "Common document rows (like for like)")
    lines += agreement_table(correct, names, paired, "All rows, including the summary fallback")

    lines += ["## Is the difference real?", "",
              "b and c are the discordant pairs: policies only one of the two runs got right. "
              "p is the exact two-sided binomial test on them.", ""]
    for a, b in combinations(names, 2):
        lines += mcnemar_table(correct, a, b, paired, "all rows")
    for a, b in combinations(names, 2):
        lines += mcnemar_table(correct, a, b, common, "common document rows")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    out = args.output_dir / OUTPUT_NAME
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
