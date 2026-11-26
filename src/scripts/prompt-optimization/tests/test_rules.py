"""Deterministic post-processing rules."""

import csv
import importlib.util
from pathlib import Path

import rules

SCRIPT = Path(__file__).resolve().parents[1] / "apply-rules.script.py"


def test_ndc_rule_sets_all_fields():
    row = {"Policy_scope": "Instrument", "Instrument_broad": "Other", "Value_chain_focus": "Demand",
           "Instrument_type": "target; mrv_standard", "Target_type": ""}
    new, applied = rules.apply_rules(row, "Brazil's Nationally Determined Contribution (NDC)")
    assert applied == ["R1_ndc"]
    assert new["Policy_scope"] == "Framework" and new["Instrument_type"] == "target"
    assert new["Target_type"] == "Emissions"


def test_framework_rule_uses_model_target():
    with_target = {"Policy_scope": "Framework", "Instrument_type": "target; Other; mrv_standard",
                   "Target_type": "CDR"}
    without = {"Policy_scope": "Framework", "Instrument_type": "rd_d_funding; mrv_standard", "Target_type": ""}
    assert rules.apply_rules(with_target, "Long-term strategy")[0]["Instrument_type"] == "target"
    assert rules.apply_rules(without, "Forestry roadmap")[0]["Instrument_type"] == "Other"


def test_instruments_are_left_alone():
    row = {"Policy_scope": "Instrument", "Instrument_type": "capital_subsidy; public_loan", "Target_type": ""}
    new, applied = rules.apply_rules(row, "Carbon Capture Infrastructure Fund")
    assert new == row and applied == []


def test_script_writes_rules_file(tmp_path):
    path = tmp_path / "run.csv"
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=["sheet_row", "Document_full_title", "Policy_scope",
                                                    "Instrument_type", "Target_type", "model_error"])
        writer.writeheader()
        writer.writerow({"sheet_row": "2", "Document_full_title": "Climate Strategy", "Policy_scope": "Framework",
                         "Instrument_type": "target; Other", "Target_type": "Emissions", "model_error": ""})
        writer.writerow({"sheet_row": "3", "Document_full_title": "X", "Policy_scope": "Framework",
                         "Instrument_type": "", "Target_type": "", "model_error": "JSONDecodeError"})
    spec = importlib.util.spec_from_file_location("apply_rules", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    out = module.main([str(path), "--gold", str(tmp_path / "missing.csv")])
    with out.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    assert out.name == "run_rules.csv"
    assert rows[0]["Instrument_type"] == "target" and rows[0]["rules_applied"] == "R2_framework"
    assert rows[1]["Instrument_type"] == "" and rows[1]["rules_applied"] == ""  # failed rows untouched
