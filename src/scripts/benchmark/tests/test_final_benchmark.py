"""Final benchmark on small synthetic runs."""

import importlib.util
from pathlib import Path

import pandas as pd

SCRIPT = Path(__file__).resolve().parents[1] / "final-benchmark.script.py"


def load():
    spec = importlib.util.spec_from_file_location("final_benchmark", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write(tmp_path):
    gold_rows = []
    for i in range(2, 22):
        gold_rows.append({"sheet_row": str(i), "policy_id": f"P{i}", "Jurisdiction": "Testland", "Iso": "TST",
                          "Document_full_title": f"Policy {i}", "Policy_scope": "Framework",
                          "Value_chain_focus": "Cross-cutting", "Instrument_broad": "Other", "Instrument_type": "target",
                          "Target_type": "Emissions", "Target_binding": "Yes", "compliance_market_type": "",
                          "Broad_method": "Multiple", "Specific_method": "Multiple", "Years_amended": "",
                          "CDR_link": "The plan sets a net zero target and expands forest sinks."})
    gold = pd.DataFrame(gold_rows)
    before = gold.copy()
    before["Policy_scope"] = "Instrument"
    before["Value_chain_focus"] = "Demand"
    before["input_type"] = "policy_text"
    before["excerpted"] = ["no"] * 10 + ["yes"] * 10
    before["validation_notes"] = ["Specific_method value 'X' is not in the codebook list"] + [""] * 19
    before["model_error"] = ""
    after = gold.copy()
    after["input_type"] = "policy_text"
    after["excerpted"] = ["no"] * 10 + ["rag+summary"] * 10
    after["validation_notes"] = ""
    after["model_error"] = ""
    after.loc[0, "Instrument_type"] = "target; mrv_standard"  # one new error
    rows = pd.DataFrame({"sheet_row": [str(i) for i in range(2, 20)]})  # 18 of 20 policies
    paths = {}
    for name, frame in {"gold": gold, "before": before, "after": after, "rows": rows}.items():
        paths[name] = tmp_path / f"{name}.csv"
        frame.to_csv(paths[name], index=False, encoding="utf-8-sig")
    return paths


def test_final_benchmark_report(tmp_path):
    paths = write(tmp_path)
    out = tmp_path / "final"
    load().main(["--run", f"v1={paths['before']}", "--run", f"v2 rag={paths['after']}", "--rows", str(paths["rows"]),
                 "--only-split", "none", "--gold", str(paths["gold"]), "--bootstrap", "200", "--output-dir", str(out)])
    text = (out / "final_benchmark.md").read_text(encoding="utf-8")
    assert "Policies: **18**" in text
    pairs = pd.read_csv(out / "paired.csv")
    assert pairs.loc[0, "Policy_scope_fixed"] == 18 and pairs.loc[0, "Value_chain_focus_fixed"] == 18
    assert pairs.loc[0, "Instrument_type_broken"] == 1
    assert pairs.loc[0, "ci_low"] > 0  # a clear improvement
    assert "Framework coded as Instrument | 18 | 0" in text
    assert "Rows with labels outside the codebook | 1 | 0" in text
    assert "RAG + own summary" in text
    assert (out / "final_core_fields.png").exists()
    per_policy = pd.read_csv(out / "per_policy.csv")
    assert len(per_policy) == 18
