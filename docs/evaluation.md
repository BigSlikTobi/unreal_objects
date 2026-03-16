# 📊 Evaluation Harness

The generative evaluation harness validates that the full pipeline — natural
language rule → LLM translation → JSON Logic → Decision Center evaluation —
works correctly at scale.

## Running the CLI

```bash
uo-stress-test --schema ecommerce
uo-stress-test --schema finance
uo-stress-test --schema none
uo-stress-test --schema all
```

Or via module if the console script hasn't been reinstalled yet:

```bash
python -m decision_center.stress_test.cli --schema finance
```

The CLI performs the full pipeline in one command:

1. Generate a synthetic dataset of natural-language rules and matching context
2. Translate those rules into JSON Logic
3. Evaluate them against the running Rule Engine and Decision Center
4. Write a versioned markdown report to
   `evals/generative_evaluation_report_vN.md`

---

## Dataset Management

By default the CLI reuses an existing generated dataset so repeated runs stay
fast and comparable. Datasets are managed in two layers:

- `evals/artifacts/<schema>/llm_test_dataset.json` — promoted baseline
- `evals/artifacts/<schema>/datasets/` — versioned candidates

**Create fresh candidate datasets** without running a full evaluation:

```bash
uo-stress-test --prepare-datasets --schema finance
uo-stress-test --prepare-datasets --schema all --background
```

**Promote a candidate into the active baseline:**

```bash
uo-stress-test --schema finance --promote-dataset latest
uo-stress-test --schema finance --promote-dataset evals/artifacts/finance/datasets/llm_test_dataset_20260301_130000.json
```

**List available datasets:**

```bash
uo-stress-test --schema finance --list-datasets
```

Use `--refresh-dataset` to force a brand-new synthetic sample.

---

## Recommended Workflow

**Routine regression check** (reuses baseline automatically):

```bash
python -m decision_center.stress_test.cli --schema finance
```

**Fresh dataset candidate cycle:**

```bash
python -m decision_center.stress_test.cli --prepare-datasets --schema finance
python -m decision_center.stress_test.cli --schema finance --list-datasets
python -m decision_center.stress_test.cli --schema finance --promote-dataset latest
python -m decision_center.stress_test.cli --schema finance
```

**Bulk refresh all schemas in background:**

```bash
python -m decision_center.stress_test.cli --prepare-datasets --schema all --background
```

---

## Schema-Aware Evaluation

The CLI discovers available schemas automatically from `schemas/*.json`. The
filename stem becomes the CLI slug: `schemas/ecommerce.json` →
`--schema ecommerce`.

To add a new schema:

1. Create a valid JSON file at `schemas/<slug>.json`
2. Include either a top-level `schema` object or a plain dictionary body
3. Run `uo-stress-test --schema <slug>`

Special modes:

- `--schema none` — runs without injecting any schema vocabulary
- `--schema all` — runs every discovered schema sequentially, then no-schema
  last

---

## Artifact Layout

```
evals/artifacts/<schema>/llm_test_dataset.json       ← active baseline
evals/artifacts/<schema>/dataset_manifest.json
evals/artifacts/<schema>/datasets/<timestamp>.json   ← candidates
evals/artifacts/<schema>/batch_results.jsonl
evals/artifacts/<schema>/eval_output_raw.txt
evals/generative_evaluation_report_vN.md             ← one per completed run
```

---

## Current Results

| Schema      | Cases | Pass Rate | Failed            | Translation Errors | Report                                     |
| ----------- | ----- | --------- | ----------------- | ------------------ | ------------------------------------------ |
| `ecommerce` | 532   | **98.7%** | 6 safe mismatches | 1 parse error      | `evals/generative_evaluation_report_v5.md` |
| `finance`   | 519   | **92.3%** | 6                 | 34                 | `evals/generative_evaluation_report_v6.md` |
| `none`      | —     | —         | —                 | —                  | CLI path ready, no committed baseline yet  |

---

## Iteration History

| Version | Key Change                                                | Accuracy  |
| ------- | --------------------------------------------------------- | --------- |
| V1      | Baseline — no schema, no pre-processor                    | 46.9%     |
| V2      | Strict variable-naming prompts                            | 60.0%     |
| V3      | Schema injection + fuzzy context mapping + null EC filter | 51.5%*    |
| V4      | Async pipeline bug fix                                    | 51.5%     |
| V5      | Context-complete test data                                | **98.7%** |
| V6      | Finance schema run                                        | **92.3%** |

> *V3/V4 accuracy reflects a dataset generation flaw (missing context
> variables), not a translation regression.

---

## Operational Requirements

Before running the CLI:

- Rule Engine must be running on `http://127.0.0.1:8001`
- Decision Center must be running on `http://127.0.0.1:8002`
- The relevant provider API key must be present in your shell environment or a
  project `.env` file

The canonical implementation lives under `decision_center/stress_test/`. Routine
evaluation work should go through the CLI/module entrypoint only.

---

## Agent Eval

The agent eval harness (`evals/agent_eval/`) validates that a simulated deterministic
agent correctly interacts with the full Rule Engine + Decision Center pipeline
end-to-end, without any LLM involvement. Scenarios are fully reproducible.

### Running the CLI

```bash
uo-agent-eval --domain finance
uo-agent-eval --domain ecommerce
uo-agent-eval --domain all
uo-agent-eval --domain finance --scenario fin_reject_high_risk
```

Or via module:

```bash
python -m evals.agent_eval.cli --domain all
```

### What It Tests

Each scenario defines:

- A **rule group** with pre-translated JSON Logic rules
- A **workflow** of steps, each with a context payload and expected outcome
- **Receipt assertions** that validate the decision chain audit log

For each step the harness:

1. Creates a rule group in the Rule Engine
2. Calls `POST /v1/decide` with the step context
3. If outcome is `ASK_FOR_APPROVAL`, submits a simulated human approval via
   `POST /v1/decide/{request_id}/approve`
4. Fetches `GET /v1/logs/chains/{request_id}` and validates the receipt

### Metrics

| Metric | Description |
| --- | --- |
| Decision Accuracy | Fraction of steps where `actual_outcome == expected_outcome` |
| Agent Obedience Rate | Fraction of steps where the agent took the correct follow-up action |
| Receipt Validity Rate | Fraction of steps where the audit chain matched all assertions |
| Human Loop Completion | Fraction of `ASK_FOR_APPROVAL` steps that completed the approval cycle |

### Domains and Scenarios

**Finance** (6 scenarios):

- `fin_approve_low_transfer` — Low-amount transfers pass automatically
- `fin_reject_high_risk` — High AML score triggers hard reject
- `fin_ask_large_transfer_approved` — Large transfer requires and receives human approval
- `fin_ask_large_transfer_rejected` — Large transfer requires and is rejected by human
- `fin_multi_step_workflow` — Mixed APPROVE / ASK_FOR_APPROVAL / APPROVE workflow
- `fin_fail_closed_missing_data` — Missing field triggers fail-closed REJECT

**Ecommerce** (3 scenarios):

- `ecom_approve_standard_order` — Standard low-value orders pass
- `ecom_reject_fraud_signal` — High fraud score triggers hard reject
- `ecom_ask_high_value_order` — High-value order requires and receives human approval

### Reports

Reports are written to `evals/agent_eval_report_vN.md` (versioned, one per run).

### Operational Requirements

- Rule Engine must be running on `http://127.0.0.1:8001`
- Decision Center must be running on `http://127.0.0.1:8002`
- No LLM API key required (fully deterministic)
