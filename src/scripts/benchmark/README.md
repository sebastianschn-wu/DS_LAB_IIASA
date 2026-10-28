# Benchmark: LLM coding vs. expert gold standard

Compares the first-loop output (`results/first_loop_coding.csv`) with the cleaned gold standard and produces
report-ready tables and a chart.

## Run

```bash
pip install pandas openpyxl matplotlib sacrebleu
python src/scripts/data-cleaning/data-cleaning.script.py   # once: creates data/processed/gold_standard_clean.csv
python src/scripts/benchmark/benchmark.script.py
```

| Option | Default | Meaning |
|---|---|---|
| `--predictions` | `results/first_loop_coding.csv` | Model output to evaluate (e.g. another model or run) |
| `--gold` | `data/processed/gold_standard_clean.csv` | Gold standard |
| `--output-dir` | `results/benchmark/` | Where results are written |
| `--bertscore` | off | Also compute BERTScore for CDR_link (`pip install bert-score`, downloads ~1.4 GB model) |
| `--bertscore-model` | `roberta-large` | Smaller alternative: `distilbert-base-uncased` |

## Outputs (`results/benchmark/`)

| File | Content |
|---|---|
| `benchmark_summary.md` | Headline, tables per field, CDR_link similarity, frequent mix-ups, weakest labels, results by country |
| `accuracy_by_source.png` | Chart for the report: agreement per core field, document vs. summary input |
| `field_metrics.csv` | One row per field and subset (`all` / `document` / `summary`) |
| `label_metrics.csv` | Precision, recall, F1 per label |
| `confusions.csv` | Gold -> model mix-ups with counts |
| `text_metrics.csv` | ROUGE-1, ROUGE-L, BLEU (and BERTScore) for CDR_link |
| `row_level.csv` | Gold vs. model per policy for the core fields (for error analysis) |
| `country_accuracy.csv` | Core agreement per country |

## Metrics

| Field type | Fields | Metrics |
|---|---|---|
| Single value | Policy_scope, Value_chain_focus, Instrument_broad, Target_type, Target_binding, compliance_market_type | Accuracy, macro-F1, accuracy on rows where the experts set a value |
| Multiple values | Broad_method, Specific_method, Instrument_type, Years_amended | Exact match of the label set, mean Jaccard, micro/macro precision, recall, F1 |
| Free text | CDR_link | ROUGE-1 F1, ROUGE-L F1 (implemented in `metrics.py`), BLEU (sacrebleu), optional BERTScore |

An empty value counts as its own label `(none)`, so "no target" predicted for "no target" is correct.
Labels are compared case- and subscript-insensitively (`CO₂` = `CO2`).

**Every metric is reported separately for rows coded from the full document and rows coded from the expert
`CDR_link` summary.** The summary is written by the experts, so the summary rows are not a fair test; the document
rows are the main result.

## Tests

```bash
python -m pytest src/scripts/benchmark/tests -q
```
