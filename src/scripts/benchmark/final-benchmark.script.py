#!/usr/bin/env python3
"""Final benchmark: several coding runs on exactly the same policies, all metrics in one report.

What it reports (everything we agreed on for the report):

* Same policies for every run: only policies present in all runs, restricted to a
  rows file (default: the test policies with a document,
  ``src/resources/document_policies_test.csv``) or a split.
* Per field: exact agreement (accuracy), macro-F1 (class imbalance); for multi-label
  fields also exact set match, mean Jaccard and micro-F1.
* Mean of the six core fields with a 95% bootstrap confidence interval
  (resampling policies), so small differences can be judged against noise.
* Paired comparison with the first run: difference with 95% CI, and per field how
  many policies went wrong -> right (fixed) and right -> wrong (broken).
* Results per input type (policy text / webpage description / title only) and per
  context method (full text / keyword excerpt / RAG).
* The four systematic error patterns (Framework->Instrument, Cross-cutting->Demand,
  Other->Regulatory, extra instrument types).
* Output quality: labels outside the codebook (validation notes), model errors.
* CDR_link free text: ROUGE-1, ROUGE-L, BLEU (optional BERTScore).

Usage:
    python src/scripts/benchmark/final-benchmark.script.py \\
        --run "v1=results/baseline/retrieved_v1_test.csv" \\
        --run "v2=results/baseline/retrieved_v2_test.csv" \\
        --run "v2 + RAG=results/baseline/retrieved_v2_rag_document_policies_test.csv"

Outputs (results/benchmark/final/): final_benchmark.md, field_metrics.csv, paired.csv,
per_policy.csv, label_metrics.csv, final_core_fields.png
"""

from __future__ import annotations

import argparse
import importlib.util
import random
import sys
from datetime import date
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = _SCRIPT_DIR.parents[2]
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))
PROMPT_DIR = REPO_ROOT / "src" / "scripts" / "prompt-optimization"
if str(PROMPT_DIR) not in sys.path:
    sys.path.append(str(PROMPT_DIR))

import pandas as pd  # noqa: E402

from constants import (  # noqa: E402
    COLOR_GRID,
    COLOR_SURFACE,
    COLOR_TEXT,
    COLOR_TEXT_SECONDARY,
    CORE_FIELDS,
    CSV_ENCODING,
    DEFAULT_GOLD,
    DEFAULT_SPLIT_FILE,
    KEY,
    MULTI_FIELDS,
    RUN_COLORS,
    SINGLE_FIELDS,
    SOURCE,
)
from metrics import label_set, single_label  # noqa: E402
from patterns import PATTERNS, extra_instrument_types, labels as pattern_labels  # noqa: E402

DEFAULT_ROWS = REPO_ROOT / "src" / "resources" / "document_policies_test.csv"
DEFAULT_OUT = REPO_ROOT / "results" / "benchmark" / "final"
ALL = "all"
PATTERN_FIELDS = ["Policy_scope", "Value_chain_focus", "Instrument_broad", "Instrument_type", "Target_type"]
INPUT_NAMES = {
    "policy_text": "policy text",
    "webpage_description": "webpage description",
    "no_text": "title only",
    "expert_summary": "expert summary",
    "document": "document (first loop)",
    "summary": "expert summary (first loop)",
}
CONTEXT_NAMES = {"no": "full text", "yes": "keyword excerpt", "rag": "RAG", "rag+summary": "RAG + own summary",
                 "rag+intro": "RAG + introduction"}


def load_benchmark():
    spec = importlib.util.spec_from_file_location("benchmark_script", _SCRIPT_DIR / "benchmark.script.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_run(text: str) -> tuple[str, Path]:
    if "=" not in text:
        raise argparse.ArgumentTypeError("use NAME=PATH")
    name, path = text.split("=", 1)
    return name.strip(), Path(path.strip())


def read_rows(path: Path) -> set[str]:
    table = pd.read_csv(path, dtype=str, encoding=CSV_ENCODING)
    return set(table[KEY].astype(str).str.strip())


def correct(field: str, gold, pred) -> bool:
    if field in MULTI_FIELDS:
        return label_set(gold) == label_set(pred)
    return single_label(gold) == single_label(pred)


def bootstrap_ci(values: list[float], draws: int, seed: int) -> tuple[float, float]:
    if not values:
        return float("nan"), float("nan")
    rng = random.Random(seed)
    n = len(values)
    means = sorted(sum(values[rng.randrange(n)] for _ in range(n)) / n for _ in range(draws))
    return means[int(0.025 * draws)], means[min(draws - 1, int(0.975 * draws))]


# ------------------------------------------------------------------ loading
def load_runs(bench, runs, gold: Path, rows: set[str] | None, only_split: str | None, split_file: Path):
    frames = {}
    for name, path in runs:
        frame = bench.load(path, gold, only_split, split_file)
        if rows is not None:
            frame = frame[frame[KEY].isin(rows)]
        frames[name] = frame
    common = set.intersection(*(set(f[KEY]) for f in frames.values()))
    for name, frame in frames.items():
        left_out = len(frame) - len(common)
        if left_out:
            print(f"{name}: {left_out} policies left out (not in every run)")
        frame = frame[frame[KEY].isin(common)].copy()
        frame = frame.sort_values(KEY, key=lambda s: s.astype(int)).reset_index(drop=True)
        frame["_input"] = (frame["input_type"] if "input_type" in frame.columns else frame[SOURCE]).fillna("")
        frame["_context"] = frame["excerpted"].fillna("no") if "excerpted" in frame.columns else "n/a"
        for field in SINGLE_FIELDS + MULTI_FIELDS:
            frame[f"{field}_ok"] = [correct(field, g, p) for g, p in zip(frame[f"{field}_gold"], frame[f"{field}_pred"])]
        frame["core_score"] = frame[[f"{f}_ok" for f in CORE_FIELDS]].mean(axis=1)
        frames[name] = frame
    return frames, len(common)


# ------------------------------------------------------------------ metrics
def field_metrics(bench, frames) -> tuple[pd.DataFrame, pd.DataFrame]:
    bench.subsets = lambda f: {ALL: f}
    tables, label_tables = [], []
    for name, frame in frames.items():
        fields, labels, _ = bench.field_tables(frame)
        fields.insert(0, "run", name)
        labels.insert(0, "run", name)
        tables.append(fields)
        label_tables.append(labels)
    return pd.concat(tables, ignore_index=True), pd.concat(label_tables, ignore_index=True)


def paired(frames, reference: str, draws: int, seed: int) -> pd.DataFrame:
    base = frames[reference]
    rows = []
    for name, frame in frames.items():
        if name == reference:
            continue
        diff = list(frame["core_score"] - base["core_score"])
        low, high = bootstrap_ci(diff, draws, seed)
        record = {"run": name, "reference": reference, "core_change": sum(diff) / len(diff),
                  "ci_low": low, "ci_high": high}
        for field in SINGLE_FIELDS + MULTI_FIELDS:
            record[f"{field}_fixed"] = int((~base[f"{field}_ok"] & frame[f"{field}_ok"]).sum())
            record[f"{field}_broken"] = int((base[f"{field}_ok"] & ~frame[f"{field}_ok"]).sum())
        record["core_fixed"] = sum(record[f"{f}_fixed"] for f in CORE_FIELDS)
        record["core_broken"] = sum(record[f"{f}_broken"] for f in CORE_FIELDS)
        rows.append(record)
    return pd.DataFrame(rows)


def pattern_counts(frame) -> dict:
    counts = {key: 0 for key in PATTERNS}
    extra = n_types = 0
    for _, row in frame.iterrows():
        gold = {f: row[f"{f}_gold"] for f in PATTERN_FIELDS}
        pred = {f: row[f"{f}_pred"] for f in PATTERN_FIELDS}
        for key, spec in PATTERNS.items():
            counts[key] += int(spec["test"](gold, pred))
        extra += extra_instrument_types(gold, pred)
        n_types += len(pattern_labels(pred["Instrument_type"]))
    counts["extra_types"] = extra
    counts["types_per_policy"] = n_types / len(frame) if len(frame) else 0.0
    counts["types_per_policy_gold"] = (sum(len(pattern_labels(v)) for v in frame["Instrument_type_gold"]) / len(frame)
                                       if len(frame) else 0.0)
    return counts


def quality(frame) -> dict:
    notes = frame["validation_notes"].fillna("") if "validation_notes" in frame.columns else pd.Series([""] * len(frame))
    errors = frame["model_error"].fillna("") if "model_error" in frame.columns else pd.Series([""] * len(frame))
    return {"labels_outside_codebook": int(notes.str.contains("not in the codebook list", case=False).sum()),
            "rows_with_validation_notes": int(notes.ne("").sum()),
            "model_errors": int(errors.ne("").sum())}


def grouped(frames, column: str) -> pd.DataFrame:
    rows = []
    for name, frame in frames.items():
        for value, part in frame.groupby(column):
            rows.append({"run": name, "group": value, "n": len(part), "core": part["core_score"].mean()})
    return pd.DataFrame(rows)


def text_metrics(bench, frames, use_bertscore: bool, model: str) -> pd.DataFrame:
    bench.subsets = lambda f: {ALL: f}
    tables = []
    for name, frame in frames.items():
        try:
            table = bench.text_table(frame, use_bertscore, model)
        except ImportError as exc:
            print(f"Text metrics skipped ({exc}); pip install sacrebleu")
            return pd.DataFrame()
        if not table.empty:
            table.insert(0, "run", name)
            tables.append(table)
    return pd.concat(tables, ignore_index=True) if tables else pd.DataFrame()


# ------------------------------------------------------------------- output
def pct(value) -> str:
    return "–" if pd.isna(value) else f"{value:.0%}"


def pp(value, digits: int = 0) -> str:
    return "–" if pd.isna(value) else f"{value * 100:+.{digits}f} pp"


def markdown(frames, n, fields, pairs, patterns, qualities, by_input, by_context, text, cis, scope, draws) -> str:
    names = list(frames)
    reference = names[0]
    lines = [
        "# Final benchmark",
        "",
        f"- Policies: **{n}**, the same for every run ({scope})",
        f"- Runs: {', '.join(f'`{name}`' for name in names)}; comparisons are against `{reference}`",
        f"- Run: {date.today().isoformat()}; confidence intervals: 95% bootstrap over policies ({draws} draws)",
        "",
        "## Headline: mean exact agreement over the six core fields",
        "",
        "| Run | Core mean | 95% CI | Change vs. " + reference + " | 95% CI of change | Fixed | Broken |",
        "|---|---|---|---|---|---|---|",
    ]
    for name in names:
        mean = frames[name]["core_score"].mean()
        low, high = cis[name]
        if name == reference:
            lines.append(f"| {name} | **{pct(mean)}** | {pct(low)}–{pct(high)} | – | – | – | – |")
            continue
        row = pairs[pairs.run == name].iloc[0]
        significant = row.ci_low > 0 or row.ci_high < 0
        lines.append(f"| {name} | **{pct(mean)}** | {pct(low)}–{pct(high)} | {pp(row.core_change)}"
                     f"{' *' if significant else ''} | {pp(row.ci_low, 1)} to {pp(row.ci_high, 1)} | "
                     f"{row.core_fixed} | {row.core_broken} |")
    lines += ["", "\\* the 95% CI of the change does not include 0. Fixed/broken: core field results that went "
              "wrong → right / right → wrong compared with the reference run.", ""]

    lines += ["## Per field: exact agreement", "", "| Field | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]
    for field in SINGLE_FIELDS + MULTI_FIELDS:
        cells = []
        for name in names:
            hit = fields[(fields.run == name) & (fields.field == field)]
            cells.append(pct(hit["accuracy"].iloc[0]) if len(hit) else "–")
        label = f"**{field}**" if field in CORE_FIELDS else field
        lines.append(f"| {label} | " + " | ".join(cells) + " |")
    lines += ["", "Core fields in bold. Multi-label fields: the whole label set must match.", ""]

    lines += ["## Per field: macro-F1 (single) and Jaccard / micro-F1 (multi-label)", "",
              "| Field | Metric | " + " | ".join(names) + " |", "|---|---|" + "---|" * len(names)]
    for field in SINGLE_FIELDS + MULTI_FIELDS:
        metrics_for = ["macro_f1"] if field in SINGLE_FIELDS else ["jaccard", "micro_f1", "macro_f1"]
        for metric in metrics_for:
            cells = []
            for name in names:
                hit = fields[(fields.run == name) & (fields.field == field)]
                cells.append(f"{hit[metric].iloc[0]:.2f}" if len(hit) and metric in hit else "–")
            lines.append(f"| {field} | {metric} | " + " | ".join(cells) + " |")
    lines.append("")

    if len(pairs):
        lines += ["## Fixed / broken per field (vs. " + reference + ")", "",
                  "| Field | " + " | ".join(f"{r} fixed / broken" for r in pairs.run) + " |",
                  "|---|" + "---|" * len(pairs)]
        for field in SINGLE_FIELDS + MULTI_FIELDS:
            cells = [f"{row[f'{field}_fixed']} / {row[f'{field}_broken']}" for _, row in pairs.iterrows()]
            lines.append(f"| {field} | " + " | ".join(cells) + " |")
        lines.append("")

    lines += ["## Systematic error patterns", "", "| Pattern | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]
    for key, spec in PATTERNS.items():
        if key == "P4_instrument_type":
            continue
        lines.append(f"| {spec['title']} | " + " | ".join(str(patterns[n][key]) for n in names) + " |")
    lines.append("| Instrument types not in expert coding (total) | "
                 + " | ".join(str(patterns[n]["extra_types"]) for n in names) + " |")
    gold_types = patterns[reference]["types_per_policy_gold"]
    lines.append(f"| Instrument types per policy (experts: {gold_types:.1f}) | "
                 + " | ".join(f"{patterns[n]['types_per_policy']:.1f}" for n in names) + " |")
    lines.append("")

    lines += ["## Core mean by input type", "", "| Input | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]
    for group in sorted(set(by_input.group)):
        cells = []
        for name in names:
            hit = by_input[(by_input.run == name) & (by_input.group == group)]
            cells.append(f"{pct(hit.core.iloc[0])} (n={hit.n.iloc[0]})" if len(hit) else "–")
        lines.append(f"| {INPUT_NAMES.get(group, group)} | " + " | ".join(cells) + " |")
    lines.append("")

    if by_context is not None and len(by_context):
        lines += ["## Core mean by context method (how the document was given to the model)", "",
                  "| Run | " + " | ".join(sorted(set(CONTEXT_NAMES.get(g, g) for g in by_context.group))) + " |"]
        groups = sorted(set(by_context.group), key=lambda g: CONTEXT_NAMES.get(g, g))
        lines[-1] = "| Run | " + " | ".join(CONTEXT_NAMES.get(g, g) for g in groups) + " |"
        lines.append("|---|" + "---|" * len(groups))
        for name in names:
            cells = []
            for group in groups:
                hit = by_context[(by_context.run == name) & (by_context.group == group)]
                cells.append(f"{pct(hit.core.iloc[0])} (n={hit.n.iloc[0]})" if len(hit) else "–")
            lines.append(f"| {name} | " + " | ".join(cells) + " |")
        lines.append("")

    lines += ["## Output quality", "", "| | " + " | ".join(names) + " |", "|---|" + "---|" * len(names),
              "| Rows with labels outside the codebook | " + " | ".join(str(qualities[n]["labels_outside_codebook"]) for n in names) + " |",
              "| Rows with any validation note | " + " | ".join(str(qualities[n]["rows_with_validation_notes"]) for n in names) + " |",
              "| Model errors (no answer) | " + " | ".join(str(qualities[n]["model_errors"]) for n in names) + " |", ""]

    if len(text):
        has_bert = "bertscore_f1" in text.columns
        lines += ["## CDR_link free text (similarity to the expert sentence)", "",
                  "| Run | n | ROUGE-1 F1 | ROUGE-L F1 | BLEU (corpus)" + (" | BERTScore F1" if has_bert else "") + " |",
                  "|---|---|---|---|---" + ("|---" if has_bert else "") + "|"]
        for _, row in text.iterrows():
            lines.append(f"| {row.run} | {row.n} | {row.rouge1_f1:.3f} | {row.rougeL_f1:.3f} | {row.bleu_corpus:.1f}"
                         + (f" | {row.bertscore_f1:.3f}" if has_bert else "") + " |")
        lines += ["", "Word-overlap metrics are only supplementary: the same content can be phrased differently.", ""]

    lines += [
        "## How to read this",
        "",
        "- All runs are scored on the same policies against the same expert coding (gold standard).",
        "- The confidence intervals show how much the result could move with a different sample of policies of "
        "the same size. A change whose interval includes 0 is not distinguishable from noise.",
        "- Fixed/broken counts show whether a gain is a real shift or errors moving between policies.",
        "- Prompt v2 rules were derived from the train split only; these policies are from the test split.",
    ]
    return "\n".join(lines) + "\n"


def chart(fields, frames, cis, path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    names = list(frames)[: len(RUN_COLORS)]
    data = fields[fields.field.isin(CORE_FIELDS)].pivot(index="field", columns="run", values="accuracy")
    data = data.reindex(CORE_FIELDS)[names].iloc[::-1]
    group, height = 0.8, 0.8 / len(names)
    fig, ax = plt.subplots(figsize=(7.6, 1.2 + 0.6 * len(CORE_FIELDS) * max(1, len(names) / 2)), dpi=200)
    fig.patch.set_facecolor(COLOR_SURFACE)
    ax.set_facecolor(COLOR_SURFACE)
    for index, (name, color) in enumerate(zip(names, RUN_COLORS)):
        offset = group / 2 - height * (index + 0.5)
        values = data[name].fillna(0).values
        positions = [i + offset for i in range(len(data))]
        mean = frames[name]["core_score"].mean()
        low, high = cis[name]
        ax.barh(positions, values, height=height * 0.9, color=color,
                label=f"{name}: {mean:.0%} (95% CI {low:.0%}–{high:.0%})")
        for y, value in zip(positions, values):
            ax.text(value + 0.01, y, f"{value:.0%}", va="center", fontsize=7, color=COLOR_TEXT_SECONDARY)
    ax.set_yticks(range(len(data)))
    ax.set_yticklabels(data.index, fontsize=8.5, color=COLOR_TEXT)
    ax.set_xlim(0, 1.1)
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.tick_params(axis="x", labelsize=8, colors=COLOR_TEXT_SECONDARY, length=0)
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="x", color=COLOR_GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_title("Exact agreement with expert coding per core field (legend: mean of core fields)",
                 loc="left", fontsize=10, color=COLOR_TEXT, pad=12 + 12 * len(names))
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=1, frameon=False, fontsize=7.5,
              labelcolor=COLOR_TEXT, handlelength=1.2, borderaxespad=0.2)
    fig.tight_layout()
    fig.savefig(path, facecolor=COLOR_SURFACE)
    plt.close(fig)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run", type=parse_run, action="append", required=True,
                        help="NAME=PATH of a results CSV; repeat. The first run is the reference.")
    parser.add_argument("--rows", type=Path, default=DEFAULT_ROWS,
                        help="CSV with sheet_row: evaluate only these policies (default: test policies with a "
                             "document). Use --rows none for all policies of the split.")
    parser.add_argument("--only-split", choices=["train", "test", "none"], default="test")
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--split-file", type=Path, default=DEFAULT_SPLIT_FILE)
    parser.add_argument("--bootstrap", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--bertscore", action="store_true", help="Also BERTScore for CDR_link (pip install bert-score)")
    parser.add_argument("--bertscore-model", default="roberta-large")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    rows = None if str(args.rows).lower() == "none" else read_rows(args.rows)
    only_split = None if args.only_split == "none" else args.only_split
    scope = (f"policies in `{args.rows.name}`" if rows is not None else "all policies") + (
        f", {only_split} split" if only_split else "")
    bench = load_benchmark()
    frames, n = load_runs(bench, args.run, args.gold, rows, only_split, args.split_file)
    if n == 0:
        raise SystemExit("No policy is in every run (check --rows / --only-split).")

    fields, label_table = field_metrics(bench, frames)
    pairs = paired(frames, list(frames)[0], args.bootstrap, args.seed)
    cis = {name: bootstrap_ci(list(frame["core_score"]), args.bootstrap, args.seed) for name, frame in frames.items()}
    patterns = {name: pattern_counts(frame) for name, frame in frames.items()}
    qualities = {name: quality(frame) for name, frame in frames.items()}
    by_input = grouped(frames, "_input")
    by_context = grouped(frames, "_context") if any(f["_context"].ne("n/a").any() for f in frames.values()) else None
    text = text_metrics(bench, frames, args.bertscore, args.bertscore_model)

    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    fields.to_csv(out / "field_metrics.csv", index=False, encoding=CSV_ENCODING)
    label_table.to_csv(out / "label_metrics.csv", index=False, encoding=CSV_ENCODING)
    pairs.to_csv(out / "paired.csv", index=False, encoding=CSV_ENCODING)
    per_policy = frames[list(frames)[0]][[KEY, "Jurisdiction", "Document_full_title", "_input"]].copy()
    for name, frame in frames.items():
        per_policy[f"core_{name}"] = frame["core_score"].values
    per_policy.to_csv(out / "per_policy.csv", index=False, encoding=CSV_ENCODING)
    text_md = markdown(frames, n, fields, pairs, patterns, qualities, by_input, by_context, text, cis, scope,
                       args.bootstrap)
    (out / "final_benchmark.md").write_text(text_md, encoding="utf-8")
    try:
        chart(fields, frames, cis, out / "final_core_fields.png")
    except ImportError:
        print("Chart skipped (pip install matplotlib)")
    print(text_md)
    print(f"Wrote {out}/")


if __name__ == "__main__":
    main()
