"""Prompt versions, error patterns, error analysis and prompt comparison on small synthetic data."""

import importlib.util
from pathlib import Path

import pandas as pd
import pytest

import patterns
from prompt_versions import V2_RULES, instructions_for, user_prompt_header

HERE = Path(__file__).resolve().parents[1]
SINGLE = ["Policy_scope", "Value_chain_focus", "Instrument_broad", "Target_type", "Target_binding",
          "compliance_market_type"]
MULTI = ["Broad_method", "Specific_method", "Instrument_type", "Years_amended"]


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), HERE / f"{name}.script.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ------------------------------------------------------------ prompt versions
def test_v1_is_unchanged_and_v2_appends_rules():
    base = "BASE INSTRUCTIONS"
    assert instructions_for("v1", base) == base
    v2 = instructions_for("v2", base)
    assert v2.startswith(base) and all(rule in v2 for rule in V2_RULES)
    assert "instrument" in user_prompt_header("v1", "Code this instrument")
    assert "Code this policy" in user_prompt_header("v2", "Code this instrument")
    with pytest.raises(ValueError):
        instructions_for("v9", base)


# ------------------------------------------------------------------- patterns
def coding(scope="Framework", chain="Cross-cutting", broad="Other", types="target", target="Emissions"):
    return {"Policy_scope": scope, "Value_chain_focus": chain, "Instrument_broad": broad,
            "Instrument_type": types, "Target_type": target}


def test_patterns_detect_each_error():
    gold = coding()
    assert patterns.scope_framework_as_instrument(gold, coding(scope="Instrument"))
    assert patterns.crosscutting_as_demand(gold, coding(chain="Demand"))
    assert patterns.other_as_regulatory(gold, coding(broad="Regulatory instrument"))
    assert patterns.too_many_instrument_types(gold, coding(types="target; mrv_standard; Other"))
    assert patterns.extra_instrument_types(gold, coding(types="target; mrv_standard; Other")) == 2
    same = coding()
    assert not any(spec["test"](gold, same) for spec in patterns.PATTERNS.values())


# ---------------------------------------------------------- synthetic files
def write_data(tmp_path):
    rows = []
    for i in range(2, 12):
        rows.append({"sheet_row": str(i), "policy_id": f"P{i}", "Jurisdiction": "Testland", "Iso": "TST",
                     "Document_full_title": "National Climate Strategy" if i % 2 else "Carbon Tax Act",
                     "Year_enacted": "2020", "Link": f"https://example.org/{i}", "CDR_link": "summary",
                     "Policy_scope": "Framework", "Value_chain_focus": "Cross-cutting", "Instrument_broad": "Other",
                     "Instrument_type": "target", "Target_type": "Emissions", "Target_binding": "Yes",
                     "compliance_market_type": "", "Broad_method": "Multiple", "Specific_method": "Multiple",
                     "Years_amended": ""})
    gold = pd.DataFrame(rows)
    before = gold.copy()
    before["Policy_scope"] = "Instrument"
    before["Value_chain_focus"] = "Demand"
    before["Instrument_broad"] = "Regulatory instrument"
    before["Instrument_type"] = "target; mrv_standard; public_procurement"
    before["source_used"] = "document"
    before["input_type"] = ["policy_text"] * 6 + ["no_text"] * 4
    after = gold.copy()
    after["source_used"] = "document"
    after["input_type"] = before["input_type"]
    after.loc[0, "Target_binding"] = "No"  # one new error
    split = pd.DataFrame({"sheet_row": gold.sheet_row, "split": ["train"] * 5 + ["test"] * 5})
    paths = {}
    for name, frame in {"gold": gold, "before": before, "after": after, "split": split}.items():
        paths[name] = tmp_path / f"{name}.csv"
        frame.to_csv(paths[name], index=False, encoding="utf-8-sig")
    return paths


def test_error_analysis_writes_review_sheet_for_train_only(tmp_path):
    paths = write_data(tmp_path)
    module = load("error-analysis")
    out = tmp_path / "ea"
    module.main(["--predictions", str(paths["before"]), "--gold", str(paths["gold"]),
                 "--split-file", str(paths["split"]), "--output-dir", str(out)])
    text = (out / "error_analysis.md").read_text(encoding="utf-8")
    assert "**5** of 5 policies the experts coded as Framework" in text
    flagged = pd.read_csv(out / "error_rows.csv", dtype=str)
    assert set(flagged.sheet_row.astype(int)) == {2, 3, 4, 5, 6}  # train rows only
    sheets = pd.read_excel(out / "error_review.xlsx", sheet_name=None)
    assert set(patterns.PATTERNS) <= set(sheets)
    assert {"cause", "notes"} <= set(sheets["P1_scope"].columns)


def test_doc_kind_guess():
    module = load("error-analysis")
    assert module.doc_kind("Brazil's Nationally Determined Contribution – Second NDC") == "NDC"
    assert module.doc_kind("National CCUS Strategy") == "strategy/plan"
    assert module.doc_kind("Climate Change Act 2022") == "law/regulation"
    assert module.doc_kind("UK Emissions Trading Scheme") == "scheme/fund/market"


def test_compare_counts_fixed_and_broken(tmp_path):
    paths = write_data(tmp_path)
    module = load("compare-prompts")
    out = tmp_path / "cmp"
    module.main(["--before", f"v1={paths['before']}", "--after", f"v2={paths['after']}",
                 "--gold", str(paths["gold"]), "--split-file", str(paths["split"]), "--output-dir", str(out)])
    table = pd.read_csv(out / "prompt_comparison.csv").set_index("field")
    assert table.at["Policy_scope", "fixed"] == 5 and table.at["Policy_scope", "broken"] == 0
    assert table.at["Policy_scope", "accuracy_v1"] == 0 and table.at["Policy_scope", "accuracy_v2"] == 1
    # row 2 is in the train split, so the new Target_binding error is not in the test comparison
    assert table.at["Target_binding", "broken"] == 0
    text = (out / "prompt_comparison.md").read_text(encoding="utf-8")
    assert "Framework coded as Instrument | 5 | 0" in text
    assert "Policies compared: 5" in text


def test_compare_reports_new_errors(tmp_path):
    paths = write_data(tmp_path)
    module = load("compare-prompts")
    out = tmp_path / "cmp_all"
    module.main(["--before", f"v1={paths['before']}", "--after", f"v2={paths['after']}",
                 "--gold", str(paths["gold"]), "--only-split", "none", "--output-dir", str(out)])
    flips = pd.read_csv(out / "flips.csv", dtype=str)
    broken = flips[flips.change == "broken"]
    assert list(broken.field) == ["Target_binding"] and list(broken.sheet_row) == ["2"]
