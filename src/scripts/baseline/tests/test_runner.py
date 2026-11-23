"""End-to-end run of the baseline script with a fake model and fake downloads."""

import csv
import importlib.util
import json
from pathlib import Path

import pytest

import retrieval

BASELINE = Path(__file__).resolve().parents[1] / "baseline.script.py"


def load_runner():
    spec = importlib.util.spec_from_file_location("baseline_script", BASELINE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def setup(monkeypatch):
    runner = load_runner()
    fl = runner.load_script(runner.FIRST_LOOP, "first_loop_test")
    calls = []

    def fake_fetch(fl_module, session, url, cache_dir):
        # every second policy fails, the others return a long PDF
        if len(calls) % 2:
            return retrieval.result(retrieval.OUTCOME_ERROR, error="HTTPError: 403")
        text = "Article 1. Purpose.\n" + "\n".join("Paragraph %d on forest carbon sinks and removals." % i
                                                    for i in range(3000))
        return retrieval.result(retrieval.OUTCOME_OK, text, fl_module.estimate_tokens(text), True, url)

    def fake_call(host, model, instructions, prompt, num_ctx, temperature):
        calls.append({"instructions": instructions, "prompt": prompt})
        return json.dumps({"Policy_scope": "Framework", "Value_chain_focus": "Cross-cutting",
                           "Instrument_type": "target; Other", "Broad_method": "Conventional CDR"})

    monkeypatch.setattr(retrieval, "fetch_full", fake_fetch)
    monkeypatch.setattr(fl, "ensure_ollama", lambda host, model: None)
    monkeypatch.setattr(fl, "call_model", fake_call)
    return runner, fl, calls


def read(path):
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def test_retrieved_run_never_sends_the_expert_summary(setup, tmp_path):
    runner, fl, calls = setup
    out = tmp_path / "run.csv"
    runner.main(["--limit", "4", "--output", str(out), "--cache-dir", str(tmp_path / "cache")], fl=fl)
    rows = read(out)
    assert len(rows) == 4 and len(calls) == 4
    policies = {p[fl.COL_SHEET_ROW]: p for p in fl.load_policies(fl.DEFAULT_SHEET)}
    for row, call in zip(rows, calls):
        summary = policies[row["sheet_row"]].get("CDR_link", "")
        if summary:
            assert summary not in call["prompt"]
    kinds = [row["input_type"] for row in rows]
    assert kinds == ["policy_text", "no_text", "policy_text", "no_text"]
    assert rows[0]["excerpted"] == "yes"
    assert int(rows[0]["tokens_sent"]) <= 6100
    assert rows[1]["source_used"] == "metadata"
    assert rows[0]["Policy_scope"] == "Framework"
    assert rows[0]["prompt_version"] == "v1"


def test_only_test_split_is_coded(setup, tmp_path):
    runner, fl, _ = setup
    out = tmp_path / "run.csv"
    runner.main(["--limit", "3", "--output", str(out), "--cache-dir", str(tmp_path / "c")], fl=fl)
    split = runner.read_split(runner.DEFAULT_SPLIT_FILE)
    assert all(split[row["sheet_row"]] == "test" for row in read(out))


def test_v2_adds_rules_and_changes_header(setup, tmp_path):
    runner, fl, calls = setup
    out = tmp_path / "v2.csv"
    runner.main(["--prompt", "v2", "--limit", "1", "--output", str(out), "--cache-dir", str(tmp_path / "c")], fl=fl)
    assert "Coding clarifications" in calls[0]["instructions"]
    assert "Code this policy" in calls[0]["prompt"]
    assert read(out)[0]["prompt_version"] == "v2"


def test_summary_mode_uses_only_the_summary(setup, tmp_path):
    runner, fl, calls = setup
    out = tmp_path / "summary.csv"
    runner.main(["--input", "summary", "--limit", "2", "--output", str(out)], fl=fl)
    rows = read(out)
    assert {row["input_type"] for row in rows} <= {"expert_summary", "no_text"}
    assert all(row["source_used"] in ("summary", "metadata") for row in rows)


def test_skip_policies_without_text(setup, tmp_path):
    runner, fl, calls = setup
    out = tmp_path / "skip.csv"
    runner.main(["--no-text", "skip", "--limit", "2", "--output", str(out), "--cache-dir", str(tmp_path / "c")],
                fl=fl)
    rows = read(out)
    assert rows[1]["source_used"] == "omitted" and len(calls) == 1


def test_resume_skips_finished_rows(setup, tmp_path):
    runner, fl, calls = setup
    out = tmp_path / "resume.csv"
    args = ["--limit", "2", "--output", str(out), "--cache-dir", str(tmp_path / "c")]
    runner.main(args, fl=fl)
    runner.main(args, fl=fl)
    assert len(read(out)) == 4


def test_schema_only_allows_codebook_values(setup):
    runner, fl, _ = setup
    allowed = fl.load_allowed_values(fl.DEFAULT_SHEET)
    schema = runner.json_schema(fl, allowed)
    assert set(schema["required"]) == set(fl.MODEL_FIELDS)
    assert schema["properties"]["Value_chain_focus"]["enum"] == allowed["Value_chain_focus"] + [""]
    assert "Regulatory instrument" not in schema["properties"]["Value_chain_focus"]["enum"]
    assert schema["properties"]["Instrument_type"]["type"] == "array"
    assert schema["properties"]["CDR_link"] == {"type": "string"}


def test_rag_context_and_rows_file(setup, tmp_path):
    runner, fl, calls = setup
    rows_file = tmp_path / "rows.csv"
    split = runner.read_split(runner.DEFAULT_SPLIT_FILE)
    test_rows = [row for row, part in split.items() if part == "test"][:2]
    rows_file.write_text("sheet_row\n" + "\n".join(test_rows) + "\n", encoding="utf-8")
    out = tmp_path / "rag.csv"
    runner.main(["--context", "rag", "--retriever", "bm25", "--rows", str(rows_file), "--no-text", "skip",
                 "--output", str(out), "--cache-dir", str(tmp_path / "c")], fl=fl)
    rows = read(out)
    assert [row["sheet_row"] for row in rows] == test_rows
    assert rows[0]["excerpted"].startswith("rag")
    assert int(rows[0]["tokens_sent"]) <= 6100
    assert "passages most relevant to the coding questions" in calls[0]["prompt"]
    assert rows[1]["source_used"] == "omitted"  # fake download failed, skipped


def test_default_output_name(setup):
    runner, _, _ = setup
    args = runner.parse_args(["--prompt", "v2", "--context", "rag", "--rows", "x/document_policies_test.csv"])
    assert runner.default_output(args).name == "retrieved_v2_rag2_document_policies_test.csv"
