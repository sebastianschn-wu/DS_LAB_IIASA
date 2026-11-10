# One-shot / few-shot prompting

Runs the **unchanged** first loop (`src/scripts/first-loop/first-loop.script.py`) with worked expert examples in
the prompt. The logic stays the same; the script only

1. appends N examples (title, country, year and the full expert coding) to the codebook instructions, and
2. codes only the **test** policies of the train/test split.

The zero-shot baseline is the existing first-loop run (`results/first_loop_coding.csv`), evaluated on the same
test policies.

## Run

```bash
python src/scripts/few-shot/few-shot.script.py --shots 1 --model qwen2.5:7b
python src/scripts/few-shot/few-shot.script.py --shots 3 --model qwen2.5:7b
python src/scripts/benchmark/compare.script.py \
    --run "zero-shot=results/first_loop_coding.csv" \
    --run "one-shot=results/shots1_test_coding.csv" \
    --run "three-shot=results/shots3_test_coding.csv"
```

- Output: `results/shots<N>_test_coding.csv` (same columns as the first loop).
- All first-loop options work (`--model`, `--max-doc-tokens`, `--limit`, `--force`, ...). Pass the exact
  installed model tag (e.g. `qwen2.5:7b`).
- Runs can be stopped and continued like the first loop.

## Split (`src/resources/train_test_split.csv`)

- 228 train / 99 test policies, 70/30 per country, seed 42.
- Rows that share a source document (e.g. the EU NDC listed under the EU, France, Germany and Italy) are in the
  same part, so no document appears in both.
- The file is versioned so every team member evaluates on the same policies.

## Examples (`examples.py`)

All from the train part, ordered by the zero-shot errors they target. `--shots N` uses the first N.

| # | Row | Policy | Targets the error |
|---|---|---|---|
| 1 | 19 | Australia – Climate Change Act 2022 | Framework coded as Instrument; emissions target vs. CDR target |
| 2 | 43 | EU – CCS Directive | Regulatory instrument for storage; no target |
| 3 | 73 | Argentina – National Forest Extension Programme | Economic instrument, supply side |
| 4 | 104 | Canada – CDR purchase commitment | Demand side |
| 5 | 118 | France – France 2030 forest renewal | Conventional (land-based) CDR |

Expert comments are left out of the examples.

## Tests

```bash
python -m pytest src/scripts/few-shot/tests -q
```
