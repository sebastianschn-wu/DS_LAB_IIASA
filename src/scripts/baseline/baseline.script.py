#!/usr/bin/env python3
"""Unbiased zero-shot baseline: code policies without any expert-written input.

Differences to the first loop (which stays unchanged and is reused for codebook
loading, prompt building, the Ollama call and output validation):

1. No expert text as input. The first loop sends the expert CDR_link summary
   whenever the document is missing or too long; CDR_link is also a field the
   model has to predict, so those rows leak the answer. Here:
     - long documents are shortened to their most relevant passages,
     - a PDF linked from a policy-database page is fetched,
     - if nothing can be retrieved, the model sees only the title and context
       (``--no-text title``, default) or the policy is skipped (``--no-text skip``).
2. Every row gets an ``input_type``: policy_text, webpage_description, no_text
   (or expert_summary in the ``--input summary`` control run), so results can be
   reported per input type (Elina's request).
3. Only the policies of one split are coded (default: the 99 test policies), so
   all runs are compared on the same independent sample.
4. ``--prompt v1|v2`` chooses the prompt (v2 = targeted clarifications, see
   ``src/scripts/prompt-optimization/prompt_versions.py``), ``--schema`` makes
   Ollama return only allowed values for closed fields.
5. ``--context rag`` replaces the keyword excerpt of long documents with RAG:
   the document's own summary section (if any), its beginning and the chunks
   retrieved for each coding question (see ``rag.py``). ``--rows FILE.csv``
   codes only the policies listed in a CSV (e.g. only those with a document).

``--input summary`` codes the same policies from the expert summary only. It is
not a fair test (the summary is expert interpretation) but shows how much
information the model needs, compared with the retrieved text.

Usage:
    python src/scripts/baseline/baseline.script.py                       # v1, test split
    python src/scripts/baseline/baseline.script.py --prompt v2           # revised prompt
    python src/scripts/baseline/baseline.script.py --input summary       # control: expert summary only
    python src/scripts/baseline/baseline.script.py --limit 3             # quick check
    python src/scripts/baseline/baseline.script.py --prompt v2 --context rag \
        --rows src/resources/document_policies_test.csv --no-text skip      # RAG, documents only

Output: results/baseline/<input>_<prompt>[_rag][_schema]_<split or rows file>.csv
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
FIRST_LOOP = REPO_ROOT / "src" / "scripts" / "first-loop" / "first-loop.script.py"
PROMPT_DIR = REPO_ROOT / "src" / "scripts" / "prompt-optimization"
DEFAULT_SPLIT_FILE = REPO_ROOT / "src" / "resources" / "train_test_split.csv"
DEFAULT_OVERRIDES = HERE / "input_type_overrides.csv"
RESULTS_DIR = REPO_ROOT / "results" / "baseline"
CACHE_DIR = REPO_ROOT / "results" / "source_cache" / "full_text"  # already git-ignored

for path in (HERE, PROMPT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import rag  # noqa: E402
import retrieval  # noqa: E402
from prompt_versions import PROMPT_V1, PROMPT_VERSIONS, instructions_for, user_prompt_header  # noqa: E402

# Same model as the first loop and the few-shot runs: the first loop's default
# "qwen2.5" is Ollama's alias for qwen2.5:7b (same model ID 845dbda0ea48, 7.6B
# parameters, Q4_K_M), so results are comparable. Written out here so the output
# CSVs name the size explicitly.
DEFAULT_MODEL = "qwen2.5:7b"
INPUT_RETRIEVED = "retrieved"
INPUT_SUMMARY_MODE = "summary"

# Extra output columns (after the first-loop run columns).
COL_INPUT_TYPE = "input_type"
COL_INPUT_REASON = "input_type_reason"
COL_PROMPT = "prompt_version"
COL_SCHEMA = "schema"
COL_EXCERPTED = "excerpted"
COL_TOKENS_SENT = "tokens_sent"
COL_FINAL_URL = "final_url"
EXTRA_COLUMNS = [COL_INPUT_TYPE, COL_INPUT_REASON, COL_PROMPT, COL_SCHEMA, COL_EXCERPTED,
                 COL_TOKENS_SENT, COL_FINAL_URL]

# source_used stays compatible with the benchmark script: "document" = retrieved text.
SOURCE_BY_INPUT = {
    retrieval.INPUT_POLICY_TEXT: "document",
    retrieval.INPUT_WEBPAGE: "document",
    retrieval.INPUT_NO_TEXT: "metadata",
    retrieval.INPUT_SUMMARY: "summary",
}
SOURCE_SKIPPED = "omitted"
SOURCE_ERROR = "error"

SOURCE_LABELS = {
    retrieval.INPUT_POLICY_TEXT: "text of the policy document retrieved from the policy link",
    retrieval.INPUT_WEBPAGE: (
        "webpage about the policy retrieved from the policy link "
        "(it may describe the policy rather than contain its full text)"
    ),
    retrieval.INPUT_NO_TEXT: (
        "none. No text could be retrieved from the policy link. Only the inventory context above is "
        "available: code only what the title clearly supports and leave all other fields empty"
    ),
    retrieval.INPUT_SUMMARY: "short summary of the policy written by the database team",
}
EXCERPT_NOTE = " (shortened: the beginning and the most relevant passages of a long document; [...] marks gaps)"
RAG_NOTE = (" (long document: its own summary section if it has one, its beginning, and the passages most "
            "relevant to the coding questions; [...] marks gaps)")
CONTEXT_KEYWORD = "keyword"
CONTEXT_RAG = "rag"
EMBED_CACHE_DIR = REPO_ROOT / "results" / "source_cache" / "embeddings"  # already git-ignored


def load_script(path: Path, name: str):
    """Import a script whose folder has its own ``constants`` module without clashing with other folders."""
    saved = {key: sys.modules.pop(key) for key in ("constants", "metrics") if key in sys.modules}
    sys.path.insert(0, str(path.parent))
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(path.parent))
        for key in ("constants", "metrics"):
            sys.modules.pop(key, None)
        sys.modules.update(saved)
    return module


def read_split(path: Path) -> dict[str, str]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return {row["sheet_row"].strip(): row["split"].strip() for row in csv.DictReader(handle)}


def json_schema(fl, allowed: dict[str, list[str]]) -> dict:
    """Ollama structured-output schema: closed fields may only take allowed values."""
    properties = {}
    for field in fl.MODEL_FIELDS:
        values = allowed.get(field)
        if field in fl.CLOSED_FIELDS and values:
            if field in fl.MULTI_VALUE_FIELDS:
                properties[field] = {"type": "array", "items": {"type": "string", "enum": values}}
            else:
                properties[field] = {"type": "string", "enum": values + [""]}
        else:
            properties[field] = {"type": "string"}
    return {"type": "object", "properties": properties, "required": list(fl.MODEL_FIELDS)}


def call_with_schema(fl, host, model, instructions, user_prompt, num_ctx, temperature, schema) -> str:
    response = fl.requests.post(
        f"{host}/api/chat",
        json={
            "model": model,
            "stream": False,
            "format": schema,
            "keep_alive": fl.OLLAMA_KEEP_ALIVE,
            "messages": [
                {"role": "system", "content": instructions},
                {"role": "user", "content": user_prompt},
            ],
            "options": {
                "temperature": temperature,
                "seed": fl.OLLAMA_SEED,
                "num_ctx": num_ctx,
                "num_predict": fl.OLLAMA_NUM_PREDICT,
            },
        },
        timeout=fl.OLLAMA_CHAT_TIMEOUT,
    )
    response.raise_for_status()
    content = response.json().get("message", {}).get("content", "")
    if not content:
        raise RuntimeError("empty model response")
    return content


def default_output(args) -> Path:
    schema = "_schema" if args.schema else ""
    context = ""
    if args.context == CONTEXT_RAG and args.input == INPUT_RETRIEVED:
        version = str(rag.RAG_VERSION) if rag.RAG_VERSION > 1 else ""
        retriever = "" if args.retriever == "keywords" else f"_{args.retriever}"
        context = f"_rag{version}{retriever}"
    scope = args.rows.stem if args.rows else args.split
    return RESULTS_DIR / f"{args.input}_{args.prompt}{context}{schema}_{scope}.csv"


def read_rows_file(path: Path) -> set[str]:
    """sheet_row values listed in a CSV (column 'sheet_row')."""
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if "sheet_row" not in (reader.fieldnames or []):
            raise SystemExit(f"{path} needs a 'sheet_row' column")
        return {row["sheet_row"].strip() for row in reader if (row.get("sheet_row") or "").strip()}


def make_retriever(fl, args):
    if args.context != CONTEXT_RAG or args.input != INPUT_RETRIEVED:
        return None
    if args.retriever == "keywords":
        return rag.KeywordRetriever()
    if args.retriever == "bm25":
        return rag.BM25Retriever()
    retriever = rag.OllamaEmbedRetriever(fl.requests, args.host, args.embed_model, args.embed_cache_dir)
    retriever.check()
    return retriever


def prepare_source(fl, policy, args, session, overrides, retriever=None) -> dict:
    """Source text, input type and bookkeeping for one policy."""
    if args.input == INPUT_SUMMARY_MODE:
        text = fl.normalize_text(policy.get(fl.SUMMARY_COLUMN, ""))
        kind = retrieval.INPUT_SUMMARY if text else retrieval.INPUT_NO_TEXT
        return {"text": text, "type": kind, "reason": "expert CDR_link summary" if text else "no summary",
                "excerpted": "", "full_tokens": fl.estimate_tokens(text), "final_url": "", "error": ""}

    link = policy.get(fl.COL_LINK, "")
    if link:
        fetched = retrieval.fetch_full(fl, session, link, args.cache_dir)
    else:
        fetched = retrieval.result(retrieval.OUTCOME_ERROR, error=fl.MISSING_LINK_ERROR)
    kind, reason = retrieval.classify(fetched, link)
    row_id = policy[fl.COL_SHEET_ROW]
    if row_id in overrides:
        kind, reason = overrides[row_id], "manual override"
    text = fetched.get("text", "") if kind != retrieval.INPUT_NO_TEXT else ""
    method = ""
    if text and fl.estimate_tokens(text) > args.max_doc_tokens:
        if retriever is not None:
            text, report = rag.build_context(text, args.max_doc_tokens, fl.estimate_tokens, retriever)
            method = "rag+summary" if report["summary"] else "rag+intro" if report.get("introduction") else "rag"
        else:
            text, _ = retrieval.excerpt(text, args.max_doc_tokens, fl.estimate_tokens)
            method = "yes"
    return {"text": text, "type": kind, "reason": reason, "excerpted": method,
            "full_tokens": int(fetched.get("tokens") or 0), "final_url": fetched.get("final_url", ""),
            "error": fetched.get("error", "")}


def code_one(fl, policy, source, instructions, allowed, args, num_ctx, schema) -> dict:
    row = fl.blank_result(policy, args.model)
    row.update({
        COL_INPUT_TYPE: source["type"],
        COL_INPUT_REASON: source["reason"],
        COL_PROMPT: args.prompt,
        COL_SCHEMA: "yes" if args.schema else "no",
        COL_EXCERPTED: source["excerpted"] or "no",
        COL_TOKENS_SENT: str(fl.estimate_tokens(source["text"])) if source["text"] else "0",
        COL_FINAL_URL: source["final_url"],
        fl.COL_DOCUMENT_TOKENS: str(source["full_tokens"] or ""),
        fl.COL_FETCH_ERROR: source["error"],
        fl.COL_SOURCE_USED: SOURCE_BY_INPUT[source["type"]],
    })
    if source["type"] == retrieval.INPUT_NO_TEXT and args.no_text == "skip":
        row[fl.COL_SOURCE_USED] = SOURCE_SKIPPED
        row[fl.COL_OMIT_REASON] = "no text retrieved"
        return row

    note = RAG_NOTE if source["excerpted"].startswith("rag") else EXCERPT_NOTE if source["excerpted"] else ""
    label = SOURCE_LABELS[source["type"]] + note
    prompt = fl.build_user_prompt(policy, label, source["text"])
    host = args.host.rstrip("/")
    last_error, content = "", ""
    for _ in range(fl.MODEL_CALL_ATTEMPTS):
        try:
            if schema is not None:
                content = call_with_schema(fl, host, args.model, instructions, prompt, num_ctx,
                                           args.temperature, schema)
            else:
                content = fl.call_model(host, args.model, instructions, prompt, num_ctx, args.temperature)
            coded, notes = fl.coerce_coding(fl.parse_json_object(content), allowed)
            row.update(coded)
            row[fl.COL_VALIDATION_NOTES] = notes
            row[fl.COL_MODEL_ERROR] = ""
            return row
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            time.sleep(1)
    row[fl.COL_MODEL_ERROR] = last_error + (" | response: " + content[:300].replace("\n", " ") if content else "")
    return row


def columns(fl) -> list[str]:
    return fl.IDENTITY_COLUMNS + fl.RUN_COLUMNS + EXTRA_COLUMNS + fl.MODEL_FIELDS


def write_rows(fl, path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", newline="", encoding=fl.CSV_ENCODING) as handle:
        writer = csv.DictWriter(handle, fieldnames=columns(fl), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def read_rows(fl, path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    with path.open(newline="", encoding=fl.CSV_ENCODING) as handle:
        return {row[fl.COL_SHEET_ROW]: row for row in csv.DictReader(handle) if row.get(fl.COL_SHEET_ROW)}


def is_done(row: dict) -> bool:
    return bool(row.get("source_used")) and row.get("source_used") != SOURCE_ERROR and not row.get("model_error")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", choices=[INPUT_RETRIEVED, INPUT_SUMMARY_MODE], default=INPUT_RETRIEVED,
                        help="retrieved = text from the policy link (default); summary = expert CDR_link only")
    parser.add_argument("--prompt", choices=PROMPT_VERSIONS, default=PROMPT_V1)
    parser.add_argument("--schema", action="store_true",
                        help="Force allowed values for closed fields (Ollama structured output, Ollama >= 0.5)")
    parser.add_argument("--split", choices=["test", "train", "all"], default="test")
    parser.add_argument("--rows", type=Path,
                        help="CSV with a sheet_row column: code only these policies (instead of --split)")
    parser.add_argument("--context", choices=[CONTEXT_KEYWORD, CONTEXT_RAG], default=CONTEXT_KEYWORD,
                        help="Long documents: keyword excerpt (default) or rag = own summary section + chunks "
                             "retrieved per coding question")
    parser.add_argument("--retriever", choices=["keywords", "embed", "bm25"], default="keywords",
                        help="RAG retrieval: targeted keywords per variable (default, no model needed), Ollama "
                             "embeddings, or bm25 over the question text")
    parser.add_argument("--embed-model", default=rag.DEFAULT_EMBED_MODEL, help="Ollama embedding model for --retriever embed")
    parser.add_argument("--embed-cache-dir", type=Path, default=EMBED_CACHE_DIR)
    parser.add_argument("--split-file", type=Path, default=DEFAULT_SPLIT_FILE)
    parser.add_argument("--no-text", choices=["title", "skip"], default="title",
                        help="Policies without retrievable text: code from title/context (default) or skip")
    parser.add_argument("--overrides", type=Path, default=DEFAULT_OVERRIDES,
                        help="CSV with manual input_type corrections (sheet_row,input_type,note)")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--host", default="http://127.0.0.1:11434")
    parser.add_argument("--max-doc-tokens", type=int, default=6000,
                        help="Token budget for the source text; longer documents are excerpted (default 6000)")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--limit", type=int, default=0, help="Code at most this many pending policies (0 = all)")
    parser.add_argument("--force", action="store_true", help="Recode rows already in the output file")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--cache-dir", type=Path, default=CACHE_DIR)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None, fl=None) -> Path:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    output = args.output or default_output(args)
    fl = fl or load_script(FIRST_LOOP, "first_loop")

    prose, definitions = fl.load_codebook(fl.DEFAULT_CODEBOOK)
    allowed = fl.load_allowed_values(fl.DEFAULT_SHEET)
    policies = fl.load_policies(fl.DEFAULT_SHEET)
    if args.rows:
        wanted = read_rows_file(args.rows)
        policies = [p for p in policies if p[fl.COL_SHEET_ROW] in wanted]
        scope = f"rows from {args.rows.name}"
    elif args.split != "all":
        split = read_split(args.split_file)
        policies = [p for p in policies if split.get(p[fl.COL_SHEET_ROW]) == args.split]
        scope = f"{args.split} split"
    else:
        scope = "all policies"

    instructions = instructions_for(args.prompt, fl.build_instructions(prose, definitions, allowed))
    fl.USER_PROMPT_HEADER = user_prompt_header(args.prompt, fl.USER_PROMPT_HEADER)
    schema = json_schema(fl, allowed) if args.schema else None
    num_ctx = min(fl.OLLAMA_CONTEXT_CAP, max(
        fl.OLLAMA_CONTEXT_FLOOR,
        int((fl.estimate_tokens(instructions) + args.max_doc_tokens) * fl.OLLAMA_CONTEXT_SAFETY_FACTOR)
        + fl.OLLAMA_CONTEXT_RESERVE,
    ))
    overrides = retrieval.read_overrides(args.overrides)

    print(f"Policies ({scope}): {len(policies)} | input: {args.input} | prompt: {args.prompt}"
          f"{' | context: rag/' + args.retriever if args.context == CONTEXT_RAG else ''}"
          f"{' + schema' if args.schema else ''} | model: {args.model}")
    print(f"Output: {output}")
    fl.ensure_ollama(args.host.rstrip("/"), args.model)
    retriever = make_retriever(fl, args)

    results = {} if args.force else read_rows(fl, output)
    pending = [p for p in policies if args.force or not is_done(results.get(p[fl.COL_SHEET_ROW], {}))]
    if args.limit:
        pending = pending[: args.limit]
    print(f"To code this run: {len(pending)}")

    session = fl.requests.Session()
    session.headers.update({"User-Agent": fl.USER_AGENT, "Accept": fl.HTTP_ACCEPT})
    for index, policy in enumerate(pending, start=1):
        row_id = policy[fl.COL_SHEET_ROW]
        print(f"[{index}/{len(pending)}] row {row_id} {policy.get(fl.COL_JURISDICTION, '')} | "
              f"{policy.get(fl.COL_DOCUMENT_TITLE, '')}")
        try:
            source = prepare_source(fl, policy, args, session, overrides, retriever)
            row = code_one(fl, policy, source, instructions, allowed, args, num_ctx, schema)
        except Exception as exc:
            row = fl.blank_result(policy, args.model)
            row[fl.COL_SOURCE_USED] = SOURCE_ERROR
            row[fl.COL_MODEL_ERROR] = f"{type(exc).__name__}: {exc}"
        results[row_id] = row
        write_rows(fl, output, [results[p[fl.COL_SHEET_ROW]] for p in policies if p[fl.COL_SHEET_ROW] in results])
        print(f"    input={row.get(COL_INPUT_TYPE, '-')} excerpt={row.get(COL_EXCERPTED, '-')} "
              f"tokens_sent={row.get(COL_TOKENS_SENT, '-')} error={row.get(fl.COL_MODEL_ERROR) or '-'}")

    done = [results[p[fl.COL_SHEET_ROW]] for p in policies if p[fl.COL_SHEET_ROW] in results]
    counts: dict[str, int] = {}
    for row in done:
        counts[row.get(COL_INPUT_TYPE) or "?"] = counts.get(row.get(COL_INPUT_TYPE) or "?", 0) + 1
    print("Input types: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    print(f"Wrote {output}")
    return output


if __name__ == "__main__":
    main()
