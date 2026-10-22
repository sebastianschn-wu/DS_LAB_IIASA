#!/usr/bin/env python3
"""Clean the expert-coded CDR policy sheet so it can serve as the gold standard.

The script never changes a coding decision of the experts. It only harmonises
formats, renames columns to the codebook v1.0 names, adds helper columns for
the evaluation, and flags rows that need a human decision in the column
``cleaning_issues``.

Steps:
 1. Drop empty helper columns and trim whitespace.
 2. Rename ETS_* columns to the codebook names (compliance_*).
 3. Normalise multi-value fields ("a;b" -> "a; b", duplicates removed).
 4. Check closed fields against the allowed values in the CodingScheme sheet.
 5. Normalise target fields (dashes, separators, number of parallel targets).
 6. Harmonise funding to ISO currency codes and absolute amounts.
 7. Remove tracking parameters from links.
 8. Parse the Validation column into coders / number of coders.
 9. Extract the expert team's comment tags (NEW ROW, CORRECTED, VCF).
10. Group rows that point to the same source document (important for the
    train/test split: such rows must end up in the same split).
11. Aggregate the cleaned data by country.

Outputs (written to data/processed/, which is git-ignored because the
benchmark data must not be redistributed):
    CDR_policy_sheet_clean.xlsx  same sheets as the input, usable with
                                 first-loop.script.py --sheet
    gold_standard_clean.csv      the cleaned Data sheet as CSV
    country_summary.csv          policies aggregated by country
    cleaning_report.md           what was changed and what needs review

Usage:
    python src/scripts/data-cleaning/data-cleaning.script.py
    python src/scripts/data-cleaning/data-cleaning.script.py --sheet path/to/sheet.xlsx --output-dir out/
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

_SCRIPT_DIR = str(Path(__file__).resolve().parent)
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

import pandas as pd

from constants import (
    CLOSED_FIELDS,
    CODER_ALIASES,
    COL_CODERS,
    COL_COMMENT_TAGS,
    COL_DOUBLE_CODED,
    COL_FUNDING_RAW,
    COL_ISSUES,
    COL_N_CODERS,
    COL_N_TARGETS,
    COL_POLICY_ID,
    COL_SHARED_DOC_GROUP,
    COL_SHEET_ROW,
    COMMENT_TAG_PATTERN,
    CSV_ENCODING,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_SHEET,
    DROP_COLUMNS,
    FUNDING_UNIT_MAP,
    MULTI_VALUE_FIELDS,
    OUTPUT_COUNTRY_SUMMARY,
    OUTPUT_CSV,
    OUTPUT_REPORT,
    OUTPUT_XLSX,
    PARALLEL_LIST_FIELDS,
    RENAME_COLUMNS,
    SHEET_CODING_SCHEME,
    SHEET_DATA,
    SHEET_README,
    TRACKING_PARAMS,
    VALUE_SEPARATOR,
)

DASHES = re.compile(r"[‒–—−]")  # figure dash, en dash, em dash, minus


class Log:
    """Collects changes and per-row issues for the report."""

    def __init__(self) -> None:
        self.steps: list[str] = []
        self.issues: dict[int, list[str]] = {}

    def step(self, text: str) -> None:
        self.steps.append(text)
        print(f"- {text}")

    def issue(self, sheet_row: int, text: str) -> None:
        self.issues.setdefault(sheet_row, []).append(text)


# --------------------------------------------------------------------- helpers
def is_empty(value) -> bool:
    return value is None or (isinstance(value, float) and pd.isna(value)) or (
        isinstance(value, str) and not value.strip()
    )


def as_text(value) -> str:
    if is_empty(value):
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def clean_whitespace(value):
    if not isinstance(value, str):
        return value
    text = value.replace(" ", " ").replace("\r\n", "\n").strip()
    return text if text else None


def split_values(value) -> list[str]:
    return [part.strip() for part in as_text(value).split(";") if part.strip()]


def fold(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("₂", "2")).strip().casefold()


# --------------------------------------------------------------------- steps
def load(path: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    data = pd.read_excel(path, sheet_name=SHEET_DATA, dtype=object)
    scheme = pd.read_excel(path, sheet_name=SHEET_CODING_SCHEME, dtype=object)
    readme = pd.read_excel(path, sheet_name=SHEET_README, header=None, dtype=object)
    data.insert(0, COL_SHEET_ROW, range(2, len(data) + 2))  # Excel row number of the source
    return data, scheme, readme


def drop_empty(data: pd.DataFrame, log: Log) -> pd.DataFrame:
    before = len(data)
    content = data.drop(columns=[COL_SHEET_ROW])
    data = data[~content.isna().all(axis=1)].copy()
    if before != len(data):
        log.step(f"Removed {before - len(data)} completely empty rows.")
    dropped = [c for c in DROP_COLUMNS if c in data.columns and data[c].isna().all()]
    kept = [c for c in DROP_COLUMNS if c in data.columns and c not in dropped]
    if dropped:
        data = data.drop(columns=dropped)
        log.step(f"Dropped empty columns: {', '.join(dropped)}.")
    if kept:
        log.step(f"Kept columns {', '.join(kept)} because they contain values (please check).")
    return data


def add_ids(data: pd.DataFrame, log: Log) -> pd.DataFrame:
    data.insert(
        0,
        COL_POLICY_ID,
        [f"{iso}-{row:03d}" for iso, row in zip(data["Iso"].map(as_text), data[COL_SHEET_ROW])],
    )
    log.step(f"Added stable `{COL_POLICY_ID}` (ISO code + source row) and `{COL_SHEET_ROW}`.")
    return data


def trim(data: pd.DataFrame, log: Log) -> pd.DataFrame:
    changed = 0
    for column in data.columns:
        new = data[column].map(clean_whitespace)
        changed += int((new.fillna("<NA>") != data[column].fillna("<NA>")).sum())
        data[column] = new
    log.step(f"Trimmed whitespace / non-breaking spaces in {changed} cells.")
    return data


def rename(data: pd.DataFrame, log: Log) -> pd.DataFrame:
    present = {old: new for old, new in RENAME_COLUMNS.items() if old in data.columns}
    if present:
        data = data.rename(columns=present)
        log.step(
            "Renamed columns to codebook v1.0 names: "
            + ", ".join(f"`{o}` -> `{n}`" for o, n in present.items())
            + "."
        )
    return data


def normalise_multi_values(data: pd.DataFrame, log: Log) -> pd.DataFrame:
    changed = 0
    for column in MULTI_VALUE_FIELDS:
        if column not in data.columns:
            continue
        for idx, value in data[column].items():
            if is_empty(value):
                continue
            parts = list(dict.fromkeys(split_values(value)))
            if column == "Years_amended":
                years = [p for p in parts if re.fullmatch(r"\d{4}", p)]
                invalid = [p for p in parts if p not in years]
                if invalid:
                    log.issue(
                        data.at[idx, COL_SHEET_ROW],
                        f"Years_amended contained non-year value(s) {invalid}; removed, please add the actual years",
                    )
                parts = years
            new = VALUE_SEPARATOR.join(parts) if parts else None
            if as_text(new) != as_text(value):
                changed += 1
            data.at[idx, column] = new
    log.step(f"Normalised separators / duplicates in multi-value fields ({changed} cells changed).")
    return data


def check_closed_fields(data: pd.DataFrame, scheme: pd.DataFrame, log: Log) -> pd.DataFrame:
    found = Counter()
    for column, scheme_column in CLOSED_FIELDS.items():
        if column not in data.columns or scheme_column not in scheme.columns:
            continue
        allowed = {fold(as_text(v)): as_text(v) for v in scheme[scheme_column].dropna()}
        for idx, value in data[column].items():
            if is_empty(value):
                continue
            parts = split_values(value) if column in MULTI_VALUE_FIELDS else [as_text(value)]
            fixed = []
            for part in parts:
                canonical = allowed.get(fold(part))
                if canonical is None:
                    found[(column, part)] += 1
                    log.issue(
                        data.at[idx, COL_SHEET_ROW],
                        f"{column} value '{part}' is not defined in the codebook / CodingScheme",
                    )
                    fixed.append(part)
                else:
                    fixed.append(canonical)
            data.at[idx, column] = VALUE_SEPARATOR.join(fixed)
    if found:
        listing = ", ".join(f"{c} = '{v}' ({n}x)" for (c, v), n in found.items())
        log.step(f"Values not in the codebook (kept, flagged for review): {listing}.")
    else:
        log.step("All closed fields use allowed codebook values.")
    return data


def normalise_targets(data: pd.DataFrame, log: Log) -> pd.DataFrame:
    counts = []
    for idx, row in data.iterrows():
        lengths = []
        for column in PARALLEL_LIST_FIELDS:
            value = row.get(column)
            if is_empty(value):
                continue
            text = DASHES.sub("-", as_text(value))
            parts = split_values(text) if column != "Target_unit" else [text]
            data.at[idx, column] = VALUE_SEPARATOR.join(parts) if column != "Target_unit" else text
            if column != "Target_unit":
                lengths.append(len(parts))
        if len(set(lengths)) > 1:
            log.issue(row[COL_SHEET_ROW], "Target_year and Target_amount list a different number of targets")
        counts.append(max(lengths) if lengths else 0)
    data[COL_N_TARGETS] = counts
    if "compliance_upper_bound" in data.columns:
        data["compliance_upper_bound"] = data["compliance_upper_bound"].map(
            lambda v: v if is_empty(v) else DASHES.sub("-", as_text(v))
        )
    log.step(
        "Target fields: unified dashes (– -> -) and separators; added "
        f"`{COL_N_TARGETS}` ({sum(c > 1 for c in counts)} policies have several targets)."
    )
    return data


def harmonise_funding(data: pd.DataFrame, log: Log) -> pd.DataFrame:
    raw_values, converted = [], 0
    for idx, row in data.iterrows():
        amount, unit = row.get("Funding_sum"), as_text(row.get("Funding_unit"))
        if is_empty(amount) and not unit:
            raw_values.append(None)
            continue
        raw_values.append(f"{as_text(amount)} {unit}".strip())
        mapping = FUNDING_UNIT_MAP.get(unit)
        if mapping is None:
            log.issue(row[COL_SHEET_ROW], f"Unknown funding unit '{unit}'")
            continue
        code, factor = mapping
        try:
            value = float(amount) * factor
        except (TypeError, ValueError):
            log.issue(row[COL_SHEET_ROW], f"Funding_sum '{amount}' is not a number")
            continue
        data.at[idx, "Funding_sum"] = int(value) if value.is_integer() else value
        if (code, factor) != (unit, 1):
            converted += 1
        data.at[idx, "Funding_unit"] = code
    position = data.columns.get_loc("Funding_unit") + 1
    data.insert(position, COL_FUNDING_RAW, raw_values)
    log.step(
        f"Funding harmonised to ISO currency codes and absolute amounts ({converted} rows converted, "
        f"e.g. '50 AUD million' -> 50000000 AUD); original kept in `{COL_FUNDING_RAW}`."
    )
    return data


def strip_tracking(url: str) -> str:
    """Remove utm_* parameters; leave every other part of the URL byte-for-byte unchanged."""
    parts = urlsplit(url)
    if not parts.query:
        return url
    pieces = parts.query.split("&")
    kept = [p for p in pieces if p.split("=", 1)[0] not in TRACKING_PARAMS]
    if len(kept) == len(pieces):
        return url
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "&".join(kept), parts.fragment))


def clean_links(data: pd.DataFrame, log: Log) -> pd.DataFrame:
    changed = 0
    for idx, value in data["Link"].items():
        if is_empty(value):
            log.issue(data.at[idx, COL_SHEET_ROW], "Missing link")
            continue
        url = as_text(value)
        if not re.match(r"https?://", url):
            log.issue(data.at[idx, COL_SHEET_ROW], f"Link is not a web address: '{url}'")
            continue
        new = strip_tracking(url)
        if new != url:
            changed += 1
            data.at[idx, "Link"] = new
    log.step(f"Removed tracking parameters from {changed} link(s).")
    return data


def parse_coders(data: pd.DataFrame, log: Log) -> pd.DataFrame:
    coders_col, n_col = [], []
    for value in data["Validation"]:
        names = []
        for part in split_values(value):
            name = re.sub(r"\s*\(.*?\)\s*", " ", part).strip()  # drop "(March 2026)" etc.
            name = CODER_ALIASES.get(name, name)
            if name and name not in names:
                names.append(name)
        coders_col.append(VALUE_SEPARATOR.join(names) or None)
        n_col.append(len(names))
    position = data.columns.get_loc("Validation") + 1
    data.insert(position, COL_CODERS, coders_col)
    data.insert(position + 1, COL_N_CODERS, n_col)
    data.insert(position + 2, COL_DOUBLE_CODED, [n >= 2 for n in n_col])
    single = sum(n < 2 for n in n_col)
    log.step(
        f"Parsed `Validation` into `{COL_CODERS}`, `{COL_N_CODERS}`, `{COL_DOUBLE_CODED}`: "
        f"{len(n_col) - single} rows list two coders, {single} rows list only one "
        f"(initials {', '.join(CODER_ALIASES)} mapped to the codebook authors - please confirm with the coach)."
    )
    return data


def extract_comment_tags(data: pd.DataFrame, log: Log) -> pd.DataFrame:
    tags = data["Comments"].map(
        lambda v: None
        if is_empty(v)
        else (VALUE_SEPARATOR.join(dict.fromkeys(re.findall(COMMENT_TAG_PATTERN, as_text(v)))) or None)
    )
    data.insert(data.columns.get_loc("Comments") + 1, COL_COMMENT_TAGS, tags)
    counts = Counter(t for v in tags.dropna() for t in v.split(VALUE_SEPARATOR))
    log.step(
        f"Extracted expert comment tags into `{COL_COMMENT_TAGS}`: "
        + (", ".join(f"{k} ({n})" for k, n in counts.items()) or "none")
        + "."
    )
    return data


def group_shared_documents(data: pd.DataFrame, log: Log) -> pd.DataFrame:
    keys = data["Link"].map(lambda v: as_text(v).rstrip("/").lower() or None)
    sizes = keys.map(keys.value_counts())
    shared = sorted({k for k, n in zip(keys, sizes) if k and n > 1})
    group_ids = {k: f"DOC-{i:02d}" for i, k in enumerate(shared, start=1)}
    data[COL_SHARED_DOC_GROUP] = keys.map(group_ids)
    for key, group in data.groupby(COL_SHARED_DOC_GROUP):
        rows = group[COL_SHEET_ROW].tolist()
        isos = group["Iso"].map(as_text)
        for idx, row in group.iterrows():
            others = [r for r in rows if r != row[COL_SHEET_ROW]]
            same_country = [
                r for r, iso in zip(group[COL_SHEET_ROW], isos) if r != row[COL_SHEET_ROW] and iso == as_text(row["Iso"])
            ]
            text = f"Same source document as row(s) {others} ({key})"
            if same_country:
                text += "; same jurisdiction too - possible duplicate entry, please check"
            log.issue(row[COL_SHEET_ROW], text)
    log.step(
        f"Added `{COL_SHARED_DOC_GROUP}`: {len(shared)} source documents are used by more than one row "
        f"({int(data[COL_SHARED_DOC_GROUP].notna().sum())} rows). Keep each group in the same train/test split."
    )
    return data


def add_issue_column(data: pd.DataFrame, log: Log) -> pd.DataFrame:
    data[COL_ISSUES] = data[COL_SHEET_ROW].map(lambda r: " | ".join(log.issues.get(r, [])) or None)
    return data


def country_summary(data: pd.DataFrame) -> pd.DataFrame:
    def count_values(frame: pd.DataFrame, column: str, prefix: str) -> pd.Series:
        exploded = frame[column].dropna().map(split_values).explode()
        return exploded.value_counts().add_prefix(prefix)

    rows = []
    for (jurisdiction, iso), group in data.groupby(["Jurisdiction", "Iso"], sort=True):
        record = {
            "Jurisdiction": jurisdiction,
            "Iso": iso,
            "n_policies": len(group),
            "n_double_coded": int(group[COL_DOUBLE_CODED].sum()),
            "first_year": int(group["Year_enacted"].min()),
            "last_year": int(group["Year_enacted"].max()),
            "n_with_target": int(group["Target_type"].notna().sum()),
            "n_with_issues": int(group[COL_ISSUES].notna().sum()),
        }
        for column, prefix in [
            ("Policy_scope", "scope: "),
            ("Broad_method", "method: "),
            ("Value_chain_focus", "value_chain: "),
            ("Instrument_broad", "instrument: "),
        ]:
            record.update(count_values(group, column, prefix).to_dict())
        rows.append(record)
    summary = pd.DataFrame(rows).fillna(0)
    count_cols = [c for c in summary.columns if ": " in c]
    summary[count_cols] = summary[count_cols].astype(int)
    fixed = ["Jurisdiction", "Iso", "n_policies", "n_double_coded", "first_year", "last_year", "n_with_target", "n_with_issues"]
    return summary[fixed + sorted(count_cols)].sort_values("n_policies", ascending=False)


# --------------------------------------------------------------------- output
def write_outputs(
    data: pd.DataFrame,
    scheme: pd.DataFrame,
    readme: pd.DataFrame,
    summary: pd.DataFrame,
    log: Log,
    source: Path,
    out_dir: Path,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    note = pd.DataFrame(
        [[None], [f"Cleaned with src/scripts/data-cleaning/data-cleaning.script.py on {date.today().isoformat()}."],
         ["See cleaning_report.md for all changes. Coding decisions of the experts were not changed."]]
    )
    readme_out = pd.concat([readme.iloc[:, :1], note], ignore_index=True)
    with pd.ExcelWriter(out_dir / OUTPUT_XLSX, engine="openpyxl") as writer:
        readme_out.to_excel(writer, sheet_name=SHEET_README, header=False, index=False)
        scheme.to_excel(writer, sheet_name=SHEET_CODING_SCHEME, index=False)
        data.to_excel(writer, sheet_name=SHEET_DATA, index=False)
    data.to_csv(out_dir / OUTPUT_CSV, index=False, encoding=CSV_ENCODING)
    summary.to_csv(out_dir / OUTPUT_COUNTRY_SUMMARY, index=False, encoding=CSV_ENCODING)

    lines = [
        "# Cleaning report: CDR policy gold standard",
        "",
        f"- Source: `{source.name}`",
        f"- Run: {date.today().isoformat()}",
        f"- Policies: {len(data)} from {data['Iso'].nunique()} jurisdictions",
        f"- Rows flagged for review: {int(data[COL_ISSUES].notna().sum())}",
        "",
        "## Changes",
        "",
        *[f"{i}. {s}" for i, s in enumerate(log.steps, start=1)],
        "",
        "## Rows that need a human decision",
        "",
        "| policy_id | sheet row | Jurisdiction | Document | Issue |",
        "|---|---|---|---|---|",
    ]
    for _, row in data[data[COL_ISSUES].notna()].iterrows():
        title = as_text(row["Document_full_title"]).replace("|", "/")
        title = title if len(title) <= 70 else title[:67] + "..."
        for issue in log.issues[row[COL_SHEET_ROW]]:
            lines.append(
                f"| {row[COL_POLICY_ID]} | {row[COL_SHEET_ROW]} | {row['Jurisdiction']} | {title} | {issue.replace('|', '/')} |"
            )
    lines += [
        "",
        "## Notes for the evaluation",
        "",
        "- `CDR_link` is written by the experts and is also a field the model has to produce. "
        "Using it as model input (summary fallback) and scoring it afterwards leaks the answer; "
        "rows coded from this summary should be reported separately or excluded from the CDR_link scores.",
        f"- Rows with the same `{COL_SHARED_DOC_GROUP}` share one source document and must stay in the same "
        "train/test split, otherwise the test set contains documents the model has already seen.",
        "- The EU uses the code `EU`, which is not an ISO 3166 code. EU NDC rows also appear under "
        "France, Germany and Italy with the suffix [Country].",
        f"- Only `{COL_DOUBLE_CODED}` = True rows are validated by two experts as described in the codebook.",
    ]
    (out_dir / OUTPUT_REPORT).write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clean the expert-coded CDR policy sheet.")
    parser.add_argument("--sheet", type=Path, default=DEFAULT_SHEET)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    log = Log()
    data, scheme, readme = load(args.sheet)
    print(f"Loaded {len(data)} rows from {args.sheet}")

    data = drop_empty(data, log)
    data = trim(data, log)
    data = add_ids(data, log)
    data = rename(data, log)
    data = normalise_multi_values(data, log)
    data = check_closed_fields(data, scheme, log)
    data = normalise_targets(data, log)
    data = harmonise_funding(data, log)
    data = clean_links(data, log)
    data = parse_coders(data, log)
    data = extract_comment_tags(data, log)
    data = group_shared_documents(data, log)
    data = add_issue_column(data, log)
    summary = country_summary(data)

    write_outputs(data, scheme, readme, summary, log, args.sheet, args.output_dir)
    print(f"\nRows flagged for review: {int(data[COL_ISSUES].notna().sum())}")
    print(f"Wrote {args.output_dir}/{{{OUTPUT_XLSX}, {OUTPUT_CSV}, {OUTPUT_COUNTRY_SUMMARY}, {OUTPUT_REPORT}}}")


if __name__ == "__main__":
    main()
