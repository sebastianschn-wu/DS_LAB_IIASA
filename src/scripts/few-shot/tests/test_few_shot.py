"""Tests for the few-shot add-on (no Ollama, no internet).

Run from the repository root:
    python -m pytest src/scripts/few-shot/tests -q
"""

from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path

import pytest

from examples import EXAMPLE_ROWS, read_split, render_examples, select_examples

HERE = Path(__file__).resolve().parents[1]
REPO_ROOT = HERE.parents[2]
SPLIT_FILE = REPO_ROOT / "src" / "resources" / "train_test_split.csv"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def first_loop():
    return load("first_loop_for_tests", REPO_ROOT / "src/scripts/first-loop/first-loop.script.py")


@pytest.fixture(scope="module")
def policies(first_loop):
    return first_loop.load_policies(first_loop.DEFAULT_SHEET)


def test_split_covers_every_policy(policies):
    split = read_split(SPLIT_FILE)
    assert {p["sheet_row"] for p in policies} == set(split)
    assert sum(v == "test" for v in split.values()) == 99


def test_examples_are_train_policies(policies):
    split = read_split(SPLIT_FILE)
    assert all(split[row] == "train" for row, _ in EXAMPLE_ROWS)
    assert [p["sheet_row"] for p in select_examples(policies, 3)] == ["19", "43", "73"]
    assert select_examples(policies, 0) == []
    with pytest.raises(SystemExit):
        select_examples(policies, 9)


def test_rendered_example_uses_expert_coding(first_loop, policies):
    example = select_examples(policies, 1)[0]
    text = render_examples([example], first_loop.MODEL_FIELDS)
    coding = json.loads(text.splitlines()[-1])
    assert list(coding) == first_loop.MODEL_FIELDS
    assert coding["Policy_scope"] == "Framework" and coding["Value_chain_focus"] == "Cross-cutting"
    assert coding["Comments"] == ""
    assert render_examples([], first_loop.MODEL_FIELDS) == ""


def test_few_shot_run_uses_unchanged_first_loop(tmp_path, monkeypatch):
    script = load("few_shot_script", HERE / "few-shot.script.py")
    first_loop = script.load_first_loop()
    seen = []

    def fake_call(host, model, instructions, prompt, num_ctx, temperature):
        seen.append(instructions)
        return json.dumps({field: "" for field in first_loop.MODEL_FIELDS} | {"Policy_scope": "Framework"})

    monkeypatch.setattr(script, "load_first_loop", lambda: first_loop)
    monkeypatch.setattr(first_loop, "ensure_ollama", lambda host, model: None)
    monkeypatch.setattr(first_loop, "fetch_document",
                        lambda *a: first_loop.fetch_payload(first_loop.OUTCOME_OK, 100, False, "Policy text."))
    monkeypatch.setattr(first_loop, "call_model", fake_call)

    output = tmp_path / "shots3.csv"
    script.main(["--shots", "3", "--limit", "4", "--output", str(output)])

    split = read_split(SPLIT_FILE)
    with output.open(encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 4 and all(split[r["sheet_row"]] == "test" for r in rows)
    assert seen[0].count("\nExample ") == 3
    assert "Worked examples" in seen[0]
