# Unbiased baseline

Zero-shot coding **without any expert-written input**, evaluated separately per input type. Reuses the
unchanged first loop (codebook, prompt, Ollama call, output validation); only the input handling is new.

## Why a new baseline

The first loop sends the expert `CDR_link` summary when a document is missing or longer than 6,000 tokens.
`CDR_link` is also one of the fields the model predicts, so 227 of 327 rows partly contained the answer
(leakage). This baseline removes that:

| | First loop | Unbiased baseline |
|---|---|---|
| Document too long | expert summary instead | **excerpt**: beginning + most relevant passages, within the token budget |
| Policy-database page (FAOLEX, climate-laws.org, …) | page text | **linked PDF** if there is one, else page text |
| Nothing retrievable | expert summary | **title and context only** (`--no-text title`) or skipped (`--no-text skip`) |
| Policies | all 327 | one split, default the **99 test policies** |
| Input label per row | document / summary | `input_type` (below) |

## Input types (Elina's request)

| `input_type` | Meaning | How it is decided |
|---|---|---|
| `policy_text` | the policy itself | PDF, or a long (≥ 1,500 tokens) page on a non-database site |
| `webpage_description` | a page *about* the policy | policy-database site, or a short page (news/landing page) |
| `no_text` | nothing usable retrieved | fetch error, empty page, file > 25 MB |
| `expert_summary` | expert `CDR_link` | only in the `--input summary` control run |

The rule is a heuristic. The output has `input_type_reason` and `final_url` for checking. Wrong cases can
be corrected in `input_type_overrides.csv` (`sheet_row,input_type,note`) and are applied on the next run
(with `--force`).

## RAG + chunking for long documents (`--context rag`)

By default a document over the token budget is shortened with a keyword excerpt. With `--context rag` the
model instead gets, within the same 6,000 tokens (`rag.py`, version 3):

1. **The frame (about 30% of the budget)**: the document's own summary (Executive Summary, Resumen ejecutivo,
   Zusammenfassung, 概要, …) or, if there is none, its introduction, plus the beginning (title, purpose, scope).
   This lets the model still see what kind of document it is.
2. **Targeted passages per coding variable**: the document is cut into chunks of about 350 tokens and searched
   with keyword lists per variable in 13 languages (`constants/keywords.json`, see below):

   | Keyword list | Variable |
   |---|---|
   | scope | Policy_scope |
   | methods | Broad_method, Specific_method |
   | storage | CO₂ storage and transport |
   | instrument | Instrument_broad, Instrument_type |
   | demand | Value_chain_focus, compliance market |
   | targets | Target_type, Target_binding, Target_year/amount/unit |
   | funding | Funding_sum, Funding_unit |

   - Only clearly relevant chunks are sent: the score must stand out within the document (z ≥ 1).
   - No single variable gets more than 30% of the budget.
   - Generic words such as "credit", "procurement" or "budget" only count when the passage is also about
     carbon or climate.
3. **Noise filter**: tables of contents, website navigation and copyright text, and garbled PDF text are never
   sent.

Every variable is searched in every document. A variable whose keywords do not occur gets no passages anyway
(a chunk needs a positive score), so a forest plan still gets no storage passages.

Version 2 came from looking at what version 1 sent (`results/baseline/rag_inspection.md`): tables of contents,
website menus, garbled PDFs, off-topic passages, a fixed quota per question, and too little of the
title/summary. `--retriever embed` (Ollama `bge-m3`) and `--retriever bm25` remain as alternatives.

Version 3 (review of PR #5): version 2 skipped the methods, storage, demand and funding questions when their
keywords occurred fewer than 5 times in a document. All of them serve variables that are coded for every policy
(e.g. Funding_sum), and a funding amount mentioned once was then never retrieved, so version 3 asks every
question. The keyword lists moved to a multilingual dictionary. The `rag2` results in `results/baseline` were
produced with version 2 (commit `a019a9f`); version 3 writes `..._rag3_...` files and has to be run again.

### Constants, parameters and keywords (`constants/`)

| File | Content |
|---|---|
| `constants/rag_settings.py` | all RAG parameters (frame share, chunk size, `MIN_Z`, `QUERY_CAP`, BM25 `k1`/`b`, ...) with the reasoning and references behind each value |
| `constants/retrieval_settings.py` | source retrieval and the keyword excerpt (`EXCERPT_KEYWORDS`, frozen so v1/v2 stay reproducible) |
| `constants/keywords.json` | multilingual keyword dictionary: one entry per concept, one term list per language |
| `constants/keywords.py` | which concepts belong to which coding variable, plus language-independent regex patterns |

Languages: en, es, pt, fr, de, it, id, ru, ja, zh, ko, tr, ar (the 20 jurisdictions of the policy sheet). To add a
synonym, add it to the concept in `keywords.json`; to add a language, add its code to `LANGUAGES` and a term list
to every concept (`tests/test_keywords.py` checks the coverage). Terms are matched as lower-case substrings, so
stems like `subsid` cover several word forms. A translation library is not used at run time (needs internet,
results could change between runs, stems and abbreviations translate badly); it can be used once to suggest
terms for a new language, which are then checked by hand.

```bash
python src/scripts/baseline/baseline.script.py --prompt v2 --context rag \
    --rows src/resources/document_policies_test.csv --no-text skip
# -> results/baseline/retrieved_v2_rag3_document_policies_test.csv
```

`--rows` codes only the policies in a CSV with a `sheet_row` column.
`src/resources/document_policies_test.csv` holds the 74 test policies for which a document or webpage could be
retrieved. The `excerpted` column shows what happened per policy: `no` (full text), `yes` (keyword excerpt),
`rag`, `rag+summary` or `rag+intro`.

## Run (on the Mac with Ollama)

```bash
cd ~/Downloads/DS_LAB_IIASA && source .venv/bin/activate
python src/scripts/baseline/baseline.script.py --limit 3          # quick check (3 policies)
python src/scripts/baseline/baseline.script.py                    # 1. unbiased baseline, prompt v1
python src/scripts/baseline/baseline.script.py --prompt v2        # 2. revised prompt (same policies, same text)
python src/scripts/baseline/baseline.script.py --input summary    # optional: expert summary only (fast)
```

Outputs go to `results/baseline/<input>_<prompt>[_schema]_<split>.csv`, e.g. `retrieved_v1_test.csv`.

- Runs can be stopped and continued; finished rows are skipped unless `--force`.
- Downloaded text is cached in `results/source_cache/full_text/` (git-ignored), so the v2 run reuses exactly
  the text of the v1 run and does not download again.
- Model: `qwen2.5:7b` for all runs, the same model as the first loop (its default `qwen2.5` is Ollama's alias
  for `qwen2.5:7b`, same model ID `845dbda0ea48`).
- Options: `--split test|train|all`, `--max-doc-tokens 6000`, `--model qwen2.5:7b`, `--schema` (Ollama
  returns only allowed values for closed fields; needs Ollama ≥ 0.5; treat it as its own run), `--limit N`.

## Evaluate per input type

```bash
python src/scripts/baseline/evaluate.script.py \
    --run "unbiased v1=results/baseline/retrieved_v1_test.csv" \
    --run "expert summary=results/baseline/summary_v1_test.csv" \
    --run "first loop=results/first_loop_coding.csv"
```

Writes `results/baseline/evaluation/evaluation.md` and `.csv`: accuracy per field and input type, the mean of
the six core fields and the mean macro-F1 (metric code from `src/scripts/benchmark`). The
`policy text` column is the main result.

## Tests

```bash
python -m pytest src/scripts/baseline/tests -q
```

The tests use a fake model and fake downloads. One test checks that the expert summary never appears in the
prompt of a retrieved-text run.
