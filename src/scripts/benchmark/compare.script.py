#!/usr/bin/env python3
"""Compare several coding runs (e.g. zero-shot, one-shot, few-shot) on the same test policies.

Each run is a results CSV from the first loop or the few-shot script. All runs are
evaluated against the gold standard on the test part of the train/test split
(``src/resources/train_test_split.csv``), so few-shot examples (taken from the train
part) never appear in the evaluation. The zero-shot run is the existing first-loop
output; only its test policies are used.

Usage:
    python src/scripts/benchmark/compare.script.py \\
        --run "zero-shot=results/first_loop_coding.csv" \\
        --run "one-shot=results/shots1_test_coding.csv" \\
        --run "three-shot=results/shots3_test_coding.csv"

Outputs (``results/benchmark/comparison/``):
    comparison.md                table per field and run + short reading guide
    comparison.csv               the same numbers as CSV
    comparison_core_fields.png   chart: agreement per core field and run (document rows)
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from datetime import date
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

import pandas as pd  # noqa: E402

from constants import (  # noqa: E402
    COLOR_GRID,
    COLOR_SURFACE,
    COLOR_TEXT,
    COLOR_TEXT_SECONDARY,
    CORE_FIELDS,
    CSV_ENCODING,
    DEFAULT_COMPARISON_DIR,
    DEFAULT_GOLD,
    DEFAULT_SPLIT_FILE,
    MULTI_FIELDS,
    OUT_COMPARISON_FIGURE,
    OUT_COMPARISON_SUMMARY,
    OUT_COMPARISON_TABLE,
    RUN_COLORS,
    SINGLE_FIELDS,
    SOURCE,
    SUBSET_ALL,
    SUBSET_DOCUMENT,
)


def load_benchmark_module():
    spec = importlib.util.spec_from_file_location("benchmark_script", _SCRIPT_DIR / "benchmark.script.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_run(text: str) -> tuple[str, Path]:
    if "=" not in text:
        raise argparse.ArgumentTypeError("use NAME=PATH, e.g. zero-shot=results/shots0_test_coding.csv")
    name, path = text.split("=", 1)
    return name.strip(), Path(path.strip())


def evaluate_runs(runs, gold: Path, only_split: str | None, split_file: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    bench = load_benchmark_module()
    field_rows, text_rows = [], []
    for name, path in runs:
        print(f"\n== {name}: {path}")
        frame = bench.load(path, gold, only_split, split_file)
        fields, _, _ = bench.field_tables(frame)
        fields.insert(0, "run", name)
        n_doc = int((frame[SOURCE] == SUBSET_DOCUMENT).sum())
        fields["n_policies"] = len(frame)
        fields["n_from_document"] = n_doc
        field_rows.append(fields)
        text = bench.text_table(frame, use_bertscore=False, bertscore_model="")
        if not text.empty:
            text.insert(0, "run", name)
            text_rows.append(text)
    return pd.concat(field_rows, ignore_index=True), (pd.concat(text_rows, ignore_index=True) if text_rows else pd.DataFrame())


def pct(value) -> str:
    return "–" if pd.isna(value) else f"{value:.0%}"


def comparison_markdown(fields: pd.DataFrame, text: pd.DataFrame, run_names: list[str], only_split: str | None) -> str:
    def value(run, field, subset):
        hit = fields[(fields.run == run) & (fields.field == field) & (fields.subset == subset)]
        return hit["accuracy"].iloc[0] if len(hit) else float("nan")

    lines = [
        "# Comparison of coding runs",
        "",
        f"- Evaluated on: {'the ' + only_split + ' split' if only_split else 'all policies in each run'}",
        f"- Run: {date.today().isoformat()}",
        "",
        "| Run | Policies | From document |",
        "|---|---|---|",
    ]
    for run in run_names:
        sub = fields[fields.run == run].iloc[0]
        lines.append(f"| {run} | {int(sub.n_policies)} | {int(sub.n_from_document)} |")

    for subset, title in [(SUBSET_DOCUMENT, "coded from the full document (main result)"),
                          (SUBSET_ALL, "all rows, including the summary fallback")]:
        lines += ["", f"## Exact agreement, {title}", "",
                  "| Field | " + " | ".join(run_names) + " |", "|---|" + "---|" * len(run_names)]
        for field in SINGLE_FIELDS + MULTI_FIELDS:
            lines.append(f"| {field} | " + " | ".join(pct(value(r, field, subset)) for r in run_names) + " |")
        means = [sum(value(r, f, subset) for f in CORE_FIELDS) / len(CORE_FIELDS) for r in run_names]
        lines.append("| **Mean of core fields** | " + " | ".join(f"**{pct(m)}**" for m in means) + " |")

    if not text.empty:
        lines += ["", "## CDR_link similarity (document rows, ROUGE-L F1)", "",
                  "| " + " | ".join(run_names) + " |", "|" + "---|" * len(run_names)]
        cells = []
        for run in run_names:
            hit = text[(text.run == run) & (text.subset == SUBSET_DOCUMENT)]
            cells.append(f"{hit['rougeL_f1'].iloc[0]:.3f}" if len(hit) else "–")
        lines.append("| " + " | ".join(cells) + " |")

    lines += [
        "",
        "## How to read this",
        "",
        "- Compare runs on the document rows; summary rows received the expert CDR_link sentence as input.",
        "- With about 100 test policies (and fewer document rows), differences of a few percentage points "
        "are within noise.",
        "- Few-shot examples come from the train split only, so no example policy is in the test set.",
    ]
    return "\n".join(lines) + "\n"


def comparison_figure(fields: pd.DataFrame, run_names: list[str], path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    if len(run_names) > len(RUN_COLORS):
        print(f"Chart shows the first {len(RUN_COLORS)} runs only.")
        run_names = run_names[: len(RUN_COLORS)]
    data = fields[(fields.subset == SUBSET_DOCUMENT) & (fields.field.isin(CORE_FIELDS))]
    table = data.pivot(index="field", columns="run", values="accuracy").reindex(CORE_FIELDS)[run_names].iloc[::-1]

    n = len(run_names)
    group = 0.8
    height = group / n
    fig, ax = plt.subplots(figsize=(7.4, 1.0 + 0.55 * len(CORE_FIELDS) * max(1, n / 2)), dpi=200)
    fig.patch.set_facecolor(COLOR_SURFACE)
    ax.set_facecolor(COLOR_SURFACE)
    for index, (run, color) in enumerate(zip(run_names, RUN_COLORS)):
        offset = group / 2 - height * (index + 0.5)
        values = table[run].fillna(0).values
        positions = [i + offset for i in range(len(table))]
        ax.barh(positions, values, height=height * 0.9, color=color, label=run)
        for y, value in zip(positions, values):
            ax.text(value + 0.01, y, f"{value:.0%}", va="center", fontsize=7, color=COLOR_TEXT_SECONDARY)
    ax.set_yticks(range(len(table)))
    ax.set_yticklabels(table.index, fontsize=8.5, color=COLOR_TEXT)
    ax.set_xlim(0, 1.08)
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.tick_params(axis="x", labelsize=8, colors=COLOR_TEXT_SECONDARY, length=0)
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="x", color=COLOR_GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_title("Exact agreement with expert coding per run (test policies, full document input)",
                 loc="left", fontsize=10, color=COLOR_TEXT, pad=26)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=n, frameon=False, fontsize=8,
              labelcolor=COLOR_TEXT, handlelength=1.2, borderaxespad=0.2)
    fig.tight_layout()
    fig.savefig(path, facecolor=COLOR_SURFACE)
    plt.close(fig)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run", type=parse_run, action="append", required=True,
                        help="NAME=PATH of a results CSV; repeat for every run")
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--only-split", choices=["train", "test", "none"], default="test",
                        help="Evaluate on this split (default: test). 'none' uses every row of each run.")
    parser.add_argument("--split-file", type=Path, default=DEFAULT_SPLIT_FILE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_COMPARISON_DIR)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    only_split = None if args.only_split == "none" else args.only_split
    run_names = [name for name, _ in args.run]
    fields, text = evaluate_runs(args.run, args.gold, only_split, args.split_file)

    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    fields.to_csv(out / OUT_COMPARISON_TABLE, index=False, encoding=CSV_ENCODING)
    (out / OUT_COMPARISON_SUMMARY).write_text(comparison_markdown(fields, text, run_names, only_split), encoding="utf-8")
    comparison_figure(fields, run_names, out / OUT_COMPARISON_FIGURE)

    core = fields[fields.field.isin(CORE_FIELDS)]
    print("\nMean exact agreement over the core fields:")
    print(core.pivot_table(index="run", columns="subset", values="accuracy", aggfunc="mean")
          .reindex(run_names).map(pct).to_string())
    print(f"\nWrote {out}/")


if __name__ == "__main__":
    main()
