# Comparison of coding runs

- Evaluated on: the test split
- Run: 2026-11-26

| Run | Policies | From document |
|---|---|---|
| zero-shot | 99 | 32 |
| one-shot | 99 | 34 |
| three-shot | 99 | 35 |

## Exact agreement, coded from the full document (main result)

| Field | zero-shot | one-shot | three-shot |
|---|---|---|---|
| Policy_scope | 75% | 88% | 83% |
| Value_chain_focus | 59% | 56% | 57% |
| Instrument_broad | 62% | 56% | 54% |
| Target_type | 31% | 53% | 69% |
| Target_binding | 31% | 41% | 63% |
| compliance_market_type | 91% | 85% | 89% |
| Broad_method | 34% | 21% | 51% |
| Specific_method | 34% | 35% | 37% |
| Instrument_type | 19% | 38% | 26% |
| Years_amended | 78% | 76% | 69% |
| **Mean of core fields** | **47%** | **49%** | **51%** |

## Exact agreement, all rows, including the summary fallback

| Field | zero-shot | one-shot | three-shot |
|---|---|---|---|
| Policy_scope | 71% | 84% | 81% |
| Value_chain_focus | 45% | 57% | 61% |
| Instrument_broad | 59% | 61% | 59% |
| Target_type | 41% | 68% | 78% |
| Target_binding | 27% | 44% | 61% |
| compliance_market_type | 91% | 90% | 91% |
| Broad_method | 36% | 31% | 60% |
| Specific_method | 47% | 48% | 47% |
| Instrument_type | 23% | 49% | 48% |
| Years_amended | 78% | 78% | 74% |
| **Mean of core fields** | **47%** | **55%** | **59%** |

## CDR_link similarity (document rows, ROUGE-L F1)

| zero-shot | one-shot | three-shot |
|---|---|---|
| 0.202 | 0.218 | 0.202 |

## How to read this

- Compare runs on the document rows; summary rows received the expert CDR_link sentence as input.
- With about 100 test policies (and fewer document rows), differences of a few percentage points are within noise.
- Few-shot examples come from the train split only, so no example policy is in the test set.
