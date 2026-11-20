#!/usr/bin/env python3
"""Error analysis for the four systematic disagreement patterns.

Looks only at the TRAIN split, so the prompt changes derived from it can be
tested fairly on the test split afterwards.

For every pattern (see ``patterns.py``) it
  1. counts how often it happens and on which kinds of documents
     (NDC, strategy/plan, law/regulation, ...; guessed from the title),
  2. draws a sample of rows (default 15 per pattern) for manual review.

Outputs (results/prompt-optimization/):
    error_analysis.md     counts and evidence per pattern
    error_review.xlsx     one sheet per pattern with the sample; fill in the
                          'cause' (drop-down) and 'notes' columns while reading the
                          policy, then use the causes to refine prompt v2
    error_rows.csv        every flagged row (all patterns), for filtering

Usage:
    python src/scripts/prompt-optimization/error-analysis.script.py
    python src/scripts/prompt-optimization/error-analysis.script.py \\
        --predictions results/baseline/retrieved_v1_train.csv --sample 20
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from patterns import PATTERNS, extra_instrument_types, labels  # noqa: E402

DEFAULT_PREDICTIONS = REPO_ROOT / "results" / "first_loop_coding.csv"
DEFAULT_GOLD = REPO_ROOT / "data" / "processed" / "gold_standard_clean.csv"
DEFAULT_SPLIT_FILE = REPO_ROOT / "src" / "resources" / "train_test_split.csv"
DEFAULT_OUT = REPO_ROOT / "results" / "prompt-optimization"
KEY = "sheet_row"
ENCODING = "utf-8-sig"
GOLD_RENAME = {"ETS_market_type": "compliance_market_type"}
FIELDS = ["Policy_scope", "Value_chain_focus", "Instrument_broad", "Instrument_type", "Target_type"]

# Document kind from the title (several languages). Order matters: first match wins.
DOC_KINDS = [
    ("NDC", r"nationally determined contribution|\bi?ndc\b"),
    ("law/regulation", r"\bact\b|\blaw\b|\bley\b|\bloi\b|\blei\b|gesetz|regulation|regulamento|reglamento|"
                       r"directive|decree|decreto|décret|ordinance|\brule\b|\bcode\b|法|条例|규정"),
    ("strategy/plan", r"strateg|\bplan\b|plano|programa|programme|\bprogram\b|roadmap|road map|vision|"
                      r"white paper|communication|\bmission\b|framework|doctrine|fundamentals|eckpunkte|"
                      r"计划|方案|规划|戦略|計画|ロードマップ|ビジョン|전략|기본계획"),
    ("scheme/fund/market", r"scheme|\bfund\b|fonds|fondo|trading|\bets\b|credit|market|mechanism|tax|subsid|"
                           r"grant|contract|procurement|purchase"),
]


def doc_kind(title: str) -> str:
    text = str(title or "").casefold()
    for name, pattern in DOC_KINDS:
        if re.search(pattern, text):
            return name
    return "other"


def read_split(path: Path) -> dict[str, str]:
    table = pd.read_csv(path, dtype=str, encoding=ENCODING)
    return dict(zip(table[KEY].str.strip(), table["split"].str.strip()))


def load(predictions: Path, gold: Path, split_file: Path, split: str | None) -> pd.DataFrame:
    pred = pd.read_csv(predictions, dtype=str, encoding=ENCODING).fillna("")
    gold_frame = pd.read_csv(gold, dtype=str, encoding=ENCODING).fillna("").rename(columns=GOLD_RENAME)
    for frame in (pred, gold_frame):
        frame[KEY] = frame[KEY].astype(str).str.strip()
    keep = [KEY, "Jurisdiction", "Document_full_title", "Year_enacted", "Link", "CDR_link"] + FIELDS
    merged = pred[[c for c in pred.columns if c == KEY or c in FIELDS or c in ("source_used", "input_type")]].merge(
        gold_frame[keep], on=KEY, suffixes=("_model", "_gold"))
    if split:
        merged = merged[merged[KEY].map(read_split(split_file)) == split].copy()
    if "input_type" not in merged.columns:
        merged["input_type"] = merged.get("source_used", "")
    merged["doc_kind"] = merged["Document_full_title"].map(doc_kind)
    return merged.reset_index(drop=True)


def row_dicts(row) -> tuple[dict, dict]:
    gold = {f: row[f"{f}_gold"] for f in FIELDS}
    model = {f: row[f"{f}_model"] for f in FIELDS}
    return gold, model


def flag(frame: pd.DataFrame) -> pd.DataFrame:
    flags = {key: [] for key in PATTERNS}
    extra = []
    for _, row in frame.iterrows():
        gold, model = row_dicts(row)
        for key, spec in PATTERNS.items():
            flags[key].append(spec["test"](gold, model))
        extra.append(extra_instrument_types(gold, model))
    for key, values in flags.items():
        frame[key] = values
    frame["extra_instrument_types"] = extra
    frame["n_types_gold"] = frame["Instrument_type_gold"].map(lambda v: len(labels(v)))
    frame["n_types_model"] = frame["Instrument_type_model"].map(lambda v: len(labels(v)))
    return frame


def share(part: pd.Series, top: int = 6) -> str:
    counts = part.value_counts()
    total = counts.sum()
    text = ", ".join(f"{name} {count} ({count / total:.0%})" for name, count in counts.head(top).items())
    rest = counts.iloc[top:].sum()
    return text + (f", other {rest} ({rest / total:.0%})" if rest else "")


def summary_markdown(frame: pd.DataFrame, predictions: Path, split: str | None) -> str:
    n = len(frame)
    lines = [
        "# Error analysis: systematic disagreements",
        "",
        f"- Predictions: `{predictions.name}`",
        f"- Policies: {n} ({'the ' + split + ' split' if split else 'all'})",
        f"- Run: {date.today().isoformat()}",
        "- Document kind is guessed from the title (NDC, strategy/plan, law/regulation, scheme/fund/market, other).",
        "",
    ]
    for key, spec in PATTERNS.items():
        field = spec["field"]
        hits = frame[frame[key]]
        if key == "P4_instrument_type":
            base = frame
            denominator = f"of {n} policies"
        else:
            gold_value = {"P1_scope": "framework", "P2_value_chain": "cross-cutting",
                          "P3_instrument_broad": "other"}[key]
            base = frame[frame[f"{field}_gold"].str.strip().str.casefold() == gold_value]
            denominator = f"of {len(base)} policies the experts coded as {gold_value.capitalize()}"
        lines += [f"## {spec['title']} ({key})", "",
                  f"- **{len(hits)}** {denominator}",
                  f"- Hypothesis: {spec['hypothesis']}"]
        if len(hits):
            lines.append(f"- Document kinds among these: {share(hits['doc_kind'])}")
            lines.append(f"- Input used: {share(hits['input_type'])}")
            if key in ("P1_scope", "P2_value_chain", "P3_instrument_broad"):
                lines.append(f"- Expert Instrument_type: {share(hits['Instrument_type_gold'].replace('', '(empty)'))}")
            if key == "P2_value_chain":
                lines.append(f"- Expert Target_type: {share(hits['Target_type_gold'].replace('', '(none)'))}")
            if key == "P4_instrument_type":
                lines.append(f"- Instrument types per policy: experts {frame['n_types_gold'].mean():.1f} on average, "
                             f"model {frame['n_types_model'].mean():.1f}")
                lines.append(f"- Extra types the model lists (not in expert coding): "
                             f"{int(frame['extra_instrument_types'].sum())} in total")
                extra = []
                for _, row in hits.iterrows():
                    extra.extend(sorted(labels(row["Instrument_type_model"]) - labels(row["Instrument_type_gold"])))
                if extra:
                    lines.append(f"- Most frequent extra types: {share(pd.Series(extra))}")
        lines.append("")
    if "P2_value_chain" in PATTERNS:
        demand = frame[frame["Value_chain_focus_gold"].str.casefold() == "demand"]
        if len(demand):
            lines += ["## Reference: what the experts code as Demand", "",
                      f"- {len(demand)} policies; Instrument_type: {share(demand['Instrument_type_gold'])}", ""]
    lines += ["## Next step", "",
              "Open `error_review.xlsx`, read each sampled policy (link in the sheet) and pick a cause. "
              "Causes that come up repeatedly become rules in prompt v2 (`prompt_versions.py`)."]
    return "\n".join(lines) + "\n"


def review_workbook(frame: pd.DataFrame, path: Path, sample: int, seed: int) -> None:
    from openpyxl import load_workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.worksheet.datavalidation import DataValidation

    columns = [KEY, "Jurisdiction", "Document_full_title", "Year_enacted", "doc_kind", "input_type", "Link"]
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        guide = pd.DataFrame({"How to use": [
            "One sheet per pattern with a random sample of train-split policies where the model disagrees.",
            "Open the link, check the gold (expert) and model labels, then choose a cause and add a short note.",
            "'expert label debatable' is a valid answer: not every disagreement is a model error.",
            "Count the causes per sheet; the frequent ones become rules in prompt_versions.py (prompt v2).",
        ]})
        guide.to_excel(writer, sheet_name="README", index=False)
        for key, spec in PATTERNS.items():
            hits = frame[frame[key]]
            if len(hits) > sample:
                hits = hits.sample(sample, random_state=seed).sort_values(KEY, key=lambda s: s.astype(int))
            field = spec["field"]
            extra = [f"{field}_gold", f"{field}_model"]
            if field != "Instrument_type":
                extra += ["Instrument_type_gold", "Instrument_type_model"]
            sheet = hits[columns + extra + ["CDR_link"]].rename(columns={"CDR_link": "expert_summary"}).copy()
            sheet["cause"] = ""
            sheet["notes"] = ""
            sheet.to_excel(writer, sheet_name=key, index=False)

    book = load_workbook(path)
    header_fill = PatternFill("solid", fgColor="DDE6F0")
    for key, spec in PATTERNS.items():
        sheet = book[key]
        for cell in sheet[1]:
            cell.font = Font(bold=True)
            cell.fill = header_fill
        widths = {"A": 9, "B": 14, "C": 48, "D": 9, "E": 16, "F": 18, "G": 30}
        for column, width in widths.items():
            sheet.column_dimensions[column].width = width
        for column_cells in sheet.iter_cols(min_col=8, max_col=sheet.max_column):
            sheet.column_dimensions[column_cells[0].column_letter].width = 26
        for row in sheet.iter_rows(min_row=2):
            for cell in row:
                cell.alignment = Alignment(wrap_text=True, vertical="top")
        cause_column = sheet.max_column - 1
        letter = sheet.cell(row=1, column=cause_column).column_letter
        options = ",".join(spec["causes"])
        validation = DataValidation(type="list", formula1=f'"{options}"', allow_blank=True)
        sheet.add_data_validation(validation)
        validation.add(f"{letter}2:{letter}{max(sheet.max_row, 2)}")
        sheet.freeze_panes = "D2"
    book["README"].column_dimensions["A"].width = 110
    book.save(path)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--predictions", type=Path, default=DEFAULT_PREDICTIONS)
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--split", choices=["train", "test", "all"], default="train",
                        help="Default train: keep the test split untouched for the prompt comparison")
    parser.add_argument("--split-file", type=Path, default=DEFAULT_SPLIT_FILE)
    parser.add_argument("--sample", type=int, default=15, help="Rows per pattern in the review workbook")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    split = None if args.split == "all" else args.split
    if split == "test":
        print("Warning: analysing the test split. Rules derived from it make the test comparison biased.")
    frame = flag(load(args.predictions, args.gold, args.split_file, split))
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    text = summary_markdown(frame, args.predictions, split)
    (out / "error_analysis.md").write_text(text, encoding="utf-8")
    flagged = frame[frame[list(PATTERNS)].any(axis=1)]
    flagged.to_csv(out / "error_rows.csv", index=False, encoding=ENCODING)
    review_workbook(frame, out / "error_review.xlsx", args.sample, args.seed)
    print(text)
    print(f"Wrote {out}/")


if __name__ == "__main__":
    main()
