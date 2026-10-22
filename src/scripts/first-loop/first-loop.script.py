#!/usr/bin/env python3
"""Code CDR policies with a local Ollama model (first loop, zero-shot).

For each policy in the sheet the script downloads the linked document, sends it
together with the codebook to the model and stores the coding. Previously coded
category values are never sent to the model.

If a document is longer than ``--max-doc-tokens``, cannot be downloaded or has no
text, the row's ``CDR_link`` sentence is sent instead (summary fallback). That
sentence is written by the experts and is itself a field the model must produce,
so rows with ``source_used=summary`` must not be scored on CDR_link. Use
``--no-summary-fallback`` to leave these rows out instead.

Results go to ``results/first_loop_coding.csv`` and are saved after every row, so a
run can be stopped and continued. Completed rows are skipped unless ``--force``.

Modules:
    constants.py      paths, column names, prompt text
    text_utils.py     token estimate and text helpers
    codebook.py       codebook/sheet loading, instructions, JSON schema
    documents.py      download + PDF/HTML text extraction + cache
    ollama_client.py  Ollama server/model handling and the chat call
    coding.py         source choice, prompt, answer cleaning, one-policy coding
    results.py        results CSV and run summary

Usage:
    python src/scripts/first-loop/first-loop.script.py
    python src/scripts/first-loop/first-loop.script.py --limit 5
    python src/scripts/first-loop/first-loop.script.py --model qwen2.5:7b --max-doc-tokens 12000
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

_SCRIPT_DIR = str(Path(__file__).resolve().parent)
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from codebook import (  # noqa: E402
    build_instructions,
    build_response_schema,
    load_allowed_values,
    load_codebook,
    load_policies,
)
from coding import blank_result, code_policy  # noqa: E402
from constants import (  # noqa: E402
    COL_DOCUMENT_TITLE,
    COL_DOCUMENT_TOKENS,
    COL_FALLBACK_REASON,
    COL_JURISDICTION,
    COL_LINK,
    COL_MODEL_ERROR,
    COL_OMIT_REASON,
    COL_SHEET_ROW,
    COL_SOURCE_USED,
    DEFAULT_CODEBOOK,
    DEFAULT_HOST,
    DEFAULT_MAX_DOC_TOKENS,
    DEFAULT_MODEL,
    DEFAULT_OUTPUT,
    DEFAULT_SHEET,
    MIN_DOCUMENT_TOKENS,
    MISSING_LINK_ERROR,
    OLLAMA_CONTEXT_CAP,
    OLLAMA_CONTEXT_FLOOR,
    OLLAMA_CONTEXT_RESERVE,
    OLLAMA_CONTEXT_SAFETY_FACTOR,
    OUTCOME_ERROR,
    SOURCE_CACHE_DIRNAME,
    SOURCE_ERROR,
)
from documents import fetch_document, fetch_payload, make_session  # noqa: E402
from ollama_client import ensure_ollama  # noqa: E402
from results import is_complete, load_existing, run_summary, write_results  # noqa: E402
from text_utils import estimate_tokens  # noqa: E402


def context_window(instruction_tokens: int, max_doc_tokens: int) -> int:
    """num_ctx for Ollama: instructions + document with a safety margin + room for the answer."""
    needed = int((instruction_tokens + max_doc_tokens) * OLLAMA_CONTEXT_SAFETY_FACTOR) + OLLAMA_CONTEXT_RESERVE
    return min(OLLAMA_CONTEXT_CAP, max(OLLAMA_CONTEXT_FLOOR, needed))


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sheet", type=Path, default=DEFAULT_SHEET,
                        help="Policy sheet (default: cleaned sheet if it exists, else the raw resource sheet)")
    parser.add_argument("--codebook", type=Path, default=DEFAULT_CODEBOOK)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Local Ollama model name. Default: {DEFAULT_MODEL}")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--max-doc-tokens", type=int, default=DEFAULT_MAX_DOC_TOKENS,
                        help=f"Maximum estimated document tokens sent to the model. Default: {DEFAULT_MAX_DOC_TOKENS}")
    parser.add_argument("--limit", type=int, default=0, help="Code at most this many pending policies. 0 codes all.")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--force", action="store_true", help="Recode rows already present in the output CSV.")
    parser.add_argument("--no-schema", action="store_true",
                        help="Ask only for free JSON instead of the codebook JSON schema (for Ollama < 0.5).")
    parser.add_argument("--no-summary-fallback", action="store_true",
                        help="Do not send the expert CDR_link sentence when the document cannot be used; omit the row.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.max_doc_tokens < MIN_DOCUMENT_TOKENS:
        raise SystemExit(f"--max-doc-tokens must be at least {MIN_DOCUMENT_TOKENS}")
    host = args.host.rstrip("/")

    prose, definitions = load_codebook(args.codebook)
    allowed = load_allowed_values(args.sheet)
    policies = load_policies(args.sheet)
    instructions = build_instructions(prose, definitions, allowed)
    response_format = "json" if args.no_schema else build_response_schema(allowed)
    num_ctx = context_window(estimate_tokens(instructions), args.max_doc_tokens)

    print(f"Sheet: {args.sheet}")
    print(f"Policies in sheet: {len(policies)}")
    print(f"Codebook instruction tokens (estimate): {estimate_tokens(instructions)}")
    print(f"Document token threshold: {args.max_doc_tokens}")
    print(f"Ollama context window: {num_ctx}")
    print(f"Output format: {'free JSON' if args.no_schema else 'codebook JSON schema'}")
    print(f"Summary fallback: {'off' if args.no_summary_fallback else 'on (expert CDR_link sentence)'}")

    model = ensure_ollama(host, args.model)

    cache_dir = args.output.parent / SOURCE_CACHE_DIRNAME
    results = {} if args.force else load_existing(args.output)
    session = make_session()

    pending = [p for p in policies if args.force or not is_complete(results.get(p[COL_SHEET_ROW], {}))]
    if args.limit:
        pending = pending[: args.limit]
    print(f"Policies to code this run: {len(pending)}")

    for index, policy in enumerate(pending, start=1):
        print(f"[{index}/{len(pending)}] row {policy[COL_SHEET_ROW]} "
              f"{policy.get(COL_JURISDICTION, '')} | {policy.get(COL_DOCUMENT_TITLE, '')}")
        link = policy.get(COL_LINK, "")
        try:
            fetched = (
                fetch_document(session, link, args.max_doc_tokens, cache_dir)
                if link
                else fetch_payload(OUTCOME_ERROR, 0, False, "", MISSING_LINK_ERROR)
            )
            row = code_policy(
                policy, fetched, instructions, allowed, host, model, args.max_doc_tokens, num_ctx,
                args.temperature, response_format, allow_summary=not args.no_summary_fallback,
            )
        except Exception as exc:
            row = blank_result(policy, model)
            row[COL_SOURCE_USED] = SOURCE_ERROR
            row[COL_MODEL_ERROR] = f"{type(exc).__name__}: {exc}"
        results[policy[COL_SHEET_ROW]] = row
        ordered = [results[p[COL_SHEET_ROW]] for p in policies if p[COL_SHEET_ROW] in results]
        write_results(args.output, ordered)
        print(f"    source={row[COL_SOURCE_USED]} tokens={row[COL_DOCUMENT_TOKENS] or '-'} "
              f"fallback={row[COL_FALLBACK_REASON] or '-'} omit={row[COL_OMIT_REASON] or '-'}"
              + (f" ERROR={row[COL_MODEL_ERROR][:80]}" if row[COL_MODEL_ERROR] else ""))
        if link:
            time.sleep(0.4)

    ordered = [results[p[COL_SHEET_ROW]] for p in policies if p[COL_SHEET_ROW] in results]
    print(f"\nWrote {args.output}")
    print(run_summary(ordered))


if __name__ == "__main__":
    main()
