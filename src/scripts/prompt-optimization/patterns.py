"""The four systematic disagreement patterns (from the benchmark and Elina's feedback).

Each pattern is a function of one policy's gold and model labels. Used by the
error analysis (which rows to inspect) and by the prompt comparison (does the
revised prompt reduce the pattern on the test split?).
"""

from __future__ import annotations

import re

NONE = ""


def norm(value) -> str:
    if value is None or (isinstance(value, float) and value != value):
        return NONE
    text = str(value).replace("CO₂", "CO2").replace("₂", "2")
    text = re.sub(r"\s+", " ", text).strip().casefold()
    return "" if text in {"nan", "none"} else text


def labels(value) -> set[str]:
    return {part for part in (norm(p) for p in str(value or "").split(";")) if part}


def scope_framework_as_instrument(gold: dict, pred: dict) -> bool:
    return norm(gold["Policy_scope"]) == "framework" and norm(pred["Policy_scope"]) == "instrument"


def crosscutting_as_demand(gold: dict, pred: dict) -> bool:
    return norm(gold["Value_chain_focus"]) == "cross-cutting" and norm(pred["Value_chain_focus"]) == "demand"


def other_as_regulatory(gold: dict, pred: dict) -> bool:
    return norm(gold["Instrument_broad"]) == "other" and norm(pred["Instrument_broad"]) == "regulatory instrument"


def extra_instrument_types(gold: dict, pred: dict) -> int:
    """Number of instrument types the model lists that the experts did not."""
    return len(labels(pred["Instrument_type"]) - labels(gold["Instrument_type"]))


def too_many_instrument_types(gold: dict, pred: dict) -> bool:
    return extra_instrument_types(gold, pred) > 0 and len(labels(pred["Instrument_type"])) > len(
        labels(gold["Instrument_type"]))


PATTERNS = {
    "P1_scope": {
        "title": "Framework coded as Instrument",
        "field": "Policy_scope",
        "test": scope_framework_as_instrument,
        "hypothesis": "Strategies, plans, NDCs and climate laws are read as instruments; "
                      "the prompt calls every document an 'instrument'.",
        "causes": ["strategy/plan read as instrument", "law with targets read as instrument",
                   "lists measures, so read as instrument", "expert label debatable", "input too thin",
                   "other"],
    },
    "P2_value_chain": {
        "title": "Cross-cutting coded as Demand",
        "field": "Value_chain_focus",
        "test": crosscutting_as_demand,
        "hypothesis": "General emissions or net-zero targets and strategies are read as creating demand "
                      "(the codebook's Demand definition mentions 'binding targets').",
        "causes": ["emissions/net-zero target read as demand", "strategy mentioning markets read as demand",
                   "codebook wording ('binding targets')", "expert label debatable", "input too thin", "other"],
    },
    "P3_instrument_broad": {
        "title": "Other coded as Regulatory instrument",
        "field": "Instrument_broad",
        "test": other_as_regulatory,
        "hypothesis": "Any official or formal document is read as a regulatory instrument, even when its "
                      "function is strategic or institutional.",
        "causes": ["formal/official document read as regulatory", "strategy with legal basis read as regulatory",
                   "expert label debatable", "input too thin", "other"],
    },
    "P4_instrument_type": {
        "title": "Too many instrument types",
        "field": "Instrument_type",
        "test": too_many_instrument_types,
        "hypothesis": "Mechanisms that are only mentioned (or planned, or belong to other policies) are listed "
                      "as if the policy established them.",
        "causes": ["mentioned, not established", "planned/future measure", "belongs to another policy",
                   "lists every measure of a strategy", "expert label incomplete", "other"],
    },
}
