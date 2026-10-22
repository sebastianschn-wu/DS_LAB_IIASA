# Data cleaning (gold standard)

Cleans the expert-coded CDR policy sheet (`src/resources/CDR_policy_sheet.xlsx`) so it can be used as the
benchmark for the first loop and the evaluation. **No coding decision of the experts is changed**: the script only
harmonises formats, adds helper columns and flags rows that need a human decision.

## Run

```bash
pip install pandas openpyxl
python src/scripts/data-cleaning/data-cleaning.script.py
```

Options: `--sheet <path>` (input, default: the resource sheet), `--output-dir <path>` (default: `data/processed/`).

## Outputs (`data/processed/`, git-ignored)

| File | Content |
|---|---|
| `CDR_policy_sheet_clean.xlsx` | Same sheets as the input (ReadMe, CodingScheme, Data), cleaned. Works with the first loop: `python src/scripts/first-loop/first-loop.script.py --sheet data/processed/CDR_policy_sheet_clean.xlsx` |
| `gold_standard_clean.csv` | Cleaned Data sheet as CSV (for evaluation scripts) |
| `country_summary.csv` | Policies aggregated by country: counts by scope, method, value chain, instrument, number of double-coded rows, year range |
| `cleaning_report.md` | Every change and a table of all rows that need review |

The outputs are not committed because the benchmark is project material that must not be redistributed
(project plan, data handling). Everyone can recreate them with the command above.

## What the script does

| Step | Why |
|---|---|
| Drop empty `Column1`/`Column2`, trim whitespace | Clean input |
| Rename `ETS_*` to `compliance_*` | Codebook v1.0 names are authoritative (assumption A1); matches `MODEL_FIELDS` in the first loop |
| Normalise multi-value fields (`a; b`, no duplicates) | Consistent multi-label evaluation |
| Check closed fields against the CodingScheme sheet | Finds labels not defined in the codebook (e.g. `Utilization`) |
| Unify dashes and separators in target fields, add `n_targets` | `26–28` vs `26-28`, several targets per policy |
| Funding to ISO currency + absolute amount (`50 AUD million` -> `50000000 AUD`), original in `Funding_raw` | Comparable funding values |
| Remove `utm_*` tracking parameters from links | Clean source URLs |
| Parse `Validation` into `coders`, `n_coders`, `double_coded` | Only part of the rows is validated by two experts; useful for the evaluation |
| Extract comment tags (`NEW ROW`, `CORRECTED`, `VCF`) into `comment_tags` | Shows rows the experts added or corrected later |
| Add `shared_document_group` | Several rows use the same source document (e.g. the EU NDC under EU, France, Germany, Italy). Rows of one group must stay in the same train/test split |
| Add `policy_id` (`ISO-row`, e.g. `DEU-296`) and `sheet_row` | Stable key for joining model output and gold standard |
| Country summary | Aggregation by country for the benchmark description |

## Open points for the team / coach

- **Possible duplicates** (same country, same link): see the review table in `cleaning_report.md`
  (e.g. Canada's two "Enhanced First NDC" rows).
- **`Utilization`** in `Specific_method` (Energy Act of 2020) is not a codebook category.
- **`Years_amended = Multiple`** (Turkey, Forest Law No. 6831) was removed; the actual years are missing.
- Coder initials `LT` and `LV` were mapped to Leona Tenkhoff and Lisa Voigt (codebook authors); please confirm.
- **`CDR_link` as summary fallback:** the first loop sends `CDR_link` to the model when a document is too long.
  This text is written by the experts and is also a field the model must produce, so these rows must be reported
  separately (or excluded) when scoring `CDR_link` with ROUGE/BLEU/BERTScore.
