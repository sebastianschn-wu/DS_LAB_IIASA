# Error analysis: systematic disagreements

- Predictions: `first_loop_coding.csv`
- Policies: 228 (the train split)
- Run: 2026-11-20
- Document kind is guessed from the title (NDC, strategy/plan, law/regulation, scheme/fund/market, other).

## Framework coded as Instrument (P1_scope)

- **65** of 130 policies the experts coded as Framework
- Hypothesis: Strategies, plans, NDCs and climate laws are read as instruments; the prompt calls every document an 'instrument'.
- Document kinds among these: strategy/plan 41 (63%), NDC 18 (28%), law/regulation 4 (6%), other 2 (3%)
- Input used: summary 49 (75%), document 16 (25%)
- Expert Instrument_type: target 30 (46%), Other 22 (34%), rd_d_funding; Other 3 (5%), (empty) 1 (2%), mrv_standard; Other 1 (2%), operating_subsidy 1 (2%), other 7 (11%)

## Cross-cutting coded as Demand (P2_value_chain)

- **60** of 134 policies the experts coded as Cross-cutting
- Hypothesis: General emissions or net-zero targets and strategies are read as creating demand (the codebook's Demand definition mentions 'binding targets').
- Document kinds among these: NDC 39 (65%), strategy/plan 15 (25%), law/regulation 5 (8%), scheme/fund/market 1 (2%)
- Input used: summary 52 (87%), document 8 (13%)
- Expert Instrument_type: target 51 (85%), Other 8 (13%), crediting_mechanism; mrv_standard 1 (2%)
- Expert Target_type: Emissions 50 (83%), (none) 8 (13%), CDR 2 (3%)

## Other coded as Regulatory instrument (P3_instrument_broad)

- **39** of 63 policies the experts coded as Other
- Hypothesis: Any official or formal document is read as a regulatory instrument, even when its function is strategic or institutional.
- Document kinds among these: strategy/plan 38 (97%), other 1 (3%)
- Input used: summary 25 (64%), document 14 (36%)
- Expert Instrument_type: Other 22 (56%), target 12 (31%), rd_d_funding; Other 2 (5%), (empty) 1 (3%), target; regulatory_safeguard 1 (3%), Other; target 1 (3%)

## Too many instrument types (P4_instrument_type)

- **129** of 228 policies
- Hypothesis: Mechanisms that are only mentioned (or planned, or belong to other policies) are listed as if the policy established them.
- Document kinds among these: strategy/plan 71 (55%), NDC 21 (16%), law/regulation 19 (15%), other 15 (12%), scheme/fund/market 3 (2%)
- Input used: summary 82 (64%), document 47 (36%)
- Instrument types per policy: experts 1.3 on average, model 2.8
- Extra types the model lists (not in expert coding): 461 in total
- Most frequent extra types: mrv_standard 84 (20%), regulatory_safeguard 67 (16%), target 50 (12%), community_safeguard 39 (9%), public_procurement 31 (7%), operating_subsidy 27 (6%), other 125 (30%)

## Reference: what the experts code as Demand

- 15 policies; Instrument_type: compliance_market_integration; mrv_standard 4 (27%), public_procurement 3 (20%), crediting_mechanism; mrv_standard 2 (13%), compliance_market_integration; regulatory_safeguard 1 (7%), compliance_market_integration 1 (7%), compliance_market_integration; crediting_mechanism; mrv_standard 1 (7%), other 3 (20%)

## Next step

Open `error_review.xlsx`, read each sampled policy (link in the sheet) and pick a cause. Causes that come up repeatedly become rules in prompt v2 (`prompt_versions.py`).
