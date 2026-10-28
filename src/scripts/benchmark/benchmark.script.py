#!/usr/bin/env python3
"""Benchmark LLM codings against the expert gold standard.

Compares the output of the first loop (``results/first_loop_coding.csv``) with the
cleaned gold standard (``data/processed/gold_standard_clean.csv``, created by
``src/scripts/data-cleaning``) and reports, for every codebook field:

- single-value fields: accuracy, macro-F1, accuracy on rows where the experts set a value
- multi-value fields: exact match, mean Jaccard, micro/macro precision, recall, F1
- CDR_link: ROUGE-1, ROUGE-L and BLEU (optional BERTScore)

Every result is split by ``source_used``: rows coded from the full document vs rows
coded from the expert CDR_link summary (fallback). The summary rows are not a fair
test, because the summary was written by the experts, so the document rows are the
main result.

Outputs (``results/benchmark/``):
    benchmark_summary.md   report-ready tables and findings
    accuracy_by_source.png chart for the report
    field_metrics.csv      one row per field and subset
    label_metrics.csv      precision/recall/F1 per label
    confusions.csv         most frequent gold -> model mix-ups
    text_metrics.csv       CDR_link similarity
    row_level.csv          gold vs model per policy (core fields)
    country_accuracy.csv   core accuracy per country

Usage:
    python src/scripts/data-cleaning/data-cleaning.script.py      # once, creates the gold standard
    python src/scripts/benchmark/benchmark.script.py
    python src/scripts/benchmark/benchmark.script.py --predictions results/test_david.csv --bertscore
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

_SCRIPT_DIR = str(Path(__file__).resolve().parent)
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

import pandas as pd  # noqa: E402

from constants import (  # noqa: E402
    COLOR_DOCUMENT,
    COLOR_GRID,
    COLOR_SUMMARY,
    COLOR_SURFACE,
    COLOR_TEXT,
    COLOR_TEXT_SECONDARY,
    CORE_FIELDS,
    CSV_ENCODING,
    DEFAULT_GOLD,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_PREDICTIONS,
    FALLBACK,
    GOLD_RENAME,
    KEY,
    MULTI_FIELDS,
    NONE_LABEL,
    OUT_CONFUSIONS,
    OUT_COUNTRIES,
    OUT_FIELD_METRICS,
    OUT_FIGURE,
    OUT_LABEL_METRICS,
    OUT_ROWS,
    OUT_SUMMARY,
    OUT_TEXT_METRICS,
    SINGLE_FIELDS,
    SOURCE,
    SUBSET_ALL,
    SUBSET_DOCUMENT,
    SUBSET_SUMMARY,
    SUBSETS,
    TEXT_FIELD,
)
from metrics import (  # noqa: E402
    confusions,
    fold,
    is_empty,
    label_set,
    multi_metrics,
    rouge_l_f1,
    rouge_n_f1,
    single_label,
    single_metrics,
)


# ---------------------------------------------------------------- loading
def load(predictions_path: Path, gold_path: Path) -> pd.DataFrame:
    if not gold_path.exists():
        raise SystemExit(
            f"Gold standard not found: {gold_path}\n"
            "Create it first: python src/scripts/data-cleaning/data-cleaning.script.py"
        )
    if not predictions_path.exists():
        raise SystemExit(f"Predictions not found: {predictions_path}")
    pred = pd.read_csv(predictions_path, dtype=str, encoding=CSV_ENCODING)
    gold = pd.read_csv(gold_path, dtype=str, encoding=CSV_ENCODING).rename(columns=GOLD_RENAME)
    for frame in (pred, gold):
        frame[KEY] = frame[KEY].astype(str).str.strip()
    fields = SINGLE_FIELDS + MULTI_FIELDS + [TEXT_FIELD]
    keep_gold = [KEY, "policy_id", "Jurisdiction", "Iso", "Document_full_title"] + fields
    keep_gold = [c for c in keep_gold if c in gold.columns]
    merged = pred.merge(gold[keep_gold], on=KEY, how="inner", suffixes=("_pred", "_gold"))
    for column in ["Jurisdiction", "Iso", "Document_full_title"]:
        if f"{column}_gold" in merged.columns:
            merged[column] = merged[f"{column}_gold"]
    missing = len(pred) - len(merged)
    if missing:
        print(f"Warning: {missing} predicted rows have no gold row and are ignored.")
    return merged


def subsets(frame: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {
        SUBSET_ALL: frame,
        SUBSET_DOCUMENT: frame[frame[SOURCE] == SUBSET_DOCUMENT],
        SUBSET_SUMMARY: frame[frame[SOURCE] == SUBSET_SUMMARY],
    }


def display_names(frame: pd.DataFrame, field: str) -> dict[str, str]:
    """Folded label -> nicely written label (first spelling seen, gold first)."""
    names = {NONE_LABEL: NONE_LABEL}
    for column in (f"{field}_gold", f"{field}_pred"):
        for value in frame[column].dropna():
            for part in str(value).split(";"):
                if part.strip():
                    names.setdefault(fold(part), part.strip())
    return names


# --------------------------------------------------------------- metrics
def field_tables(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    field_rows, label_rows, confusion_rows = [], [], []
    for field in SINGLE_FIELDS + MULTI_FIELDS:
        names = display_names(frame, field)
        multi = field in MULTI_FIELDS
        for subset, part in subsets(frame).items():
            if part.empty:
                continue
            if multi:
                gold = [label_set(v) for v in part[f"{field}_gold"]]
                pred = [label_set(v) for v in part[f"{field}_pred"]]
                summary, per_label = multi_metrics(gold, pred)
            else:
                gold = [single_label(v) for v in part[f"{field}_gold"]]
                pred = [single_label(v) for v in part[f"{field}_pred"]]
                summary, per_label = single_metrics(gold, pred)
            field_rows.append({"field": field, "type": "multi" if multi else "single", "subset": subset, **summary})
            for row in per_label:
                label_rows.append({"field": field, "subset": subset, **row, "label": names.get(row["label"], row["label"])})
            if subset == SUBSET_ALL:
                total = len(part)
                for (g, p), count in confusions(gold, pred).most_common():
                    pretty = (
                        (lambda s: "; ".join(sorted(names.get(x, x) for x in s)))
                        if multi
                        else (lambda s: names.get(s, s))
                    )
                    confusion_rows.append({"field": field, "gold": pretty(g), "model": pretty(p),
                                           "count": count, "share_of_rows": count / total})
    return pd.DataFrame(field_rows), pd.DataFrame(label_rows), pd.DataFrame(confusion_rows)


def text_table(frame: pd.DataFrame, use_bertscore: bool, bertscore_model: str) -> pd.DataFrame:
    import sacrebleu

    rows = []
    for subset, part in subsets(frame).items():
        pairs = [(g, p) for g, p in zip(part[f"{TEXT_FIELD}_gold"], part[f"{TEXT_FIELD}_pred"])
                 if not is_empty(g) and not is_empty(p)]
        if not pairs:
            continue
        refs, cands = [g for g, _ in pairs], [p for _, p in pairs]
        record = {
            "subset": subset,
            "n": len(pairs),
            "rouge1_f1": sum(rouge_n_f1(r, c) for r, c in pairs) / len(pairs),
            "rougeL_f1": sum(rouge_l_f1(r, c) for r, c in pairs) / len(pairs),
            "bleu_sentence_mean": sum(sacrebleu.sentence_bleu(c, [r]).score for r, c in pairs) / len(pairs),
            "bleu_corpus": sacrebleu.corpus_bleu(cands, [refs]).score,
        }
        if use_bertscore:
            from bert_score import score as bert_score

            _, _, f1 = bert_score(cands, refs, model_type=bertscore_model, verbose=False)
            record["bertscore_f1"] = float(f1.mean())
            record["bertscore_model"] = bertscore_model
        rows.append(record)
    return pd.DataFrame(rows)


def row_table(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame[[KEY, "policy_id", "Jurisdiction", "Document_full_title", SOURCE, FALLBACK]].copy()
    correct = []
    for field in CORE_FIELDS:
        if field in MULTI_FIELDS:
            ok = [label_set(g) == label_set(p) for g, p in zip(frame[f"{field}_gold"], frame[f"{field}_pred"])]
        else:
            ok = [single_label(g) == single_label(p) for g, p in zip(frame[f"{field}_gold"], frame[f"{field}_pred"])]
        out[f"{field}_gold"] = frame[f"{field}_gold"].values
        out[f"{field}_model"] = frame[f"{field}_pred"].values
        out[f"{field}_correct"] = ok
        correct.append(ok)
    out["core_correct"] = [sum(values) for values in zip(*correct)]
    out["core_share"] = out["core_correct"] / len(CORE_FIELDS)
    return out.sort_values(["core_share", KEY])


def country_table(rows: pd.DataFrame) -> pd.DataFrame:
    table = rows.groupby("Jurisdiction").agg(
        n_policies=(KEY, "size"),
        n_from_document=(SOURCE, lambda s: int((s == SUBSET_DOCUMENT).sum())),
        core_accuracy=("core_share", "mean"),
    )
    return table.sort_values("core_accuracy", ascending=False).reset_index()


# ----------------------------------------------------------------- figure
def figure(fields: pd.DataFrame, path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    order = CORE_FIELDS + ["Target_type"]
    data = fields[fields["field"].isin(order)].pivot(index="field", columns="subset", values="accuracy").reindex(order)
    data = data.iloc[::-1]  # first field on top
    fig, ax = plt.subplots(figsize=(7.2, 4.2), dpi=200)
    fig.patch.set_facecolor(COLOR_SURFACE)
    ax.set_facecolor(COLOR_SURFACE)
    height = 0.36
    y = range(len(data))
    for offset, subset, color, label in [
        (height / 2 + 0.02, SUBSET_DOCUMENT, COLOR_DOCUMENT, "Coded from full document"),
        (-height / 2 - 0.02, SUBSET_SUMMARY, COLOR_SUMMARY, "Coded from expert summary (fallback)"),
    ]:
        if subset not in data.columns:
            continue
        values = data[subset].fillna(0).values
        ax.barh([i + offset for i in y], values, height=height, color=color, label=label)
        for i, value in zip(y, values):
            ax.text(value + 0.01, i + offset, f"{value:.0%}", va="center", fontsize=7.5, color=COLOR_TEXT_SECONDARY)
    ax.set_yticks(list(y))
    ax.set_yticklabels(data.index, fontsize=8.5, color=COLOR_TEXT)
    ax.set_xlim(0, 1.08)
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.tick_params(axis="x", labelsize=8, colors=COLOR_TEXT_SECONDARY, length=0)
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="x", color=COLOR_GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_title("Exact agreement with expert coding, by input source", loc="left", fontsize=10.5, color=COLOR_TEXT, pad=26)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2, frameon=False, fontsize=8, labelcolor=COLOR_TEXT,
              handlelength=1.2, borderaxespad=0.2)
    fig.tight_layout()
    fig.savefig(path, facecolor=COLOR_SURFACE)
    plt.close(fig)


# ---------------------------------------------------------------- summary
def pct(value) -> str:
    return "–" if pd.isna(value) else f"{value:.0%}"


def summary_markdown(frame, fields, labels, conf, text, countries, predictions_path) -> str:
    sources = frame[SOURCE].value_counts()
    reasons = frame[FALLBACK].fillna("").replace("", pd.NA).dropna().value_counts()
    model = ", ".join(sorted(frame["model"].dropna().unique())) if "model" in frame else "?"
    pivot = fields.pivot(index="field", columns="subset", values="accuracy")
    core = pivot.loc[CORE_FIELDS]

    lines = [
        "# Benchmark: first loop vs. expert gold standard",
        "",
        f"- Predictions: `{predictions_path.name}` (model: {model})",
        f"- Policies compared: {len(frame)}",
        f"- Input source: {sources.get(SUBSET_DOCUMENT, 0)} coded from the full document, "
        f"{sources.get(SUBSET_SUMMARY, 0)} from the expert CDR_link summary (fallback)",
        "- Fallback reasons: " + ", ".join(f"{k} {v}" for k, v in reasons.items()),
        f"- Run: {date.today().isoformat()}",
        "",
        "## Headline",
        "",
        f"Mean exact agreement over the six core fields: **{pct(core[SUBSET_DOCUMENT].mean())}** for policies coded "
        f"from the full document, {pct(core[SUBSET_SUMMARY].mean())} for policies coded from the expert summary.",
        "The summary rows are not a fair test (the summary is written by the experts), so the document rows are the "
        "main result.",
        "",
        "## Agreement per field",
        "",
        "Single fields: accuracy. Multi fields: exact match of the full label set (Jaccard in brackets).",
        "",
        "| Field | Type | All | Document | Summary | Macro-F1 (all) |",
        "|---|---|---|---|---|---|",
    ]
    for field in SINGLE_FIELDS + MULTI_FIELDS:
        sub = fields[fields["field"] == field].set_index("subset")
        kind = sub["type"].iloc[0]

        def cell(subset):
            if subset not in sub.index:
                return "–"
            value = pct(sub.at[subset, "accuracy"])
            if kind == "multi":
                value += f" ({sub.at[subset, 'jaccard']:.2f})"
            return value

        lines.append(f"| {field} | {kind} | {cell(SUBSET_ALL)} | {cell(SUBSET_DOCUMENT)} | {cell(SUBSET_SUMMARY)} | "
                     f"{sub.at[SUBSET_ALL, 'macro_f1']:.2f} |")
    lines += [
        "",
        "Fields that are empty for most policies (Target_*, compliance_market_type, Years_amended) get high accuracy "
        "mainly from correctly predicting \"(none)\". Accuracy on rows where the experts set a value:",
        "",
    ]
    for field in SINGLE_FIELDS:
        row = fields[(fields["field"] == field) & (fields["subset"] == SUBSET_ALL)].iloc[0]
        lines.append(f"- {field}: {pct(row['accuracy_gold_set'])} of {int(row['n_gold_set'])} rows")

    if not text.empty:
        lines += ["", "## CDR_link (text similarity to the expert sentence)", "",
                  "| Subset | n | ROUGE-1 F1 | ROUGE-L F1 | BLEU (corpus) |" + (" BERTScore F1 |" if "bertscore_f1" in text else ""),
                  "|---|---|---|---|---|" + ("---|" if "bertscore_f1" in text else "")]
        for _, row in text.iterrows():
            extra = f" {row['bertscore_f1']:.3f} |" if "bertscore_f1" in text else ""
            lines.append(f"| {row['subset']} | {row['n']} | {row['rouge1_f1']:.3f} | {row['rougeL_f1']:.3f} | "
                         f"{row['bleu_corpus']:.1f} |{extra}")
        lines += ["", "Summary rows received the expert sentence as input, so their CDR_link scores measure copying, "
                      "not understanding; use the document rows."]

    lines += ["", "## Most frequent mix-ups (all rows)", ""]
    for field in CORE_FIELDS:
        top = conf[conf["field"] == field].head(3)
        if top.empty:
            continue
        lines.append(f"**{field}**")
        lines += [f"- expert *{r.gold}* → model *{r.model}*: {r['count']}x ({r.share_of_rows:.0%})" for _, r in top.iterrows()]
        lines.append("")

    weak = labels[(labels["subset"] == SUBSET_ALL) & (labels["support"] >= 5)].sort_values("f1").head(6)
    lines += ["## Weakest labels (F1, at least 5 expert cases)", "",
              "| Field | Label | Expert cases | Model predictions | Precision | Recall | F1 |", "|---|---|---|---|---|---|---|"]
    for _, r in weak.iterrows():
        lines.append(f"| {r.field} | {r.label} | {int(r.support)} | {int(r.predicted)} | {r.precision:.2f} | {r.recall:.2f} | {r.f1:.2f} |")

    lines += ["", "## Core agreement by country", "", "| Country | Policies | From document | Core agreement |", "|---|---|---|---|"]
    for _, r in countries.iterrows():
        lines.append(f"| {r.Jurisdiction} | {r.n_policies} | {r.n_from_document} | {pct(r.core_accuracy)} |")

    lines += [
        "",
        "## Notes",
        "",
        "- Exact agreement is strict: for multi-value fields one missing or extra label counts as wrong; "
        "the Jaccard value shows partial overlap.",
        "- Several expert rows are coded by one person only (`double_coded` in the cleaned sheet), so the gold "
        "standard itself contains some uncertainty.",
        "- Zero-shot run without examples; few-shot prompting and fine-tuning follow in the improvement loop.",
    ]
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------- main
def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--predictions", type=Path, default=DEFAULT_PREDICTIONS)
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--bertscore", action="store_true", help="Also compute BERTScore (pip install bert-score; downloads a model)")
    parser.add_argument("--bertscore-model", default="roberta-large")
    parser.add_argument("--no-figure", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    frame = load(args.predictions, args.gold)
    print(f"Comparing {len(frame)} policies "
          f"({(frame[SOURCE] == SUBSET_DOCUMENT).sum()} from document, {(frame[SOURCE] == SUBSET_SUMMARY).sum()} from summary)")

    fields, labels, conf = field_tables(frame)
    text = text_table(frame, args.bertscore, args.bertscore_model)
    rows = row_table(frame)
    countries = country_table(rows)

    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    fields.to_csv(out / OUT_FIELD_METRICS, index=False, encoding=CSV_ENCODING)
    labels.to_csv(out / OUT_LABEL_METRICS, index=False, encoding=CSV_ENCODING)
    conf.to_csv(out / OUT_CONFUSIONS, index=False, encoding=CSV_ENCODING)
    text.to_csv(out / OUT_TEXT_METRICS, index=False, encoding=CSV_ENCODING)
    rows.to_csv(out / OUT_ROWS, index=False, encoding=CSV_ENCODING)
    countries.to_csv(out / OUT_COUNTRIES, index=False, encoding=CSV_ENCODING)
    if not args.no_figure:
        figure(fields, out / OUT_FIGURE)
    (out / OUT_SUMMARY).write_text(
        summary_markdown(frame, fields, labels, conf, text, countries, args.predictions), encoding="utf-8"
    )

    pivot = fields.pivot(index="field", columns="subset", values="accuracy").reindex(SINGLE_FIELDS + MULTI_FIELDS)
    print("\nExact agreement per field:")
    print(pivot[[c for c in SUBSETS if c in pivot.columns]].map(pct).to_string())
    print(f"\nWrote {out}/")


if __name__ == "__main__":
    main()
