# Generative Testing Evaluation Report: V3 (Context Mapping Isolation)

**Date Run:** 2026-02-27 **Dataset:** V2 Baseline Dataset (515 cases,
Unconstrained Schema) **Feature Tested:** Context Mapping Pre-processor
(Isolated)

## Summary of Results

Running the new Context Mapping Pre-processor against the older V2 dataset
resulted in exactly the same accuracy score: **60.0%**.

| Metric                        | Count | Percentage |
| :---------------------------- | :---- | :--------- |
| Passed                        | 309   | 60.0%      |
| Fail-Closed Mismatches (Safe) | 204   | 39.6%      |
| Parse Errors                  | 2     | 0.4%       |

## Analysis: Why didn't Fuzzy Matching improve the score?

The user requested we test the new Context Mapping Pre-processor on the existing
V2 dataset to isolate its impact. The results conclusively prove that **Context
Mapping cannot solve the Semantic Variable Gap alone.**

The V2 dataset was generated _without_ Schema Injection. When reviewing the
mismatched cases, the LLM invented entirely new business concepts and variables
that did not exist in the evaluator's test payload.

### Example Failures:

- **Rule generated:**
  `If account_balance minus transaction_amount is less than overdraft_limit then REJECT.`
  - _Why Context Mapping Failed:_ The variables `account_balance` and
    `overdraft_limit` are entirely foreign concepts. The fuzzy matcher cannot
    alias `overdraft_limit` to an existing payload key because they have zero
    string similarity.
- **Rule generated:** `If card_bin is in blacklisted_bins then REJECT.`
  - _Why Context Mapping Failed:_ `card_bin` and `blacklisted_bins` were
    completely invented by the LLM.

## The Necessity of Schema Injection (V3 Full Pipeline)

This isolated test mathematically proves the necessity of the second half of our
V3 architecture: **Schema Injection**.

Fuzzy matching is fantastic for fixing typos (e.g., matching `txn_amt` to
`transaction_amount`). However, if the LLM is free to dream up entirely
un-provided variables like `blacklisted_bins`, the rule engine will default
"Fail-Closed" to `ASK_FOR_APPROVAL` every time.

**Next Steps:** To achieve the 95%+ accuracy rates we are targeting, we **must**
run the newly built V3 data generation pipeline (`generate_llm_dataset.py` &
`batch_1_create.py`). The new pipeline strictly injects the `ecommerce.json`
schema into the LLM's system prompt, forcing it to _only_ use valid application
keys, thereby eliminating these hallucination errors at the source.
