# Final benchmark

- Policies: **74**, the same for every run (policies in `document_policies_test.csv`, test split)
- Runs: `v1`, `v2 + rules`, `v2 + RAG1 + rules`, `v2 + RAG2 + rules`; comparisons are against `v1`
- Run: 2026-11-23; confidence intervals: 95% bootstrap over policies (2000 draws)

## Headline: mean exact agreement over the six core fields

| Run | Core mean | 95% CI | Change vs. v1 | 95% CI of change | Fixed | Broken |
|---|---|---|---|---|---|---|
| v1 | **43%** | 39%–48% | – | – | – | – |
| v2 + rules | **56%** | 51%–60% | +12 pp * | +6.1 pp to +18.7 pp | 99 | 44 |
| v2 + RAG1 + rules | **54%** | 49%–59% | +11 pp * | +4.1 pp to +17.3 pp | 100 | 52 |
| v2 + RAG2 + rules | **57%** | 52%–61% | +13 pp * | +7.0 pp to +19.1 pp | 99 | 40 |

\* the 95% CI of the change does not include 0. Fixed/broken: core field results that went wrong → right / right → wrong compared with the reference run.

## Per field: exact agreement

| Field | v1 | v2 + rules | v2 + RAG1 + rules | v2 + RAG2 + rules |
|---|---|---|---|---|
| **Policy_scope** | 78% | 85% | 84% | 85% |
| **Value_chain_focus** | 46% | 73% | 70% | 72% |
| **Instrument_broad** | 59% | 69% | 69% | 73% |
| Target_type | 28% | 47% | 45% | 49% |
| Target_binding | 20% | 16% | 19% | 15% |
| compliance_market_type | 89% | 91% | 91% | 91% |
| **Broad_method** | 31% | 36% | 32% | 36% |
| **Specific_method** | 32% | 30% | 28% | 34% |
| **Instrument_type** | 12% | 41% | 41% | 39% |
| Years_amended | 77% | 77% | 78% | 77% |

Core fields in bold. Multi-label fields: the whole label set must match.

## Per field: macro-F1 (single) and Jaccard / micro-F1 (multi-label)

| Field | Metric | v1 | v2 + rules | v2 + RAG1 + rules | v2 + RAG2 + rules |
|---|---|---|---|---|---|
| Policy_scope | macro_f1 | 0.78 | 0.85 | 0.84 | 0.85 |
| Value_chain_focus | macro_f1 | 0.47 | 0.61 | 0.59 | 0.60 |
| Instrument_broad | macro_f1 | 0.54 | 0.58 | 0.58 | 0.61 |
| Target_type | macro_f1 | 0.19 | 0.35 | 0.34 | 0.43 |
| Target_binding | macro_f1 | 0.17 | 0.15 | 0.19 | 0.15 |
| compliance_market_type | macro_f1 | 0.24 | 0.24 | 0.24 | 0.24 |
| Broad_method | jaccard | 0.40 | 0.48 | 0.42 | 0.46 |
| Broad_method | micro_f1 | 0.42 | 0.50 | 0.45 | 0.48 |
| Broad_method | macro_f1 | 0.37 | 0.42 | 0.38 | 0.38 |
| Specific_method | jaccard | 0.43 | 0.45 | 0.44 | 0.47 |
| Specific_method | micro_f1 | 0.30 | 0.37 | 0.42 | 0.39 |
| Specific_method | macro_f1 | 0.19 | 0.23 | 0.24 | 0.24 |
| Instrument_type | jaccard | 0.26 | 0.49 | 0.47 | 0.48 |
| Instrument_type | micro_f1 | 0.26 | 0.52 | 0.48 | 0.51 |
| Instrument_type | macro_f1 | 0.24 | 0.42 | 0.37 | 0.39 |
| Years_amended | jaccard | 0.80 | 0.80 | 0.81 | 0.81 |
| Years_amended | micro_f1 | 0.27 | 0.34 | 0.36 | 0.44 |
| Years_amended | macro_f1 | 0.20 | 0.25 | 0.25 | 0.58 |

## Fixed / broken per field (vs. v1)

| Field | v2 + rules fixed / broken | v2 + RAG1 + rules fixed / broken | v2 + RAG2 + rules fixed / broken |
|---|---|---|---|
| Policy_scope | 14 / 9 | 13 / 9 | 13 / 8 |
| Value_chain_focus | 35 / 15 | 35 / 17 | 34 / 15 |
| Instrument_broad | 14 / 7 | 15 / 8 | 14 / 4 |
| Target_type | 22 / 8 | 21 / 9 | 24 / 9 |
| Target_binding | 4 / 7 | 8 / 9 | 5 / 9 |
| compliance_market_type | 1 / 0 | 1 / 0 | 1 / 0 |
| Broad_method | 8 / 4 | 7 / 6 | 9 / 5 |
| Specific_method | 3 / 5 | 5 / 8 | 5 / 4 |
| Instrument_type | 25 / 4 | 25 / 4 | 24 / 4 |
| Years_amended | 1 / 1 | 2 / 1 | 1 / 1 |

## Systematic error patterns

| Pattern | v1 | v2 + rules | v2 + RAG1 + rules | v2 + RAG2 + rules |
|---|---|---|---|---|
| Framework coded as Instrument | 14 | 0 | 0 | 1 |
| Cross-cutting coded as Demand | 23 | 0 | 0 | 0 |
| Other coded as Regulatory instrument | 9 | 2 | 1 | 2 |
| Instrument types not in expert coding (total) | 332 | 46 | 51 | 59 |
| Instrument types per policy (experts: 1.3) | 5.3 | 1.3 | 1.3 | 1.5 |

## Core mean by input type

| Input | v1 | v2 + rules | v2 + RAG1 + rules | v2 + RAG2 + rules |
|---|---|---|---|---|
| title only | 33% (n=1) | – | – | – |
| policy text | 43% (n=56) | 58% (n=56) | 56% (n=56) | 59% (n=56) |
| webpage description | 46% (n=17) | 48% (n=18) | 49% (n=18) | 48% (n=18) |

## Core mean by context method (how the document was given to the model)

| Run | RAG | RAG + introduction | RAG + own summary | full text | keyword excerpt |
|---|---|---|---|---|---|
| v1 | – | – | – | 49% (n=36) | 38% (n=38) |
| v2 + rules | – | – | – | 53% (n=36) | 58% (n=38) |
| v2 + RAG1 + rules | 54% (n=22) | 63% (n=9) | 50% (n=7) | 53% (n=36) | – |
| v2 + RAG2 + rules | 61% (n=22) | 65% (n=9) | 52% (n=7) | 53% (n=36) | – |

## Output quality

| | v1 | v2 + rules | v2 + RAG1 + rules | v2 + RAG2 + rules |
|---|---|---|---|---|
| Rows with labels outside the codebook | 15 | 17 | 16 | 16 |
| Rows with any validation note | 21 | 22 | 22 | 26 |
| Model errors (no answer) | 0 | 0 | 1 | 0 |

## CDR_link free text (similarity to the expert sentence)

| Run | n | ROUGE-1 F1 | ROUGE-L F1 | BLEU (corpus) |
|---|---|---|---|---|
| v1 | 74 | 0.268 | 0.206 | 3.4 |
| v2 + rules | 74 | 0.272 | 0.209 | 3.7 |
| v2 + RAG1 + rules | 73 | 0.263 | 0.202 | 3.5 |
| v2 + RAG2 + rules | 74 | 0.265 | 0.203 | 3.9 |

Word-overlap metrics are only supplementary: the same content can be phrased differently.

## How to read this

- All runs are scored on the same policies against the same expert coding (gold standard).
- The confidence intervals show how much the result could move with a different sample of policies of the same size. A change whose interval includes 0 is not distinguishable from noise.
- Fixed/broken counts show whether a gain is a real shift or errors moving between policies.
- Prompt v2 rules were derived from the train split only; these policies are from the test split.
