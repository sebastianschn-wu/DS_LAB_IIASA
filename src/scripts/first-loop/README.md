# First loop: zero-shot coding with a local LLM

Codes every policy of the gold standard with a local open-weight model (Ollama, default Qwen 2.5) according to the
codebook. The output is compared with the expert coding in the benchmarking step.

## Setup

```bash
pip install -r requirements.txt          # from the repository root
ollama pull qwen2.5:7b                   # once; ~4.7 GB
```

## Run

```bash
python src/scripts/first-loop/first-loop.script.py --limit 5     # quick test with 5 policies
python src/scripts/first-loop/first-loop.script.py               # all policies
```

| Option | Default | Meaning |
|---|---|---|
| `--sheet` | cleaned sheet (`data/processed/CDR_policy_sheet_clean.xlsx`) if it exists, else `src/resources/CDR_policy_sheet.xlsx` | Policy sheet |
| `--model` | `qwen2.5` | Ollama model. If only another tag is installed (e.g. `qwen2.5:7b`), that tag is used |
| `--max-doc-tokens` | 6000 | Documents above this estimate are not sent (summary fallback instead) |
| `--limit` | 0 (all) | Code at most N pending policies |
| `--force` | off | Recode rows that are already in the output |
| `--no-schema` | off | Free JSON instead of the codebook JSON schema (only needed for Ollama < 0.5) |
| `--no-summary-fallback` | off | Leave rows out instead of sending the expert `CDR_link` sentence |

The run can be stopped at any time (Ctrl+C). The next run continues with the missing rows.
At the end the script prints how many rows used the full document, the summary, or were omitted.

## Output

`results/first_loop_coding.csv`, one row per policy:

- identity: `sheet_row`, `Jurisdiction`, `Iso`, `Document_full_title`, `Year_enacted`, `Link`
- run info: `model`, `source_used` (`document` / `summary` / `omitted` / `error`), `fallback_reason`, `omit_reason`,
  `document_tokens`, `fetch_error`, `model_error`, `coded_at`, `validation_notes`
- the coded codebook fields (`Policy_scope`, `Broad_method`, ..., `Comments`)

Downloaded document texts are cached in `results/source_cache/`.

## How it works

```
sheet + codebook ──► instructions (system prompt) + JSON schema
        │
policy link ──► download ──► PDF/HTML text ──► token check
        │                                        │ too long / empty / failed
        │                                        ▼
        │                               CDR_link sentence (summary fallback)
        ▼
  Ollama (local) ──► JSON ──► codebook spelling + validation notes ──► CSV
```

| Module | Content |
|---|---|
| `first-loop.script.py` | Command line and main loop |
| `constants.py` | Paths, column names, prompt text, limits |
| `text_utils.py` | Token estimate, text helpers |
| `codebook.py` | Read codebook (.docx) and sheet, build instructions and JSON schema |
| `documents.py` | Download, PDF/HTML text extraction, cache |
| `ollama_client.py` | Start/check Ollama, pick the installed model tag, chat call |
| `coding.py` | Choose the source text, build the prompt, clean the model answer |
| `results.py` | Results CSV, run summary |

## Tests

```bash
pip install pytest reportlab
python -m pytest src/scripts/first-loop/tests -q
```

The tests need neither Ollama nor internet (model and downloads are simulated).

## Important for the evaluation

Rows with `source_used = summary` were coded from the expert-written `CDR_link` sentence. Do not score `CDR_link`
(ROUGE/BLEU/BERTScore) on these rows, and report the other fields for document and summary rows separately.
See `VALIDATION.md`.
