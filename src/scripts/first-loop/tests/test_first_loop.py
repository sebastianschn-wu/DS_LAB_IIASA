"""Tests for the first loop. They need no Ollama and no internet.

Run from the repository root:
    python -m pytest src/scripts/first-loop/tests -q
"""

from __future__ import annotations

import csv
import importlib.util
import json
from io import BytesIO
from pathlib import Path

import pytest

import codebook
import coding
import documents
import ollama_client
import results
from constants import (
    CLOSED_FIELDS,
    CSV_ENCODING,
    FETCH_OUTCOME,
    FETCH_TEXT,
    MODEL_FIELDS,
    MULTI_VALUE_FIELDS,
    OUTCOME_EMPTY,
    OUTCOME_OK,
    OUTCOME_OVER_THRESHOLD,
    RAW_SHEET,
    DEFAULT_CODEBOOK,
    SOURCE_DOCUMENT,
    SOURCE_OMITTED,
    SOURCE_SUMMARY,
)
from text_utils import estimate_tokens, fold_label

SCRIPT = Path(__file__).resolve().parents[1] / "first-loop.script.py"


@pytest.fixture(scope="module")
def allowed():
    return codebook.load_allowed_values(RAW_SHEET)


@pytest.fixture(scope="module")
def policies():
    return codebook.load_policies(RAW_SHEET)


# ------------------------------------------------------------------ text utils
def test_estimate_tokens_counts_cjk_as_one_token_each():
    assert estimate_tokens("abcd" * 10) == 10
    assert estimate_tokens("碳达峰") == 3


def test_fold_label_ignores_case_and_subscript():
    assert fold_label("CO₂  Geological storage") == fold_label("co2 geological storage")


# ------------------------------------------------------------------- codebook
def test_codebook_defines_every_model_field():
    prose, definitions = codebook.load_codebook(DEFAULT_CODEBOOK)
    assert len(prose) == 4
    assert [field for field in MODEL_FIELDS if field not in definitions] == []


def test_allowed_values_cover_closed_fields(allowed):
    assert [field for field in CLOSED_FIELDS if field not in allowed] == []
    assert "Cross-cutting" in allowed["Value_chain_focus"]


def test_instructions_list_all_fields(allowed):
    prose, definitions = codebook.load_codebook(DEFAULT_CODEBOOK)
    text = codebook.build_instructions(prose, definitions, allowed)
    for field in MODEL_FIELDS:
        assert f"- {field}" in text


def test_response_schema_restricts_closed_fields(allowed):
    schema = codebook.build_response_schema(allowed)
    assert schema["required"] == MODEL_FIELDS
    assert schema["properties"]["Value_chain_focus"]["enum"][-1] == ""  # empty is allowed
    assert schema["properties"]["Instrument_type"]["type"] == "array"
    assert set(schema["properties"]["Broad_method"]["items"]["enum"]) == set(allowed["Broad_method"])
    assert schema["properties"]["CDR_link"] == {"type": "string"}


def test_policies_are_loaded_with_sheet_rows(policies):
    assert len(policies) == 327
    assert policies[0]["sheet_row"] == "2"


# --------------------------------------------------------------- model answer
def test_parse_json_object_handles_fences_and_noise():
    assert coding.parse_json_object('```json\n{"a": 1}\n```') == {"a": 1}
    assert coding.parse_json_object('Here you go: {"a": 1} done') == {"a": 1}
    with pytest.raises(ValueError):
        coding.parse_json_object("[1, 2]")


def test_canonicalize_maps_spelling_and_abbreviations(allowed):
    value, notes = coding.canonicalize("Specific_method", "co2 geological storage; DACCS", allowed)
    assert value == "CO₂ geological storage; Direct air capture with geological storage (DACCS)"
    assert notes == []


def test_canonicalize_flags_several_values_in_single_field(allowed):
    value, notes = coding.canonicalize("Value_chain_focus", "Supply; Demand", allowed)
    assert value == "Supply; Demand"
    assert any("single value" in note for note in notes)


def test_canonicalize_flags_unknown_values_and_keeps_units(allowed):
    _, notes = coding.canonicalize("Policy_scope", "Programme", allowed)
    assert any("not in the codebook" in note for note in notes)
    value, notes = coding.canonicalize("Target_unit", "million trees", allowed)
    assert value == "million trees" and "outside the preferred unit list" in notes[0]


def test_coerce_coding_accepts_lists_and_case_insensitive_keys(allowed):
    coded, _ = coding.coerce_coding(
        {"policy_scope": "framework", "Broad_method": ["Novel CDR", "Enabling infrastructure"], "Target_year": 2030.0},
        allowed,
    )
    assert coded["Policy_scope"] == "Framework"
    assert coded["Broad_method"] == "Novel CDR; Enabling infrastructure"
    assert coded["Target_year"] == "2030"
    assert coded["Funding_sum"] == ""


# -------------------------------------------------------------- source choice
POLICY = {"CDR_link": "Sets a framework for permanent CO2 storage.", "sheet_row": "9"}


def test_choose_source_prefers_document():
    fetched = {FETCH_OUTCOME: OUTCOME_OK, "tokens": 100, FETCH_TEXT: "full text"}
    assert coding.choose_source(POLICY, fetched, 6000)[:2] == ("full text", SOURCE_DOCUMENT)


def test_choose_source_falls_back_to_summary_when_too_long():
    fetched = {FETCH_OUTCOME: OUTCOME_OVER_THRESHOLD, "tokens": 9000, FETCH_TEXT: ""}
    text, source, reason, _ = coding.choose_source(POLICY, fetched, 6000)
    assert (source, reason) == (SOURCE_SUMMARY, "over_token_threshold")
    assert text == POLICY["CDR_link"]


def test_choose_source_can_disable_summary_fallback():
    fetched = {FETCH_OUTCOME: OUTCOME_EMPTY, "tokens": 3, FETCH_TEXT: ""}
    _, source, _, omit = coding.choose_source(POLICY, fetched, 6000, allow_summary=False)
    assert source == SOURCE_OMITTED and omit == "empty_document_summary_fallback_disabled"


def test_choose_source_omits_without_summary():
    fetched = {FETCH_OUTCOME: OUTCOME_EMPTY, "tokens": 3, FETCH_TEXT: ""}
    _, source, _, omit = coding.choose_source({"sheet_row": "3"}, fetched, 6000)
    assert source == SOURCE_OMITTED and omit == "empty_document_and_no_summary"


# ------------------------------------------------------------------- Ollama
@pytest.mark.parametrize(
    "requested, installed, expected",
    [
        ("qwen2.5", ["qwen2.5:7b"], "qwen2.5:7b"),  # old version called 'qwen2.5' -> model not found
        ("qwen2.5", ["qwen2.5:latest"], "qwen2.5:latest"),
        ("qwen2.5:7b", ["qwen2.5:7b"], "qwen2.5:7b"),
        ("qwen2.5:14b", ["qwen2.5:7b"], None),  # explicit tag that is missing -> pull
        ("llama3.1", ["qwen2.5:7b"], None),
    ],
)
def test_resolve_model(requested, installed, expected):
    assert ollama_client.resolve_model(requested, installed) == expected


# ----------------------------------------------------------------- documents
class FakeResponse:
    def __init__(self, data: bytes, content_type: str, url: str):
        self._data, self.headers, self.url = data, {"Content-Type": content_type}, url

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size):
        yield self._data

    def close(self):
        pass


class FakeSession:
    def __init__(self, pages: dict[str, tuple[bytes, str]]):
        self.pages, self.calls = pages, []

    def get(self, url, **kwargs):
        self.calls.append(url)
        data, content_type = self.pages[url]
        return FakeResponse(data, content_type, url)


def test_html_to_text_drops_navigation():
    html = "<html><nav>Home Menu Login</nav><main><p>Article 1. CO2 storage permits.</p></main><footer>Imprint</footer></html>"
    assert documents.html_to_text(html) == "Article 1. CO2 storage permits."


def test_fetch_document_reads_html_and_uses_cache(tmp_path):
    text = "This regulation sets permitting rules for geological storage of carbon dioxide. " * 5
    session = FakeSession({"https://x.test/law": (f"<p>{text}</p>".encode(), "text/html; charset=utf-8")})
    first = documents.fetch_document(session, "https://x.test/law", 6000, tmp_path)
    second = documents.fetch_document(session, "https://x.test/law", 6000, tmp_path)
    assert first[FETCH_OUTCOME] == OUTCOME_OK and first == second
    assert session.calls == ["https://x.test/law"]  # second call came from the cache


def test_fetch_document_marks_long_documents(tmp_path):
    session = FakeSession({"https://x.test/long": (("<p>" + "word " * 40000 + "</p>").encode(), "text/html")})
    fetched = documents.fetch_document(session, "https://x.test/long", 6000, tmp_path)
    assert fetched[FETCH_OUTCOME] == OUTCOME_OVER_THRESHOLD and fetched["tokens"] > 6000


def test_fetch_document_follows_pdf_link_from_empty_landing_page(tmp_path):
    canvas_module = pytest.importorskip("reportlab.pdfgen.canvas")
    buffer = BytesIO()
    pdf = canvas_module.Canvas(buffer)
    pdf.drawString(72, 720, "Carbon Dioxide Storage Act. Section 1: purpose of permanent storage of CO2 underground.")
    pdf.drawString(72, 700, "Section 2: permits are required for exploration and storage sites of carbon dioxide.")
    pdf.save()
    session = FakeSession({
        "https://x.test/page": (b'<html><a href="/doc.pdf">PDF</a></html>', "text/html"),
        "https://x.test/doc.pdf": (buffer.getvalue(), "application/pdf"),
    })
    fetched = documents.fetch_document(session, "https://x.test/page", 6000, tmp_path)
    assert fetched[FETCH_OUTCOME] == OUTCOME_OK
    assert "Carbon Dioxide Storage Act" in fetched[FETCH_TEXT]


# ---------------------------------------------------------- end-to-end run
def load_script():
    spec = importlib.util.spec_from_file_location("first_loop_script", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_full_run_with_fake_model(tmp_path, monkeypatch, allowed):
    script = load_script()
    model_answer = {field: "" for field in MODEL_FIELDS}
    model_answer.update({
        "Policy_scope": "Instrument",
        "CDR_link": "Regulates geological CO2 storage.",
        "Broad_method": ["Enabling infrastructure"],
        "Specific_method": ["CO₂ geological storage"],
        "Value_chain_focus": "Cross-cutting",
        "Instrument_broad": "Regulatory instrument",
        "Instrument_type": ["regulatory_safeguard", "mrv_standard"],
    })
    sent = []

    def fake_fetch(session, url, max_doc_tokens, cache_dir):
        # every second document is too long -> summary fallback
        long = len(sent) % 2 == 1
        return {FETCH_OUTCOME: OUTCOME_OVER_THRESHOLD if long else OUTCOME_OK,
                "tokens": 9000 if long else 120, "tokens_lower_bound": long,
                FETCH_TEXT: "" if long else "Full text of the law about CO2 storage."}

    def fake_call(host, model, instructions, prompt, num_ctx, temperature, response_format):
        sent.append({"model": model, "format": response_format, "prompt": prompt})
        return json.dumps(model_answer)

    monkeypatch.setattr(script, "ensure_ollama", lambda host, model: "qwen2.5:7b")
    monkeypatch.setattr(script, "fetch_document", fake_fetch)
    monkeypatch.setattr(coding, "call_model", fake_call)

    output = tmp_path / "out.csv"
    script.main(["--sheet", str(RAW_SHEET), "--output", str(output), "--limit", "4"])

    with output.open(encoding=CSV_ENCODING) as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 4
    assert {row["source_used"] for row in rows} == {SOURCE_DOCUMENT, SOURCE_SUMMARY}
    assert rows[0]["Instrument_type"] == "regulatory_safeguard; mrv_standard"
    assert all(call["model"] == "qwen2.5:7b" for call in sent)
    assert isinstance(sent[0]["format"], dict)  # JSON schema is sent by default
    # expert category values are never part of the prompt
    assert "Value_chain_focus" not in sent[0]["prompt"]

    # second run continues where the first stopped and skips completed rows
    sent.clear()
    script.main(["--sheet", str(RAW_SHEET), "--output", str(output), "--limit", "2"])
    with output.open(encoding=CSV_ENCODING) as handle:
        assert len(list(csv.DictReader(handle))) == 6
    assert "source_used=summary" in results.run_summary(rows)
