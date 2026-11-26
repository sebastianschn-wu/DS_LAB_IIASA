# Prompt optimization

Targets the four systematic errors from the benchmark (and Elina's feedback) instead of trying to improve
everything at once, then checks the revised prompt on the independent test split, including **new errors**
it might introduce.

| | Pattern | Train split, zero-shot first loop |
|---|---|---|
| P1 | Framework coded as Instrument | 65 of 130 frameworks |
| P2 | Cross-cutting coded as Demand | 60 of 134 cross-cutting policies (65% of them NDCs, 83% with an emissions target) |
| P3 | Other coded as Regulatory instrument | 39 of 63 "Other" policies (97% strategies/plans) |
| P4 | Too many instrument types | model 2.8 per policy vs. experts 1.3 |

Full numbers: `results/prompt-optimization/error_analysis.md`.

## Workflow

1. **Error analysis (train split only)**

   ```bash
   python src/scripts/prompt-optimization/error-analysis.script.py
   ```

   Outputs go to `results/prompt-optimization/`:
   - `error_analysis.md`: counts and evidence per pattern.
   - `error_review.xlsx`: 15 sampled policies per pattern, with `cause` (drop-down) and `notes` columns for
     the manual review.
   - `error_rows.csv`: all flagged rows.

   The default input is the first-loop run. Use `--predictions results/baseline/retrieved_v1_train.csv`
   after a train-split baseline run.

2. **Prompt v2** (`prompt_versions.py`): v1 plus one clarification per pattern. Plus "Code this policy"
   instead of "Code this instrument" in the user prompt.
   - P1: NDCs, strategies, plans, roadmaps and climate laws with national targets → Framework.
   - P2: an emissions or net-zero target alone ≠ Demand. Demand = buyers or payment for removal units (ETS
     or compliance rules, crediting, procurement, CfDs).
   - P3: Regulatory = binding acts and NDCs. Strategies, plans and communications → Other or Information
     instrument.
   - P4: only instrument types the policy itself establishes, not ones it merely mentions. Frameworks: target
     or Other.

   Every rule matches the expert coding on the train split. For example, all 42 train NDCs are Framework,
   Regulatory and Cross-cutting, and 119 of 130 train frameworks have exactly one instrument type. The test
   split was not used. **The rules describe how the experts applied the codebook, so they should be
   confirmed with IIASA.**

3. **Run v1 and v2 on the same test policies and compare**

   ```bash
   python src/scripts/baseline/baseline.script.py --prompt v1
   python src/scripts/baseline/baseline.script.py --prompt v2
   python src/scripts/prompt-optimization/compare-prompts.script.py \
       --before "v1=results/baseline/retrieved_v1_test.csv" \
       --after "v2=results/baseline/retrieved_v2_test.csv"
   ```

   Outputs go to `results/prompt-optimization/comparison/`:
   - `prompt_comparison.md`: accuracy and macro-F1 per field before/after, the pattern counts before/after,
     and results per input type.
   - The **fixed** (wrong → right) and **broken** (right → wrong) counts per field.
   - `flips.csv`: every policy and field whose result changed.

   Both runs use the same cached text, so only the prompt differs.

## Tests

```bash
python -m pytest src/scripts/prompt-optimization/tests -q
```

## Rules after the model (hybrid: rules + LLM)

`rules.py` and `apply-rules.script.py` set the values that follow fixed conventions in the expert coding. The
rules use only the title and the model's own output, so they also work on new (scraped) policies.

| Rule | What it does | Evidence on the train split |
|---|---|---|
| R1 NDC | (I)NDC in the title → Framework, Regulatory instrument, Cross-cutting, Instrument_type target, Target_type Emissions | 42 of 42 NDCs |
| R2 Framework | Policy_scope Framework → Instrument_type target if the model coded a target, otherwise Other | 109 of 130 frameworks (84%) |

```bash
python src/scripts/prompt-optimization/apply-rules.script.py results/baseline/retrieved_v2_test.csv
# -> results/baseline/retrieved_v2_test_rules.csv (no model call, takes seconds)
```

Results on the 74 test policies with a document: core mean 49% → 56% (change against v1 +12 pp, 95% CI +6.1
to +18.7 pp). Instrument_type rises from 12% to 41% and Instrument_broad from 58% to 69%.
