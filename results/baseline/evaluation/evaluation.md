# Benchmark by input type

- Policies: the test split
- Run: 2026-11-20
- Exact agreement with the expert coding (multi-label fields: the whole label set must match).

## unbiased v1

| Field | all (n=99) | policy text (n=56) | webpage description (n=17) | title only (nothing retrieved) (n=26) |
|---|---|---|---|---|
| Policy_scope | 78% | 79% | 76% | 77% |
| Value_chain_focus | 42% | 41% | 65% | 31% |
| Instrument_broad | 59% | 64% | 47% | 54% |
| Target_type | 31% | 23% | 41% | 42% |
| Target_binding | 24% | 18% | 24% | 38% |
| compliance_market_type | 89% | 93% | 76% | 88% |
| Broad_method | 36% | 27% | 41% | 54% |
| Specific_method | 32% | 30% | 41% | 31% |
| Instrument_type | 14% | 14% | 6% | 19% |
| Years_amended | 77% | 77% | 76% | 77% |
| **Mean of 6 core fields** | **44%** | **43%** | **46%** | **44%** |
| Mean macro-F1, core fields | 0.43 | 0.43 | 0.44 | 0.45 |

## first loop

| Field | all (n=99) | document (first loop) (n=32) | expert summary (first-loop fallback) (n=67) |
|---|---|---|---|
| Policy_scope | 71% | 75% | 69% |
| Value_chain_focus | 45% | 59% | 39% |
| Instrument_broad | 59% | 62% | 57% |
| Target_type | 41% | 31% | 46% |
| Target_binding | 27% | 31% | 25% |
| compliance_market_type | 91% | 91% | 91% |
| Broad_method | 36% | 34% | 37% |
| Specific_method | 47% | 34% | 54% |
| Instrument_type | 23% | 19% | 25% |
| Years_amended | 78% | 78% | 78% |
| **Mean of 6 core fields** | **47%** | **47%** | **47%** |
| Mean macro-F1, core fields | 0.44 | 0.45 | 0.44 |

## How to read this

- `policy text` is the main result: the model saw the policy itself and no expert-written text.
- `webpage description` rows saw only a page about the policy; `title only` rows saw no text at all.
- `expert summary` (control run) is not an independent test: the summary is expert interpretation.
- Groups with few policies (n < 20) are noisy; a difference of a few percentage points means little.
