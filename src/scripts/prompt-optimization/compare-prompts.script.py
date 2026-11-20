#!/usr/bin/env python3
"""Compare two coding runs (e.g. prompt v1 vs. v2) on the same test policies.

Answers Elina's two questions for the prompt change:
  * Did the targeted errors go down?          -> pattern counts before/after
  * Did the change break anything that was    -> per field: how many policies went
    correct before?                              wrong -> right (fixed) and
                                                 right -> wrong (broken)

Only policies present in both runs are compared (default: the test split).
Accuracy, exact match and macro-F1 use the benchmark's metric code.

Usage:
    python src/scripts/prompt-optimization/compare-prompts.script.py \\
        --before "v1=results/baseline/retrieved_v1_test.csv" \\
        --after "v2=results/baseline/retrieved_v2_test.csv"

Outputs (results/prompt-optimization/comparison/):
    prompt_comparison.md   tables for the report
    prompt_comparison.csv  per field: accuracy, macro-F1, fixed, broken
    flips.csv              every policy/field whose correctness changed (for inspection)
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
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from patterns import PATTERNS, extra_instrument_types, labels  # noqa: E402

BENCHMARK = REPO_ROOT / "src" / "scripts" / "benchmark" / "benchmark.script.py"
DEFAULT_GOLD = REPO_ROOT / "data" / "processed" / "gold_standard_clean.csv"
DEFAULT_SPLIT_FILE = REPO_ROOT / "src" / "resources" / "train_test_split.csv"
DEFAULT_OUT = REPO_ROOT / "results" / "prompt-optimization" / "comparison"
KEY = "sheet_row"
CORE_FIELDS = ["Policy_scope", "Broad_method", "Specific_method", "Value_chain_focus",
               "Instrument_broad", "Instrument_type"]
PATTERN_FIELDS = ["Policy_scope", "Value_chain_focus", "Instrument_broad", "Instrument_type", "Target_type"]


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


def parse_run(text: str) -> tuple[str, Path]:
    if "=" not in text:
        raise argparse.ArgumentTypeError("use NAME=PATH")
    name, path = text.split("=", 1)
    return name.strip(), Path(path.strip())


def correct(bench, field: str, gold, pred) -> bool:
    if field in bench.MULTI_FIELDS:
        return bench.label_set(gold) == bench.label_set(pred)
    return bench.single_label(gold) == bench.single_label(pred)


def field_metrics(bench, frame: pd.DataFrame) -> pd.DataFrame:
    bench.subsets = lambda f: {"all": f}
    fields, _, _ = bench.field_tables(frame)
    return fields.set_index("field")


def pattern_counts(frame: pd.DataFrame) -> dict[str, float]:
    counts = {key: 0 for key in PATTERNS}
    extra = 0
    n_types = 0
    for _, row in frame.iterrows():
        gold = {f: row[f"{f}_gold"] for f in PATTERN_FIELDS}
        pred = {f: row[f"{f}_pred"] for f in PATTERN_FIELDS}
        for key, spec in PATTERNS.items():
            counts[key] += int(spec["test"](gold, pred))
        extra += extra_instrument_types(gold, pred)
        n_types += len(labels(pred["Instrument_type"]))
    counts["extra_instrument_types"] = extra
    counts["mean_instrument_types"] = n_types / len(frame) if len(frame) else 0.0
    return counts


def compare(bench, before, after, gold: Path, only_split: str | None, split_file: Path):
    (name_a, path_a), (name_b, path_b) = before, after
    frame_a = bench.load(path_a, gold, only_split, split_file)
    frame_b = bench.load(path_b, gold, only_split, split_file)
    common = sorted(set(frame_a[KEY]) & set(frame_b[KEY]), key=int)
    dropped = (len(frame_a) - len(common), len(frame_b) - len(common))
    if any(dropped):
        print(f"Comparing the {len(common)} policies present in both runs "
              f"(left out: {dropped[0]} only in {name_a}, {dropped[1]} only in {name_b}).")
    frame_a = frame_a[frame_a[KEY].isin(common)].sort_values(KEY, key=lambda s: s.astype(int)).reset_index(drop=True)
    frame_b = frame_b[frame_b[KEY].isin(common)].sort_values(KEY, key=lambda s: s.astype(int)).reset_index(drop=True)

    metrics_a, metrics_b = field_metrics(bench, frame_a), field_metrics(bench, frame_b)
    input_type = frame_b["input_type"] if "input_type" in frame_b.columns else frame_b[bench.SOURCE]

    rows, flips = [], []
    for field in bench.SINGLE_FIELDS + bench.MULTI_FIELDS:
        ok_a = [correct(bench, field, g, p) for g, p in zip(frame_a[f"{field}_gold"], frame_a[f"{field}_pred"])]
        ok_b = [correct(bench, field, g, p) for g, p in zip(frame_b[f"{field}_gold"], frame_b[f"{field}_pred"])]
        fixed = sum(not a and b for a, b in zip(ok_a, ok_b))
        broken = sum(a and not b for a, b in zip(ok_a, ok_b))
        rows.append({
            "field": field,
            "core": field in CORE_FIELDS,
            f"accuracy_{name_a}": metrics_a.at[field, "accuracy"],
            f"accuracy_{name_b}": metrics_b.at[field, "accuracy"],
            "accuracy_change": metrics_b.at[field, "accuracy"] - metrics_a.at[field, "accuracy"],
            f"macro_f1_{name_a}": metrics_a.at[field, "macro_f1"],
            f"macro_f1_{name_b}": metrics_b.at[field, "macro_f1"],
            "fixed": fixed,
            "broken": broken,
        })
        for i, (a, b) in enumerate(zip(ok_a, ok_b)):
            if a != b:
                flips.append({
                    KEY: frame_b.at[i, KEY],
                    "Jurisdiction": frame_b.at[i, "Jurisdiction"],
                    "Document_full_title": frame_b.at[i, "Document_full_title"],
                    "input_type": input_type.iloc[i],
                    "field": field,
                    "change": "fixed" if b else "broken",
                    "gold": frame_b.at[i, f"{field}_gold"],
                    f"model_{name_a}": frame_a.at[i, f"{field}_pred"],
                    f"model_{name_b}": frame_b.at[i, f"{field}_pred"],
                })

    by_input = []
    for kind in sorted(set(input_type)):
        mask = (input_type == kind).values
        means = []
        for frame in (frame_a, frame_b):
            part = frame[mask]
            scores = [sum(correct(bench, f, g, p) for g, p in zip(part[f"{f}_gold"], part[f"{f}_pred"])) / len(part)
                      for f in CORE_FIELDS]
            means.append(sum(scores) / len(scores))
        by_input.append({"input_type": kind, "n": int(mask.sum()), name_a: means[0], name_b: means[1]})

    patterns = {"before": pattern_counts(frame_a), "after": pattern_counts(frame_b)}
    return pd.DataFrame(rows), pd.DataFrame(flips), pd.DataFrame(by_input), patterns, len(common)


def pct(value) -> str:
    return "–" if pd.isna(value) else f"{value:.0%}"


def signed_pp(value) -> str:
    return f"{value * 100:+.0f} pp"


def markdown(table, flips, by_input, patterns, n, name_a, name_b, only_split) -> str:
    core = table[table.core]
    mean_a, mean_b = core[f"accuracy_{name_a}"].mean(), core[f"accuracy_{name_b}"].mean()
    lines = [
        f"# Prompt comparison: {name_a} vs. {name_b}",
        "",
        f"- Policies compared: {n} ({'the ' + only_split + ' split' if only_split else 'all rows in both runs'})",
        f"- Run: {date.today().isoformat()}",
        f"- Mean exact agreement over the six core fields: **{pct(mean_a)} → {pct(mean_b)}** "
        f"({signed_pp(mean_b - mean_a)})",
        f"- Field results that changed: {int(table.fixed.sum())} fixed (wrong → right), "
        f"{int(table.broken.sum())} broken (right → wrong)",
        "",
        "## Per field",
        "",
        f"| Field | Accuracy {name_a} | Accuracy {name_b} | Change | Macro-F1 {name_a} | Macro-F1 {name_b} "
        f"| Fixed | Broken |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for _, row in table.iterrows():
        label = f"**{row.field}**" if row.core else row.field
        lines.append(
            f"| {label} | {pct(row[f'accuracy_{name_a}'])} | {pct(row[f'accuracy_{name_b}'])} | "
            f"{signed_pp(row.accuracy_change)} | {row[f'macro_f1_{name_a}']:.2f} | {row[f'macro_f1_{name_b}']:.2f} | "
            f"{row.fixed} | {row.broken} |")
    lines += ["", "Core fields in bold.", "", "## Targeted error patterns", "",
              f"| Pattern | {name_a} | {name_b} |", "|---|---|---|"]
    for key, spec in PATTERNS.items():
        if key == "P4_instrument_type":
            continue
        lines.append(f"| {spec['title']} | {patterns['before'][key]} | {patterns['after'][key]} |")
    lines.append(f"| Instrument types listed that experts did not code (total) | "
                 f"{patterns['before']['extra_instrument_types']} | {patterns['after']['extra_instrument_types']} |")
    lines.append(f"| Instrument types per policy (mean; experts ≈ 1.3) | "
                 f"{patterns['before']['mean_instrument_types']:.1f} | {patterns['after']['mean_instrument_types']:.1f} |")
    lines += ["", "## Mean core agreement by input type", "",
              f"| Input type | n | {name_a} | {name_b} |", "|---|---|---|---|"]
    for _, row in by_input.iterrows():
        lines.append(f"| {row.input_type} | {row.n} | {pct(row[name_a])} | {pct(row[name_b])} |")
    if len(flips):
        broken = flips[flips.change == "broken"].groupby("field").size().sort_values(ascending=False)
        if len(broken):
            lines += ["", "## Where the change introduced new errors", "",
                      ", ".join(f"{field}: {count}" for field, count in broken.items()),
                      "", "Details per policy: `flips.csv`."]
    lines += [
        "",
        "## How to read this",
        "",
        f"- Both runs coded the same {n} policies from the same retrieved text; only the prompt differs.",
        "- With about 100 policies, a change of a few percentage points can be noise. The fixed/broken counts "
        "show whether a gain is a real shift or errors moving around.",
        "- The prompt rules were derived from the train split only, so this test comparison is independent.",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--before", type=parse_run, required=True, help="NAME=PATH of the original run")
    parser.add_argument("--after", type=parse_run, required=True, help="NAME=PATH of the revised run")
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--only-split", choices=["train", "test", "none"], default="test")
    parser.add_argument("--split-file", type=Path, default=DEFAULT_SPLIT_FILE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    only_split = None if args.only_split == "none" else args.only_split
    bench = load_script(BENCHMARK, "benchmark_script")
    table, flips, by_input, patterns, n = compare(bench, args.before, args.after, args.gold, only_split,
                                                  args.split_file)
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    table.to_csv(out / "prompt_comparison.csv", index=False, encoding="utf-8-sig")
    flips.to_csv(out / "flips.csv", index=False, encoding="utf-8-sig")
    text = markdown(table, flips, by_input, patterns, n, args.before[0], args.after[0], only_split)
    (out / "prompt_comparison.md").write_text(text, encoding="utf-8")
    print(text)
    print(f"Wrote {out}/")


if __name__ == "__main__":
    main()
