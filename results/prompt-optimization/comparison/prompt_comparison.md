# Prompt comparison: v1 vs. v2

- Policies compared: 99 (the test split)
- Run: 2026-11-20
- Mean exact agreement over the six core fields: **44% → 53%** (+9 pp)
- Field results that changed: 134 fixed (wrong → right), 77 broken (right → wrong)

## Per field

| Field | Accuracy v1 | Accuracy v2 | Change | Macro-F1 v1 | Macro-F1 v2 | Fixed | Broken |
|---|---|---|---|---|---|---|---|
| **Policy_scope** | 78% | 87% | +9 pp | 0.78 | 0.87 | 19 | 10 |
| **Value_chain_focus** | 42% | 75% | +32 pp | 0.43 | 0.64 | 47 | 15 |
| **Instrument_broad** | 59% | 61% | +2 pp | 0.55 | 0.53 | 20 | 18 |
| Target_type | 31% | 34% | +3 pp | 0.23 | 0.25 | 14 | 11 |
| Target_binding | 24% | 23% | -1 pp | 0.21 | 0.21 | 7 | 8 |
| compliance_market_type | 89% | 90% | +1 pp | 0.24 | 0.24 | 1 | 0 |
| **Broad_method** | 36% | 43% | +7 pp | 0.39 | 0.42 | 12 | 5 |
| **Specific_method** | 32% | 30% | -2 pp | 0.18 | 0.21 | 4 | 6 |
| **Instrument_type** | 14% | 20% | +6 pp | 0.25 | 0.28 | 9 | 3 |
| Years_amended | 77% | 77% | +0 pp | 0.17 | 0.22 | 1 | 1 |

Core fields in bold.

## Targeted error patterns

| Pattern | v1 | v2 |
|---|---|---|
| Framework coded as Instrument | 20 | 1 |
| Cross-cutting coded as Demand | 30 | 1 |
| Other coded as Regulatory instrument | 12 | 2 |
| Instrument types listed that experts did not code (total) | 367 | 242 |
| Instrument types per policy (mean; experts ≈ 1.3) | 4.5 | 3.3 |

## Mean core agreement by input type

| Input type | n | v1 | v2 |
|---|---|---|---|
| no_text | 25 | 45% | 64% |
| policy_text | 56 | 43% | 49% |
| webpage_description | 18 | 45% | 47% |

## Where the change introduced new errors

Instrument_broad: 18, Value_chain_focus: 15, Target_type: 11, Policy_scope: 10, Target_binding: 8, Specific_method: 6, Broad_method: 5, Instrument_type: 3, Years_amended: 1

Details per policy: `flips.csv`.

## How to read this

- Both runs coded the same 99 policies from the same retrieved text; only the prompt differs.
- With about 100 policies, a change of a few percentage points can be noise. The fixed/broken counts show whether a gain is a real shift or errors moving around.
- The prompt rules were derived from the train split only, so this test comparison is independent.
