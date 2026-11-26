#!/usr/bin/env python3
"""Benchmark coding runs separately for each input type.

Uses the metric code of ``src/scripts/benchmark`` (same accuracy, macro-F1,
exact-match and Jaccard definitions) but groups rows by ``input_type`` instead of
document vs. summary:

    policy_text          coded from the policy text itself
    webpage_description  coded from a webpage that describes the policy
    no_text              nothing retrieved, coded from title and context only
    expert_summary       coded from the expert CDR_link summary (control run)

Runs without an ``input_type`` column (e.g. the original first loop) are grouped
by their ``source_used`` value instead.

Usage:
    python src/scripts/baseline/evaluate.script.py \\
        --run "baseline=results/baseline/retrieved_v1_test.csv" \\
        --run "summary only=results/baseline/summary_v1_test.csv" \\
        --run "first loop=results/first_loop_coding.csv"

Outputs (results/baseline/evaluation/): evaluation.md, evaluation.csv
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from datetime import date
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
BENCHMARK = REPO_ROOT / "src" / "scripts" / "benchmark" / "benchmark.script.py"
DEFAULT_GOLD = REPO_ROOT / "data" / "processed" / "gold_standard_clean.csv"
DEFAULT_SPLIT_FILE = REPO_ROOT / "src" / "resources" / "train_test_split.csv"
DEFAULT_OUT = REPO_ROOT / "results" / "baseline" / "evaluation"

CORE_FIELDS = ["Policy_scope", "Broad_method", "Specific_method", "Value_chain_focus",
               "Instrument_broad", "Instrument_type"]
SUBSET_ALL = "all"
INPUT_ORDER = ["policy_text", "webpage_description", "no_text", "expert_summary", "document", "summary"]
INPUT_NAMES = {
    "policy_text": "policy text",
    "webpage_description": "webpage description",
    "no_text": "title only (nothing retrieved)",
    "expert_summary": "expert summary",
    "document": "document (first loop)",
    "summary": "expert summary (first-loop fallback)",
}
GROUP = "_group"


def load_script(path: Path, name: str):
    saved = {key: sys.modules.pop(key) for key in ("constants", "metrics") if key in sys.modules}
    sys.path.insert(0, str(path.parent))
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(path.parent))
        for key in ("constants", "metrics"):
            sys.modules.pop(key, None)
        sys.modules.update(saved)
    return module


def by_input_type(frame: pd.DataFrame) -> dict[str, pd.DataFrame]:
    groups = {SUBSET_ALL: frame}
    for name in INPUT_ORDER:
        part = frame[frame[GROUP] == name]
        if len(part):
            groups[name] = part
    return groups


def parse_run(text: str) -> tuple[str, Path]:
    if "=" not in text:
        raise argparse.ArgumentTypeError("use NAME=PATH")
    name, path = text.split("=", 1)
    return name.strip(), Path(path.strip())


def evaluate(bench, runs, gold: Path, only_split: str | None, split_file: Path) -> pd.DataFrame:
    bench.subsets = by_input_type  # group by input type instead of document/summary
    tables = []
    for name, path in runs:
        frame = bench.load(path, gold, only_split, split_file)
        if "input_type" in frame.columns:
            frame[GROUP] = frame["input_type"].fillna("").replace("", "unknown")
        else:
            frame[GROUP] = frame[bench.SOURCE].fillna("")
        if "model_error" in frame.columns:
            failed = frame["model_error"].fillna("").ne("").sum()
            if failed:
                print(f"Warning: {name}: {failed} rows with a model error are scored as empty predictions.")
        fields, _, _ = bench.field_tables(frame)
        fields.insert(0, "run", name)
        counts = frame[GROUP].value_counts()
        fields["n_subset"] = fields["subset"].map(lambda s: len(frame) if s == SUBSET_ALL else int(counts.get(s, 0)))
        tables.append(fields)
    return pd.concat(tables, ignore_index=True)


def pct(value) -> str:
    return "–" if pd.isna(value) else f"{value:.0%}"


def markdown(table: pd.DataFrame, run_names: list[str], only_split: str | None) -> str:
    lines = [
        "# Benchmark by input type",
        "",
        f"- Policies: {'the ' + only_split + ' split' if only_split else 'all rows of each run'}",
        f"- Run: {date.today().isoformat()}",
        "- Exact agreement with the expert coding (multi-label fields: the whole label set must match).",
        "",
    ]
    for run in run_names:
        part = table[table.run == run]
        subsets = [s for s in [SUBSET_ALL] + INPUT_ORDER if s in set(part.subset)]
        sizes = {s: int(part[part.subset == s]["n_subset"].iloc[0]) for s in subsets}
        lines += [f"## {run}", "",
                  "| Field | " + " | ".join(f"{INPUT_NAMES.get(s, s)} (n={sizes[s]})" for s in subsets) + " |",
                  "|---|" + "---|" * len(subsets)]
        for field in table.field.unique():
            cells = []
            for s in subsets:
                hit = part[(part.field == field) & (part.subset == s)]
                cells.append(pct(hit["accuracy"].iloc[0]) if len(hit) else "–")
            lines.append(f"| {field} | " + " | ".join(cells) + " |")
        means = []
        for s in subsets:
            core = part[(part.subset == s) & (part.field.isin(CORE_FIELDS))]["accuracy"]
            means.append(f"**{pct(core.mean())}**")
        lines.append("| **Mean of 6 core fields** | " + " | ".join(means) + " |")
        f1 = []
        for s in subsets:
            core = part[(part.subset == s) & (part.field.isin(CORE_FIELDS))]["macro_f1"]
            f1.append(f"{core.mean():.2f}" if len(core) else "–")
        lines.append("| Mean macro-F1, core fields | " + " | ".join(f1) + " |")
        lines.append("")
    lines += [
        "## How to read this",
        "",
        "- `policy text` is the main result: the model saw the policy itself and no expert-written text.",
        "- `webpage description` rows saw only a page about the policy; `title only` rows saw no text at all.",
        "- `expert summary` (control run) is not an independent test: the summary is expert interpretation.",
        "- Groups with few policies (n < 20) are noisy; a difference of a few percentage points means little.",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run", type=parse_run, action="append", required=True)
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--only-split", choices=["train", "test", "none"], default="test")
    parser.add_argument("--split-file", type=Path, default=DEFAULT_SPLIT_FILE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    only_split = None if args.only_split == "none" else args.only_split
    bench = load_script(BENCHMARK, "benchmark_script")
    table = evaluate(bench, args.run, args.gold, only_split, args.split_file)
    names = [name for name, _ in args.run]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    table.to_csv(args.output_dir / "evaluation.csv", index=False, encoding="utf-8-sig")
    text = markdown(table, names, only_split)
    (args.output_dir / "evaluation.md").write_text(text, encoding="utf-8")
    print(text)
    print(f"Wrote {args.output_dir}/")


if __name__ == "__main__":
    main()
