"""Code one policy: choose the source text, build the prompt, call the model, clean the answer."""

from __future__ import annotations

import json
import re
import time
from datetime import datetime
from typing import Any

from constants import (
    CLOSED_FIELDS,
    COL_CODED_AT,
    COL_DOCUMENT_TITLE,
    COL_DOCUMENT_TOKENS,
    COL_FALLBACK_REASON,
    COL_FETCH_ERROR,
    COL_ISO,
    COL_JURISDICTION,
    COL_LINK,
    COL_MODEL,
    COL_MODEL_ERROR,
    COL_OMIT_REASON,
    COL_SOURCE_USED,
    COL_TOKENS_LOWER_BOUND,
    COL_VALIDATION_NOTES,
    COL_YEAR_ENACTED,
    EMPTY_MODEL_VALUES,
    FALLBACK_BY_OUTCOME,
    FALLBACK_EMPTY_DOCUMENT,
    FALLBACK_OVER_TOKEN_THRESHOLD,
    FETCH_ERROR,
    FETCH_OUTCOME,
    FETCH_TEXT,
    FETCH_TOKENS,
    FETCH_TOKENS_LOWER_BOUND,
    IDENTITY_COLUMNS,
    JSON_OBJECT_ERROR,
    LABEL_DOCUMENT_TITLE,
    LABEL_ISO,
    LABEL_JURISDICTION,
    LABEL_URL,
    LABEL_YEAR_ENACTED,
    MODEL_CALL_ATTEMPTS,
    MODEL_FIELDS,
    MULTI_VALUE_FIELDS,
    NOTE_EXPECTED_SINGLE,
    NOTE_UNIT_OUTSIDE,
    NOTE_VALUE_OUTSIDE,
    OMIT_REASON_SUFFIX,
    OPEN_UNIT_FIELDS,
    OTHER_LABEL,
    OUTCOME_OK,
    RUN_COLUMNS,
    SOURCE_DOCUMENT,
    SOURCE_LABEL_DOCUMENT,
    SOURCE_LABEL_SUMMARY,
    SOURCE_OMITTED,
    SOURCE_SUMMARY,
    SUMMARY_COLUMN,
    SUMMARY_FALLBACK_DISABLED,
    TOKENS_LOWER_BOUND_NO,
    TOKENS_LOWER_BOUND_YES,
    USER_PROMPT_HEADER,
    USER_PROMPT_RETURN,
    USER_PROMPT_SOURCE_TEXT,
    USER_PROMPT_SOURCE_TYPE,
    VALUE_SEPARATOR,
)
from ollama_client import call_model
from text_utils import as_text, estimate_tokens, fold_label, normalize_text


# ------------------------------------------------------------ model answer
def parse_json_object(text: str) -> dict[str, Any]:
    """Parse the model output; tolerates ```json fences and text around the object."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start < 0 or end <= start:
            raise
        payload = json.loads(cleaned[start : end + 1])
    if not isinstance(payload, dict):
        raise ValueError(JSON_OBJECT_ERROR)
    return payload


def stringify_model_value(value: Any) -> str:
    """Lists become 'a; b', whole floats become ints, 'null'/'n/a'/... become empty."""
    if value is None:
        return ""
    if isinstance(value, list):
        return VALUE_SEPARATOR.join(s for s in (stringify_model_value(item) for item in value) if s)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value)
    text = as_text(value)
    return "" if text.casefold() in EMPTY_MODEL_VALUES else text


def label_lookup(choices: list[str]) -> dict[str, str]:
    """Folded label -> codebook label. Abbreviations in brackets also match,
    e.g. 'DACCS' -> 'Direct air capture with geological storage (DACCS)'."""
    lookup = {fold_label(choice): choice for choice in choices}
    for choice in choices:
        for abbreviation in re.findall(r"\(([A-Z][A-Za-z0-9]{1,9})\)", choice):
            lookup.setdefault(fold_label(abbreviation), choice)
    return lookup


def canonicalize(field: str, raw: Any, allowed: dict[str, list[str]]) -> tuple[str, list[str]]:
    """Map a model value to codebook spelling. Returns (value, validation notes)."""
    text = stringify_model_value(raw)
    if not text:
        return "", []
    choices = allowed.get(field)
    split = field in MULTI_VALUE_FIELDS or field in CLOSED_FIELDS
    pieces = [part.strip() for part in text.split(";")] if split else [text]
    pieces = [part for part in pieces if part]
    if not choices:
        return (VALUE_SEPARATOR.join(pieces) if field in MULTI_VALUE_FIELDS else text), []

    lookup = label_lookup(choices)
    notes: list[str] = []
    canonical: list[str] = []
    for piece in pieces:
        match = lookup.get(fold_label(piece))
        if match:
            canonical.append(match)
        elif lookup.get(OTHER_LABEL) and fold_label(piece).startswith(OTHER_LABEL):
            canonical.append(piece)
        elif field in OPEN_UNIT_FIELDS:
            canonical.append(piece)
            notes.append(NOTE_UNIT_OUTSIDE.format(field=field, piece=piece))
        else:
            canonical.append(piece)
            notes.append(NOTE_VALUE_OUTSIDE.format(field=field, piece=piece))

    if field not in MULTI_VALUE_FIELDS and len(pieces) > 1:
        notes.append(NOTE_EXPECTED_SINGLE.format(field=field))
    return VALUE_SEPARATOR.join(dict.fromkeys(canonical)), notes


def coerce_coding(payload: dict[str, Any], allowed: dict[str, list[str]]) -> tuple[dict[str, str], str]:
    """Bring every model field into codebook form; keys are matched case-insensitively."""
    folded = {str(key).strip().casefold(): value for key, value in payload.items()}
    coded: dict[str, str] = {}
    notes: list[str] = []
    for field in MODEL_FIELDS:
        raw = payload.get(field, folded.get(field.casefold(), ""))
        value, field_notes = canonicalize(field, raw, allowed)
        coded[field] = value
        notes.extend(field_notes)
    return coded, VALUE_SEPARATOR.join(notes)


# ------------------------------------------------------------ prompt + source
def build_user_prompt(policy: dict[str, str], source_label: str, source_text: str) -> str:
    return "\n".join(
        [
            USER_PROMPT_HEADER,
            f"{LABEL_JURISDICTION}: {policy.get(COL_JURISDICTION, '')}",
            f"{LABEL_ISO}: {policy.get(COL_ISO, '')}",
            f"{LABEL_DOCUMENT_TITLE}: {policy.get(COL_DOCUMENT_TITLE, '')}",
            f"{LABEL_YEAR_ENACTED}: {policy.get(COL_YEAR_ENACTED, '')}",
            f"{LABEL_URL}: {policy.get(COL_LINK, '')}",
            "",
            f"{USER_PROMPT_SOURCE_TYPE} {source_label}",
            USER_PROMPT_SOURCE_TEXT,
            source_text,
            "",
            USER_PROMPT_RETURN,
        ]
    )


def choose_source(
    policy: dict[str, str],
    fetched: dict[str, Any],
    max_doc_tokens: int,
    allow_summary: bool = True,
) -> tuple[str, str, str, str]:
    """Return (source text, source_used, fallback_reason, omit_reason).

    The summary is the expert-written ``CDR_link`` cell. It is also a field the model
    has to produce, so rows coded from it must not be scored on CDR_link.
    """
    outcome = fetched.get(FETCH_OUTCOME)
    if outcome == OUTCOME_OK and int(fetched.get(FETCH_TOKENS) or 0) <= max_doc_tokens:
        return as_text(fetched.get(FETCH_TEXT)), SOURCE_DOCUMENT, "", ""

    reason = FALLBACK_BY_OUTCOME.get(outcome, "") or (
        FALLBACK_OVER_TOKEN_THRESHOLD
        if int(fetched.get(FETCH_TOKENS) or 0) > max_doc_tokens
        else FALLBACK_EMPTY_DOCUMENT
    )
    if not allow_summary:
        return "", SOURCE_OMITTED, "", f"{reason}_{SUMMARY_FALLBACK_DISABLED}"

    summary = normalize_text(policy.get(SUMMARY_COLUMN, ""))
    if summary and estimate_tokens(summary) <= max_doc_tokens:
        return summary, SOURCE_SUMMARY, reason, ""
    return "", SOURCE_OMITTED, "", f"{reason}{OMIT_REASON_SUFFIX}"


def blank_result(policy: dict[str, str], model: str) -> dict[str, str]:
    row = {column: "" for column in IDENTITY_COLUMNS + RUN_COLUMNS + MODEL_FIELDS}
    for column in IDENTITY_COLUMNS:
        row[column] = policy.get(column, "")
    row[COL_MODEL] = model
    row[COL_CODED_AT] = datetime.now().isoformat(timespec="seconds")
    return row


def code_policy(
    policy: dict[str, str],
    fetched: dict[str, Any],
    instructions: str,
    allowed: dict[str, list[str]],
    host: str,
    model: str,
    max_doc_tokens: int,
    num_ctx: int,
    temperature: float,
    response_format: Any = "json",
    allow_summary: bool = True,
) -> dict[str, str]:
    """Code one policy and return its result row (identity, run info, model fields)."""
    row = blank_result(policy, model)
    row[COL_DOCUMENT_TOKENS] = str(fetched.get(FETCH_TOKENS) or "")
    row[COL_TOKENS_LOWER_BOUND] = (
        TOKENS_LOWER_BOUND_YES if fetched.get(FETCH_TOKENS_LOWER_BOUND) else TOKENS_LOWER_BOUND_NO
    )
    row[COL_FETCH_ERROR] = as_text(fetched.get(FETCH_ERROR))

    source_text, source_used, fallback_reason, omit_reason = choose_source(
        policy, fetched, max_doc_tokens, allow_summary
    )
    row[COL_SOURCE_USED] = source_used
    row[COL_FALLBACK_REASON] = fallback_reason
    row[COL_OMIT_REASON] = omit_reason
    if source_used == SOURCE_OMITTED:
        return row

    if source_used == SOURCE_DOCUMENT:
        source_label = SOURCE_LABEL_DOCUMENT
    else:
        source_label = SOURCE_LABEL_SUMMARY.format(fallback_reason=fallback_reason)
    prompt = build_user_prompt(policy, source_label, source_text)

    last_error, content = "", ""
    for _ in range(MODEL_CALL_ATTEMPTS):
        try:
            content = call_model(host, model, instructions, prompt, num_ctx, temperature, response_format)
            coded, notes = coerce_coding(parse_json_object(content), allowed)
            row.update(coded)
            row[COL_VALIDATION_NOTES] = notes
            row[COL_MODEL_ERROR] = ""
            return row
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            time.sleep(1)
    row[COL_MODEL_ERROR] = last_error
    if content:
        row[COL_MODEL_ERROR] += " | response: " + content[:500].replace("\n", " ")
    return row
