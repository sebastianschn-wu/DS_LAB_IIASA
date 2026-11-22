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
model instead gets, within the same 6,000 tokens (`rag.py`):

1. **The document's own summary**: Executive Summary, Summary, Overview, Resumen ejecutivo, Zusammenfassung,
   概要 and so on. If there is none, its **introduction**.
2. **The beginning** of the document: title, purpose and scope.
3. **The passages most relevant to each coding question**: the document is cut into chunks of about 350 tokens,
   and for each question (scope, CDR methods, storage, instruments, demand, targets, funding) the most similar
   chunks are retrieved, taking turns between the questions.

Retrieval uses Ollama embeddings (`bge-m3`, multilingual) and caches them in
`results/source_cache/embeddings/`. `--retriever bm25` is a keyword alternative that needs no model. The
`excerpted` column shows what happened per policy: `no` (full text), `yes` (keyword excerpt), `rag`,
`rag+summary` or `rag+intro`.

On the 38 long test documents, a summary section is found in 7 and an introduction in 9.

```bash
ollama pull bge-m3                                   # once, about 1.2 GB
python src/scripts/baseline/baseline.script.py --prompt v2 --context rag \
    --rows src/resources/document_policies_test.csv --no-text skip
# -> results/baseline/retrieved_v2_rag_document_policies_test.csv
```

`--rows` codes only the policies in a CSV with a `sheet_row` column.
`src/resources/document_policies_test.csv` holds the 74 test policies for which a document or webpage could be
retrieved (56 policy texts, 18 webpage descriptions). `--no-text skip` skips a policy if its download fails
this time, so it is not coded from the title.

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
