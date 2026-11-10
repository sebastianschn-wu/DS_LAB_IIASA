"""Train/test split and the worked examples for one-/few-shot prompting.

Split
    ``src/resources/train_test_split.csv`` assigns every policy to ``train`` (228) or
    ``test`` (99): 70/30 per country, seed 42, rows that share one source document
    kept together. Few-shot runs code only the test policies; examples come only
    from the train policies, so no example is ever evaluated.

Examples
    Five train policies, chosen to target the systematic zero-shot errors found in
    the benchmark. One-shot uses the first, three-shot the first three, and so on.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

SHEET_ROW = "sheet_row"
JURISDICTION = "Jurisdiction"
TITLE = "Document_full_title"
YEAR = "Year_enacted"
SPLIT_TRAIN = "train"
SPLIT_TEST = "test"
SPLIT_ENCODING = "utf-8-sig"

# (sheet row, why this policy is an example) - all five are in the train split.
EXAMPLE_ROWS = [
    ("19", "framework law with emissions target, cross-cutting (Australia, Climate Change Act 2022)"),
    ("43", "regulatory instrument for CO2 storage, no target (EU, CCS Directive)"),
    ("73", "economic instrument supporting supply (Argentina, National Forest Extension Programme)"),
    ("104", "demand-side instrument (Canada, CDR purchase commitment)"),
    ("118", "conventional (land-based) CDR instrument (France, France 2030 forest renewal)"),
]

# The raw sheet still uses the old ETS_ column names for these codebook fields.
LEGACY_FIELD_NAMES = {
    "compliance_market_type": "ETS_market_type",
    "compliance_upper_bound": "ETS_upper_bound",
    "compliance_upper_bound_unit": "ETS_upper_bound_unit",
}
# Expert comments are internal notes ("[NEW ROW: ...]"), not part of the coding to imitate.
EMPTY_IN_EXAMPLES = {"Comments"}

EXAMPLES_HEADING = (
    "Worked examples. The experts coded these policies as shown. "
    "They are examples of the coding decisions, not part of the policy you have to code."
)


def read_split(path: Path) -> dict[str, str]:
    """sheet_row -> 'train' / 'test'."""
    with path.open(newline="", encoding=SPLIT_ENCODING) as handle:
        return {row[SHEET_ROW]: row["split"] for row in csv.DictReader(handle)}


def select_examples(policies: list[dict[str, str]], shots: int) -> list[dict[str, str]]:
    if shots < 0 or shots > len(EXAMPLE_ROWS):
        raise SystemExit(f"--shots must be between 0 and {len(EXAMPLE_ROWS)}")
    by_row = {policy[SHEET_ROW]: policy for policy in policies}
    return [by_row[row] for row, _ in EXAMPLE_ROWS[:shots]]


def gold_value(policy: dict[str, str], field: str) -> str:
    value = (policy.get(field) or "").strip()
    if not value and field in LEGACY_FIELD_NAMES:
        value = (policy.get(LEGACY_FIELD_NAMES[field]) or "").strip()
    return value


def example_coding(policy: dict[str, str], model_fields: list[str]) -> dict[str, str]:
    """The expert coding in the answer format the first loop asks for (multi values joined by '; ')."""
    return {field: "" if field in EMPTY_IN_EXAMPLES else gold_value(policy, field) for field in model_fields}


def render_examples(examples: list[dict[str, str]], model_fields: list[str]) -> str:
    """Text block appended to the first-loop instructions."""
    if not examples:
        return ""
    lines = ["", EXAMPLES_HEADING]
    for number, policy in enumerate(examples, start=1):
        lines += [
            "",
            f"Example {number}: {policy.get(JURISDICTION, '')} | {policy.get(TITLE, '')} | {policy.get(YEAR, '')}",
            json.dumps(example_coding(policy, model_fields), ensure_ascii=False),
        ]
    return "\n".join(lines)
