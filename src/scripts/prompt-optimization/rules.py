"""Deterministic coding rules applied after the model (hybrid: rules + LLM).

Some codings follow fixed conventions in the expert data. Where a convention
holds (almost) always on the TRAIN split, a rule sets the value instead of the
model. The rules only use the policy title and the model's own predictions,
never the gold standard, so they can run on new (scraped) policies too.

    R1 NDC          Title is a (I)NDC -> Policy_scope Framework, Instrument_broad
                    Regulatory instrument, Value_chain_focus Cross-cutting,
                    Instrument_type target, Target_type Emissions.
                    Train split: 42 of 42 NDCs coded exactly like this.
    R2 Framework    Policy_scope (after R1) is Framework -> Instrument_type is
                    target if the model coded a target, otherwise Other.
                    Train split: 72 of 77 frameworks with a target have only
                    'target', 38 of 53 without a target have only 'Other'.

``check_on_gold`` recomputes these shares from the gold standard, so the
evidence stays reproducible.
"""

from __future__ import annotations

import re

NDC_TITLE = re.compile(r"nationally determined contribution|\bi?ndc\b", re.IGNORECASE)
FRAMEWORK = "Framework"
TARGET = "target"
OTHER = "Other"
RULES_COLUMN = "rules_applied"

R1_VALUES = {
    "Policy_scope": FRAMEWORK,
    "Instrument_broad": "Regulatory instrument",
    "Value_chain_focus": "Cross-cutting",
    "Instrument_type": TARGET,
    "Target_type": "Emissions",
}


def is_ndc(title: str) -> bool:
    return bool(NDC_TITLE.search(title or ""))


def has_value(value) -> bool:
    text = "" if value is None else str(value).strip()
    return text not in ("", "nan", "None")


def apply_rules(row: dict, title: str) -> tuple[dict, list[str]]:
    """Return the changed row and the names of the rules that changed something."""
    row = dict(row)
    applied: list[str] = []
    if is_ndc(title):
        changed = [f for f, v in R1_VALUES.items() if str(row.get(f, "")).strip() != v]
        if changed:
            row.update(R1_VALUES)
            applied.append("R1_ndc")
    if str(row.get("Policy_scope", "")).strip().casefold() == FRAMEWORK.casefold():
        wanted = TARGET if has_value(row.get("Target_type")) else OTHER
        if str(row.get("Instrument_type", "")).strip() != wanted:
            row["Instrument_type"] = wanted
            applied.append("R2_framework")
    return row, applied


def check_on_gold(gold_rows: list[dict]) -> list[str]:
    """How often each rule agrees with the expert coding (pass train-split gold rows)."""
    lines = []
    ndcs = [r for r in gold_rows if is_ndc(r.get("Document_full_title", ""))]
    if ndcs:
        agree = sum(all(str(r.get(f, "")).strip() == v for f, v in R1_VALUES.items()) for r in ndcs)
        lines.append(f"R1 NDC: {agree} of {len(ndcs)} NDCs coded exactly as the rule says")
    frameworks = [r for r in gold_rows if str(r.get("Policy_scope", "")).strip() == FRAMEWORK]
    with_target = [r for r in frameworks if has_value(r.get("Target_type"))]
    without = [r for r in frameworks if not has_value(r.get("Target_type"))]
    if frameworks:
        a = sum(str(r.get("Instrument_type", "")).strip() == TARGET for r in with_target)
        b = sum(str(r.get("Instrument_type", "")).strip() == OTHER for r in without)
        lines.append(f"R2 Framework: {a} of {len(with_target)} with a target have only 'target'; "
                     f"{b} of {len(without)} without a target have only 'Other' "
                     f"({(a + b) / len(frameworks):.0%} of {len(frameworks)} frameworks)")
    return lines
