# Significance of the differences between runs

- Split: test
- Policies coded by every run: 99

## Which policies were coded from the document

| Run | document rows | summary rows |
|---|---|---|
| zero-shot | 32 | 67 |
| one-shot | 34 | 65 |
| three-shot | 35 | 64 |

Document rows common to every run: **31** of 36 policies that any run read as a document. A link that fails in one run can succeed in another, so the per-run document subsets are not the same policies. Only the common subset is a like-for-like comparison, and the difference in subset size says nothing about the prompt.

Rows read as a document in some runs only -- zero-shot: ['50'], one-shot: ['105', '288', '85'], three-shot: ['105', '288', '51', '85']

## Agreement

### Common document rows (like for like) (n = 31)

| Field | zero-shot | one-shot | three-shot |
|---|---|---|---|
| Policy_scope | 74% | 87% | 84% |
| Value_chain_focus | 58% | 55% | 58% |
| Instrument_broad | 61% | 58% | 61% |
| Target_type | 32% | 52% | 68% |
| Target_binding | 32% | 42% | 61% |
| compliance_market_type | 90% | 87% | 90% |
| Broad_method | 32% | 23% | 52% |
| Specific_method | 35% | 35% | 35% |
| Instrument_type | 19% | 42% | 29% |
| Years_amended | 77% | 77% | 68% |
| **Mean of core fields** | **47%** | **50%** | **53%** |

### All rows, including the summary fallback (n = 99)

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

## Is the difference real?

b and c are the discordant pairs: policies only one of the two runs got right. p is the exact two-sided binomial test on them.

### McNemar: zero-shot vs one-shot -- all rows (n = 99)

| Field | only zero-shot | only one-shot | p (exact) |
|---|---|---|---|
| Policy_scope | 3 | 16 | 0.004 |
| Value_chain_focus | 8 | 19 | 0.052 |
| Instrument_broad | 3 | 5 | 0.727 |
| Target_type | 1 | 27 | 0.000 |
| Target_binding | 2 | 19 | 0.000 |
| compliance_market_type | 1 | 0 | 1.000 |
| Broad_method | 16 | 11 | 0.442 |
| Specific_method | 7 | 8 | 1.000 |
| Instrument_type | 2 | 28 | 0.000 |
| Years_amended | 1 | 1 | 1.000 |
| **All fields pooled** | **44** | **134** | **0.000** |

### McNemar: zero-shot vs three-shot -- all rows (n = 99)

| Field | only zero-shot | only three-shot | p (exact) |
|---|---|---|---|
| Policy_scope | 1 | 11 | 0.006 |
| Value_chain_focus | 5 | 20 | 0.004 |
| Instrument_broad | 7 | 7 | 1.000 |
| Target_type | 1 | 37 | 0.000 |
| Target_binding | 1 | 34 | 0.000 |
| compliance_market_type | 0 | 0 | 1.000 |
| Broad_method | 4 | 27 | 0.000 |
| Specific_method | 9 | 9 | 1.000 |
| Instrument_type | 3 | 28 | 0.000 |
| Years_amended | 5 | 1 | 0.219 |
| **All fields pooled** | **36** | **174** | **0.000** |

### McNemar: one-shot vs three-shot -- all rows (n = 99)

| Field | only one-shot | only three-shot | p (exact) |
|---|---|---|---|
| Policy_scope | 6 | 3 | 0.508 |
| Value_chain_focus | 6 | 10 | 0.454 |
| Instrument_broad | 5 | 3 | 0.727 |
| Target_type | 4 | 14 | 0.031 |
| Target_binding | 1 | 17 | 0.000 |
| compliance_market_type | 0 | 1 | 1.000 |
| Broad_method | 5 | 33 | 0.000 |
| Specific_method | 10 | 9 | 1.000 |
| Instrument_type | 7 | 6 | 1.000 |
| Years_amended | 4 | 0 | 0.125 |
| **All fields pooled** | **48** | **96** | **0.000** |

### McNemar: zero-shot vs one-shot -- common document rows (n = 31)

| Field | only zero-shot | only one-shot | p (exact) |
|---|---|---|---|
| Policy_scope | 2 | 6 | 0.289 |
| Value_chain_focus | 5 | 4 | 1.000 |
| Instrument_broad | 1 | 0 | 1.000 |
| Target_type | 0 | 6 | 0.031 |
| Target_binding | 1 | 4 | 0.375 |
| compliance_market_type | 1 | 0 | 1.000 |
| Broad_method | 6 | 3 | 0.508 |
| Specific_method | 2 | 2 | 1.000 |
| Instrument_type | 0 | 7 | 0.016 |
| Years_amended | 1 | 1 | 1.000 |
| **All fields pooled** | **19** | **33** | **0.070** |

### McNemar: zero-shot vs three-shot -- common document rows (n = 31)

| Field | only zero-shot | only three-shot | p (exact) |
|---|---|---|---|
| Policy_scope | 1 | 4 | 0.375 |
| Value_chain_focus | 3 | 3 | 1.000 |
| Instrument_broad | 2 | 2 | 1.000 |
| Target_type | 0 | 11 | 0.001 |
| Target_binding | 1 | 10 | 0.012 |
| compliance_market_type | 0 | 0 | 1.000 |
| Broad_method | 2 | 8 | 0.109 |
| Specific_method | 3 | 3 | 1.000 |
| Instrument_type | 2 | 5 | 0.453 |
| Years_amended | 4 | 1 | 0.375 |
| **All fields pooled** | **18** | **47** | **0.000** |

### McNemar: one-shot vs three-shot -- common document rows (n = 31)

| Field | only one-shot | only three-shot | p (exact) |
|---|---|---|---|
| Policy_scope | 2 | 1 | 1.000 |
| Value_chain_focus | 2 | 3 | 1.000 |
| Instrument_broad | 1 | 2 | 1.000 |
| Target_type | 0 | 5 | 0.062 |
| Target_binding | 0 | 6 | 0.031 |
| compliance_market_type | 0 | 1 | 1.000 |
| Broad_method | 3 | 12 | 0.035 |
| Specific_method | 4 | 4 | 1.000 |
| Instrument_type | 4 | 0 | 0.125 |
| Years_amended | 3 | 0 | 0.250 |
| **All fields pooled** | **19** | **34** | **0.053** |

