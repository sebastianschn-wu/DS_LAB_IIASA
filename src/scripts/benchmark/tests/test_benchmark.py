"""Tests for the benchmark (no model, no internet).

Run from the repository root:
    python -m pytest src/scripts/benchmark/tests -q
"""

import importlib.util
from pathlib import Path

import pandas as pd
import pytest

from constants import NONE_LABEL
from metrics import (
    label_set,
    multi_metrics,
    rouge_l_f1,
    rouge_n_f1,
    single_label,
    single_metrics,
)

SCRIPT = Path(__file__).resolve().parents[1] / "benchmark.script.py"


def test_labels_ignore_case_subscript_and_order():
    assert single_label(" Cross-cutting ") == single_label("cross-cutting")
    assert single_label(None) == single_label("") == NONE_LABEL
    assert label_set("CO₂ transport; Novel CDR") == label_set("novel cdr;CO2 transport")


def test_single_metrics_accuracy_and_macro_f1():
    gold = ["supply", "supply", "demand", NONE_LABEL]
    pred = ["supply", "demand", "demand", NONE_LABEL]
    summary, per_label = single_metrics(gold, pred)
    assert summary["accuracy"] == pytest.approx(0.75)
    assert summary["n_gold_set"] == 3 and summary["accuracy_gold_set"] == pytest.approx(2 / 3)
    supply = next(r for r in per_label if r["label"] == "supply")
    assert (supply["precision"], supply["recall"]) == (1.0, 0.5)


def test_multi_metrics_exact_match_jaccard_and_micro_f1():
    gold = [frozenset({"a", "b"}), frozenset({"a"}), frozenset({NONE_LABEL})]
    pred = [frozenset({"a"}), frozenset({"a"}), frozenset({NONE_LABEL})]
    summary, per_label = multi_metrics(gold, pred)
    assert summary["accuracy"] == pytest.approx(2 / 3)
    assert summary["jaccard"] == pytest.approx((0.5 + 1 + 1) / 3)
    # tp=2 (a twice), fn=1 (b), fp=0
    assert summary["micro_precision"] == 1.0 and summary["micro_recall"] == pytest.approx(2 / 3)
    assert NONE_LABEL not in {r["label"] for r in per_label}


def test_rouge_scores():
    assert rouge_n_f1("storage of CO2 underground", "storage of CO2 underground") == 1.0
    assert rouge_l_f1("a b c d", "a c d") == pytest.approx(2 * 1 * 0.75 / 1.75)
    assert rouge_l_f1("a b", "") == 0.0


def test_full_run_on_small_example(tmp_path):
    spec = importlib.util.spec_from_file_location("benchmark_script", SCRIPT)
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)

    gold = pd.DataFrame({
        "sheet_row": ["2", "3", "4"], "policy_id": ["AUS-002", "AUS-003", "DEU-004"],
        "Jurisdiction": ["Australia", "Australia", "Germany"], "Iso": ["AUS", "AUS", "DEU"],
        "Document_full_title": ["A", "B", "C"],
        "Policy_scope": ["Framework", "Instrument", "Instrument"],
        "Value_chain_focus": ["Cross-cutting", "Supply", "Demand"],
        "Instrument_broad": ["Other", "Economic instrument", "Regulatory instrument"],
        "Target_type": ["Emissions", None, None], "Target_binding": ["No", None, None],
        "compliance_market_type": [None, None, "limited_share"],
        "Broad_method": ["Multiple", "Novel CDR", "Novel CDR; Enabling infrastructure"],
        "Specific_method": ["Multiple", "Biochar soil amendment", "CO₂ geological storage"],
        "Instrument_type": ["target", "capital_subsidy", "compliance_market_integration"],
        "Years_amended": [None, "2020", None],
        "CDR_link": ["Sets a net zero target.", "Grants for biochar.", "Allows removals in the ETS."],
    })
    pred = gold.drop(columns=["policy_id", "Iso"]).copy()
    pred["Policy_scope"] = ["Instrument", "Instrument", "Instrument"]
    pred["CDR_link"] = ["Net zero target for 2050.", "Grants for biochar.", "Removal credits in the ETS."]
    pred["source_used"] = ["summary", "document", "document"]
    pred["fallback_reason"] = ["fetch_failed", None, None]
    pred["model"] = "qwen2.5"
    gold_path, pred_path, out = tmp_path / "gold.csv", tmp_path / "pred.csv", tmp_path / "out"
    gold.to_csv(gold_path, index=False)
    pred.to_csv(pred_path, index=False)

    script.main(["--gold", str(gold_path), "--predictions", str(pred_path), "--output-dir", str(out)])

    fields = pd.read_csv(out / "field_metrics.csv")
    scope = fields[(fields.field == "Policy_scope")].set_index("subset")["accuracy"]
    assert scope["all"] == pytest.approx(2 / 3)
    assert scope["document"] == 1.0 and scope["summary"] == 0.0
    assert (out / "accuracy_by_source.png").exists()
    summary = (out / "benchmark_summary.md").read_text()
    assert "Framework* → model *Instrument*: 1x" in summary
