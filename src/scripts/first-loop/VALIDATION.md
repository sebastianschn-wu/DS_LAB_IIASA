# Validation of the first-loop script

Review of the agent-generated first-loop script (`d3d9c80`), what was changed, and what the team still has to decide.

## How it was checked

- Read every function and compared it with the codebook and the project plan.
- 26 automated tests (`tests/`): codebook and sheet loading, instruction and schema building, answer cleaning,
  source choice, document download/extraction with simulated web pages and PDFs, model-tag selection, and a full run
  with a simulated model including resume.
- Regression check: the new modules build **exactly the same** system prompt, policy list and user prompt as the
  original script.
- Not checked here: a real run with Ollama and real downloads. Please run `--limit 5` locally once.

## What works as intended

- The codebook .docx is read correctly: all 19 model fields get their definition, plus the four general rules.
- Allowed values come from the CodingScheme sheet; expert codings are never sent to the model.
- Results are saved after every row and the run can be resumed.
- Downloads are cached; failed downloads are retried in the next run.

## Bugs found and fixed

| # | Problem | Effect | Fix |
|---|---|---|---|
| 1 | Default model `qwen2.5` was accepted as "installed" when only `qwen2.5:7b` was present, but the script still called `qwen2.5` (= `qwen2.5:latest`). | Every model call fails with "model not found" on a machine that pulled `qwen2.5:7b`. | `resolve_model` uses the installed tag. |
| 2 | The model was only asked for "some JSON" (`format: "json"`). | Labels outside the codebook were possible and only flagged afterwards. | Codebook JSON schema is sent by default (closed fields as enums, multi-value fields as arrays). `--no-schema` restores the old behaviour. |
| 3 | Several values in a single-value field (e.g. `Supply; Demand`) were reported as "not in the codebook list"; the "expected a single value" check could never trigger. | Misleading validation notes. | Closed single-value fields are split and checked; the correct note is written. |
| 4 | Abbreviations were not matched (`DACCS`, `BECCS`). | Correct answers were flagged as unknown values. | Abbreviations in brackets are matched to the full codebook label. |
| 5 | PDF token count re-joined all pages after every page. | Quadratic runtime on long PDFs. | Tokens are added per page. |
| 6 | Navigation, header and footer of web pages were sent as document text. | Noise in the prompt. | `nav`, `header`, `footer`, `aside` are removed. |
| 7 | `PyPDF2` is no longer maintained. | Future install problems. | Replaced by `pypdf` (same API). |
| 8 | No `requirements.txt`. | Unclear setup. | Added at repository root. |

## Methodological issues (need a team decision)

1. **Leakage through the summary fallback.** When a document is too long, cannot be downloaded or is empty, the
   script sends the `CDR_link` sentence. This sentence is written by the experts and is also one of the fields the
   model must produce, and it often names the method or instrument. Rows coded this way are not a fair test.
   - Now: the row is marked `source_used = summary`; `--no-summary-fallback` leaves such rows out.
   - To decide: report document and summary rows separately (recommended), or exclude summary rows from the benchmark.
2. **Token threshold of 6000.** Most NDCs, long-term strategies and laws are far longer (the German KSpG alone is about
   30,000 tokens). With 6000, a large share of the 327 policies will probably fall back to the summary. The run summary
   at the end now shows the exact numbers. Options: raise `--max-doc-tokens` (the context cap is 32,768; needs more
   RAM), or add chunking/RAG (listed as "open" in the project plan).
3. **Landing pages.** The script follows a PDF link only if the HTML page has almost no text. Pages such as
   climate-laws.org document pages or the UNFCCC NDC registry contain enough text to be coded directly, so the model
   may code a database summary page instead of the law. Check `document_tokens` and a few cached texts after the
   first run.
4. **Shared documents.** Several rows use the same source document (EU NDCs under EU, France, Germany, Italy). The
   cleaned sheet marks them in `shared_document_group`; keep each group in the same train/test split.
5. **Fields marked "(not include)" in the codebook.** `compliance_upper_bound` and its unit are marked "not include"
   for publication but are still coded; harmless, but they need not be evaluated.
