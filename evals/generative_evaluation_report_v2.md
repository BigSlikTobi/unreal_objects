# Rule Engine End-to-End Generative Evaluation Report (V2 optimized)

**Date:** 2026-02-27\
**Total Test Cases Evaluated:** 515\
**Methodology:** OpenAI Batch API (GPT-5-mini) with strict variable prompt
adherence. The generator was explicitly prompted to embed the exact context JSON
keys into the natural language rule, and the translator was explicitly prompted
not to invent or normalize variables.

## Summary of Results

| Metric                            | Count | Percentage |
| :-------------------------------- | :---- | :--------- |
| **Total Cases**                   | 515   | 100.0%     |
| **Passed (Perfect Match)**        | 309   | 60.0%      |
| **Fail-Closed Mismatches (Safe)** | 204   | 39.6%      |
| **Parse / Translation Errors**    | 2     | 0.4%       |

## Analysis of the 60.0% Match Rate

By simply adding a "strict variable matching constraint" to the LLM system
prompts, we jumped from a **46.9%** success rate to a **60.0%** success rate.
The remaining **39.6%** of cases still safely trigger the Engine's fail-closed
mechanism, resulting in 0 insecure approvals.

Here is a breakdown of why 39.6% of the optimized rules still resulted in a
mismatch:

### 1. LLM Prompt Disobedience (The Remaining Semantic Gap)

Even after prompt optimization, GPT-5 occasionally fails to strictly align the
context data keys to the English text. For example, one generated rule stated:
_"If the category equals 'electronics' and the user_risk_score is greater than
50 then REJECT."_ However, if the corresponding `context_data` key provided by
the LLM was `merchant_category`, the strict JSON logic translation mapping
`category` resulted in missing data, safely triggering the fail-closed integrity
defense constraint (`Missing Variables`). **Insight:** LLMs still hallucinate
constraints when strictly prompted in zero-shot generation loops.

### 2. Edge Case Interference (The Safe Default)

In multiple mismatches, the LLM successfully aligned the variables, but it
generated an edge case that safely superseded the expected main logic. For
example, a prompt expected `APPROVE` based purely on
`"If transaction_amount <= 50 AND user_risk_score < 30"`. However, the
translator generated an edge case indicating that if the user's
`account_age_days` was missing, it should default to `REJECT`. Because the
`context_data` only provided `transaction_amount` and `user_risk_score`, the
engine correctly triggered the edgecase and returned `REJECT`. **Insight:** The
translator acts highly defensively by guarding any omitted generic attributes as
edge cases.

## Actionable Next Steps

To push the match rate to 99% in production, Prompt Engineering alone is not
enough. The Decision Center must utilize explicit Application Schemas:

1. **JSON Schema Context Injection:** Instead of relying on LLM alignment, the
   UI should allow users to select from explicitly defined organizational
   schemas (e.g., passing a specific `OrderSchema` JSON into the translator).
   The translator prompt must strictly validate the translated variables against
   these known keys.
2. **Context Mapping Pre-Processor:** Implement a mechanism to map generic
   variable names (e.g., `amount`) to explicit context paths (e.g.,
   `transaction.amount.value`) before hitting the strict `jsonLogic` engine.

## Conclusion

The V2 optimization highlights that while prompt engineering can close the
semantic gap by 13% (46.9% -> 60.0%), strict deterministic engines require
strict data schemas. In all 515 cases, the Engine successfully defaulted to
restricted safe-paths when confronted by ambiguity.
