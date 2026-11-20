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
