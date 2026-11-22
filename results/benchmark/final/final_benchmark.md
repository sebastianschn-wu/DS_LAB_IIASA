# Final benchmark

- Policies: **74**, the same for every run (policies in `document_policies_test.csv`, test split)
- Runs: `v1`, `v2`, `v2 + RAG`; comparisons are against `v1`
- Run: 2026-11-22; confidence intervals: 95% bootstrap over policies (2000 draws)

## Headline: mean exact agreement over the six core fields

| Run | Core mean | 95% CI | Change vs. v1 | 95% CI of change | Fixed | Broken |
|---|---|---|---|---|---|---|
| v1 | **43%** | 39%–48% | – | – | – | – |
| v2 | **49%** | 45%–53% | +6 pp * | +0.2 pp to +10.6 pp | 75 | 50 |
| v2 + RAG | **47%** | 42%–51% | +4 pp | -2.0 pp to +9.0 pp | 78 | 62 |

\* the 95% CI of the change does not include 0. Fixed/broken: core field results that went wrong → right / right → wrong compared with the reference run.

## Per field: exact agreement

| Field | v1 | v2 | v2 + RAG |
|---|---|---|---|
| **Policy_scope** | 78% | 85% | 84% |
| **Value_chain_focus** | 46% | 72% | 70% |
| **Instrument_broad** | 59% | 58% | 53% |
| Target_type | 28% | 32% | 35% |
| Target_binding | 20% | 16% | 19% |
| compliance_market_type | 89% | 91% | 91% |
| **Broad_method** | 31% | 36% | 32% |
| **Specific_method** | 32% | 30% | 28% |
| **Instrument_type** | 12% | 12% | 14% |
| Years_amended | 77% | 77% | 78% |

Core fields in bold. Multi-label fields: the whole label set must match.

## Per field: macro-F1 (single) and Jaccard / micro-F1 (multi-label)

| Field | Metric | v1 | v2 | v2 + RAG |
|---|---|---|---|---|
| Policy_scope | macro_f1 | 0.78 | 0.85 | 0.84 |
| Value_chain_focus | macro_f1 | 0.47 | 0.59 | 0.59 |
| Instrument_broad | macro_f1 | 0.54 | 0.51 | 0.48 |
| Target_type | macro_f1 | 0.19 | 0.24 | 0.28 |
| Target_binding | macro_f1 | 0.17 | 0.15 | 0.19 |
| compliance_market_type | macro_f1 | 0.24 | 0.24 | 0.24 |
| Broad_method | jaccard | 0.40 | 0.48 | 0.42 |
| Broad_method | micro_f1 | 0.42 | 0.50 | 0.45 |
| Broad_method | macro_f1 | 0.37 | 0.42 | 0.38 |
| Specific_method | jaccard | 0.43 | 0.45 | 0.44 |
| Specific_method | micro_f1 | 0.30 | 0.37 | 0.42 |
| Specific_method | macro_f1 | 0.19 | 0.23 | 0.24 |
| Instrument_type | jaccard | 0.26 | 0.32 | 0.34 |
| Instrument_type | micro_f1 | 0.26 | 0.32 | 0.36 |
| Instrument_type | macro_f1 | 0.24 | 0.27 | 0.29 |
| Years_amended | jaccard | 0.80 | 0.80 | 0.81 |
| Years_amended | micro_f1 | 0.27 | 0.34 | 0.36 |
| Years_amended | macro_f1 | 0.20 | 0.25 | 0.25 |

## Fixed / broken per field (vs. v1)

| Field | v2 fixed / broken | v2 + RAG fixed / broken |
|---|---|---|
| Policy_scope | 14 / 9 | 13 / 9 |
| Value_chain_focus | 34 / 15 | 35 / 17 |
| Instrument_broad | 13 / 14 | 14 / 19 |
| Target_type | 11 / 8 | 14 / 9 |
| Target_binding | 4 / 7 | 8 / 9 |
| compliance_market_type | 1 / 0 | 1 / 0 |
| Broad_method | 8 / 4 | 7 / 6 |
| Specific_method | 3 / 5 | 5 / 8 |
| Instrument_type | 3 / 3 | 4 / 3 |
| Years_amended | 1 / 1 | 2 / 1 |

## Systematic error patterns

| Pattern | v1 | v2 | v2 + RAG |
|---|---|---|---|
| Framework coded as Instrument | 14 | 0 | 0 |
| Cross-cutting coded as Demand | 23 | 1 | 0 |
| Other coded as Regulatory instrument | 9 | 2 | 1 |
| Instrument types not in expert coding (total) | 332 | 230 | 177 |
| Instrument types per policy (experts: 1.3) | 5.3 | 4.0 | 3.2 |

## Core mean by input type

| Input | v1 | v2 | v2 + RAG |
|---|---|---|---|
| title only | 33% (n=1) | – | – |
| policy text | 43% (n=56) | 49% (n=56) | 46% (n=56) |
| webpage description | 46% (n=17) | 47% (n=18) | 48% (n=18) |

## Core mean by context method (how the document was given to the model)

| Run | RAG | RAG + introduction | RAG + own summary | full text | keyword excerpt |
|---|---|---|---|---|---|
| v1 | – | – | – | 49% (n=36) | 38% (n=38) |
| v2 | – | – | – | 50% (n=36) | 47% (n=38) |
| v2 + RAG | 43% (n=22) | 43% (n=9) | 45% (n=7) | 50% (n=36) | – |

## Output quality

| | v1 | v2 | v2 + RAG |
|---|---|---|---|
| Rows with labels outside the codebook | 15 | 17 | 16 |
| Rows with any validation note | 21 | 22 | 22 |
| Model errors (no answer) | 0 | 0 | 1 |

## CDR_link free text (similarity to the expert sentence)

| Run | n | ROUGE-1 F1 | ROUGE-L F1 | BLEU (corpus) |
|---|---|---|---|---|
| v1 | 74 | 0.268 | 0.206 | 3.4 |
| v2 | 74 | 0.272 | 0.209 | 3.7 |
| v2 + RAG | 73 | 0.263 | 0.202 | 3.5 |

Word-overlap metrics are only supplementary: the same content can be phrased differently.

## How to read this

- All runs are scored on the same policies against the same expert coding (gold standard).
- The confidence intervals show how much the result could move with a different sample of policies of the same size. A change whose interval includes 0 is not distinguishable from noise.
- Fixed/broken counts show whether a gain is a real shift or errors moving between policies.
- Prompt v2 rules were derived from the train split only; these policies are from the test split.
