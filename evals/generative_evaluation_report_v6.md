# Generative Evaluation Report

**Date**: 2026-03-01
**Provider**: openai
**Model**: gpt-5-mini-2025-08-07
**Schema Slug**: finance
**Schema Mode**: schema
**Schema Path**: schemas/finance.json

## Final Results

| Metric | Count |
| --- | ---: |
| Total Cases | 519 |
| Passed | 479 |
| Failed | 6 |
| Translation Errors | 34 |
| Rule Upload Errors | 0 |
| Decision Errors | 0 |
| Pass Rate | 92.3% |

## Artifact Locations

| Artifact | Path |
| --- | --- |
| Dataset | evals/artifacts/finance/llm_test_dataset.json |
| Translations | evals/artifacts/finance/batch_results.jsonl |
| Raw Eval Log | evals/artifacts/finance/eval_output_raw.txt |
| Report | evals/generative_evaluation_report_v6.md |

## Mismatch Analysis

- Case 30: expected None, actual None
- Case 50: expected ASK_FOR_APPROVAL, actual APPROVE
- Case 51: expected None, actual None
- Case 75: expected None, actual None
- Case 83: expected None, actual None
- Case 111: expected None, actual None
- Case 123: expected None, actual None
- Case 142: expected ASK_FOR_APPROVAL, actual APPROVE
- Case 155: expected None, actual None
- Case 162: expected None, actual None
- Case 166: expected None, actual None
- Case 168: expected None, actual None
- Case 195: expected None, actual None
- Case 204: expected None, actual None
- Case 207: expected None, actual None
- Case 220: expected None, actual None
- Case 234: expected None, actual None
- Case 244: expected None, actual None
- Case 263: expected None, actual None
- Case 276: expected REJECT, actual APPROVE
- Case 281: expected REJECT, actual ASK_FOR_APPROVAL
- Case 284: expected None, actual None
- Case 287: expected None, actual None
- Case 288: expected REJECT, actual APPROVE
- Case 290: expected ASK_FOR_APPROVAL, actual APPROVE
- Case 302: expected None, actual None
- Case 304: expected None, actual None
- Case 312: expected None, actual None
- Case 314: expected None, actual None
- Case 367: expected None, actual None
- Case 385: expected None, actual None
- Case 387: expected None, actual None
- Case 390: expected None, actual None
- Case 416: expected None, actual None
- Case 441: expected None, actual None
- Case 443: expected None, actual None
- Case 446: expected None, actual None
- Case 463: expected None, actual None
- Case 466: expected None, actual None
- Case 478: expected None, actual None
