import json
from unittest.mock import patch, MagicMock
import pytest
from pydantic import ValidationError
from decision_center.translator import (
    _validate_rule_payload,
    _validate_schema_variables,
    _validate_rule_logic_json_populated,
    _validate_candidate_alignment,
    _detect_unsupported_sentinel,
    _find_candidate_fields,
    swap_variable_in_result,
    check_llm_connection,
    translate_rule,
    SchemaConceptMismatchError,
)

@patch("openai.OpenAI")
def test_test_llm_connection_openai(mock_openai):
    mock_client = MagicMock()
    mock_openai.return_value = mock_client
    
    assert check_llm_connection("openai", "gpt-5.2", "fake_key") is True
    mock_client.models.retrieve.assert_called_once_with("gpt-5.2")

@patch("openai.OpenAI")
def test_test_llm_connection_openai_fail(mock_openai):
    mock_client = MagicMock()
    mock_client.models.retrieve.side_effect = Exception("Unauthorized")
    mock_openai.return_value = mock_client
    
    assert check_llm_connection("openai", "gpt-5.2", "fake_key") is False

@patch("anthropic.Anthropic")
def test_test_llm_connection_anthropic(mock_anthropic):
    mock_client = MagicMock()
    mock_anthropic.return_value = mock_client
    
    assert check_llm_connection("anthropic", "claude-4.5-haiku", "fake_key") is True
    mock_client.messages.create.assert_called_once()

@patch("google.genai.Client")
def test_test_llm_connection_gemini(mock_genai):
    mock_client = MagicMock()
    mock_genai.return_value = mock_client
    
    assert check_llm_connection("gemini", "gemini-3.0-flash", "fake_key") is True
    mock_client.models.get.assert_called_once_with(name="models/gemini-3.0-flash")

@patch("openai.OpenAI")
def test_translate_rule_openai(mock_openai):
    mock_client = MagicMock()
    mock_openai.return_value = mock_client
    
    # Mocking the JSON string response from chat.completions.create
    mock_message = MagicMock()
    mock_message.content = json.dumps({
        "datapoints": ["billing_amount"],
        "edge_cases": ["IF billing_amount < 0 THEN REJECT"],
        "edge_cases_json": [],
        "rule_logic": "IF billing_amount > 100 THEN ASK_FOR_APPROVAL",
        "rule_logic_json": {"if": [{">": [{"var": "billing_amount"}, 100]}, "ASK_FOR_APPROVAL", "APPROVE"]}
    })
    
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    
    mock_client.chat.completions.create.return_value = mock_response
    
    result = translate_rule("ask for approval if billing amount is > 100", "fraud", "Fraud Check", "openai", "gpt-5.2", "fake_key")
    
    assert result["datapoints"] == ["billing_amount"]
    assert result["edge_cases"] == ["IF billing_amount < 0 THEN REJECT"]
    assert result["rule_logic"] == "IF billing_amount > 100 THEN ASK_FOR_APPROVAL"
    mock_client.chat.completions.create.assert_called_once()


@patch("openai.OpenAI")
def test_translate_rule_openai_prompt_forbids_pseudo_datapoints_under_schema(mock_openai):
    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    mock_message = MagicMock()
    mock_message.content = json.dumps(
        {
            "datapoints": ["delivery_time_days"],
            "edge_cases": [],
            "edge_cases_json": [],
            "rule_logic": "IF delivery_time_days > 10 THEN REJECT",
            "rule_logic_json": {
                "if": [{">": [{"var": "delivery_time_days"}, 10]}, "REJECT", None]
            },
        }
    )
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_response

    translate_rule(
        "reject when delivery time is longer than 10 days",
        "ecommerce",
        "Delivery Rule",
        "openai",
        "gpt-5.2",
        "fake_key",
        context_schema={"delivery_time_days": "number"},
    )

    call = mock_client.chat.completions.create.call_args
    system_message = call.kwargs["messages"][0]["content"]
    assert "Never output pseudo-datapoints" in system_message
    assert "`exists`" in system_message


@patch("openai.OpenAI")
def test_translate_rule_openai_prompt_prefers_known_datapoints_in_no_schema_mode(mock_openai):
    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    mock_message = MagicMock()
    mock_message.content = json.dumps(
        {
            "datapoints": ["delivery_time_days"],
            "edge_cases": [],
            "edge_cases_json": [],
            "rule_logic": "IF delivery_time_days > 10 THEN REJECT",
            "rule_logic_json": {
                "if": [{">": [{"var": "delivery_time_days"}, 10]}, "REJECT", None]
            },
        }
    )
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_response

    translate_rule(
        "reject when delivery time is longer than 10 days",
        "ecommerce",
        "Delivery Rule",
        "openai",
        "gpt-5.2",
        "fake_key",
        datapoint_definitions=[{"name": "delivery_time_days", "type": "number"}],
    )

    call = mock_client.chat.completions.create.call_args
    user_prompt = call.kwargs["messages"][1]["content"]
    assert "Prefer reusing these exact datapoint names when they fit the rule." in user_prompt
    assert "delivery_time_days" in user_prompt


@patch("openai.OpenAI")
def test_translate_rule_openai_retries_schema_shaped_response(mock_openai):
    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    schema_message = MagicMock()
    schema_message.content = json.dumps(
        {
            "properties": {
                "datapoints": {"type": "array"},
                "rule_logic": {"type": "string"},
            },
            "required": ["datapoints", "rule_logic"],
            "rule_logic_json": {},
        }
    )
    valid_message = MagicMock()
    valid_message.content = json.dumps(
        {
            "datapoints": ["withdrawal_amount"],
            "edge_cases": [],
            "edge_cases_json": [],
            "rule_logic": "IF withdrawal_amount > 1000 THEN ASK_FOR_APPROVAL",
            "rule_logic_json": {
                "if": [{">": [{"var": "withdrawal_amount"}, 1000]}, "ASK_FOR_APPROVAL", None]
            },
        }
    )

    first_choice = MagicMock()
    first_choice.message = schema_message
    second_choice = MagicMock()
    second_choice.message = valid_message

    first_response = MagicMock()
    first_response.choices = [first_choice]
    second_response = MagicMock()
    second_response.choices = [second_choice]

    mock_client.chat.completions.create.side_effect = [first_response, second_response]

    result = translate_rule(
        "ask for approval if withdrawal_amount is > 1000",
        "finance",
        "Withdrawal Rule",
        "openai",
        "gpt-5.2",
        "fake_key",
    )

    assert result["datapoints"] == ["withdrawal_amount"]
    assert result["rule_logic"] == "IF withdrawal_amount > 1000 THEN ASK_FOR_APPROVAL"
    assert mock_client.chat.completions.create.call_count == 2


def test_validate_rule_payload_raises_validation_error_for_non_string_edge_cases():
    with pytest.raises(ValidationError):
        _validate_rule_payload(
            {
                "datapoints": ["withdrawal_amount"],
                "edge_cases": [None, 7],
                "edge_cases_json": [{}, {}],
                "rule_logic": "IF withdrawal_amount > 1000 THEN ASK_FOR_APPROVAL",
                "rule_logic_json": {
                    "if": [{">": [{"var": "withdrawal_amount"}, 1000]}, "ASK_FOR_APPROVAL", None]
                },
            }
        )


def test_validate_rule_payload_derives_datapoints_from_json_logic_when_missing():
    result = _validate_rule_payload(
        {
            "datapoints": [],
            "edge_cases": ["IF currency != 'EUR' THEN REJECT"],
            "edge_cases_json": [
                {"if": [{"!=": [{"var": "currency"}, "EUR"]}, "REJECT", None]}
            ],
            "rule_logic": "IF withdrawal_amount > 1000 THEN ASK_FOR_APPROVAL",
            "rule_logic_json": {
                "if": [{">": [{"var": "withdrawal_amount"}, 1000]}, "ASK_FOR_APPROVAL", None]
            },
        }
    )

    assert result["datapoints"] == ["withdrawal_amount", "currency"]


def test_validate_rule_payload_derives_datapoints_from_rule_text_when_json_logic_is_missing():
    result = _validate_rule_payload(
        {
            "datapoints": [],
            "edge_cases": [],
            "edge_cases_json": [],
            "rule_logic": "IF withdrawal_amount > 1000 THEN ASK_FOR_APPROVAL",
            "rule_logic_json": {},
        }
    )

    assert result["datapoints"] == ["withdrawal_amount"]


@patch("openai.OpenAI")
def test_translate_rule_filters_schema_external_datapoints_and_uses_schema_backfill(mock_openai):
    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    mock_message = MagicMock()
    mock_message.content = json.dumps(
        {
            "datapoints": ["time", "exists"],
            "edge_cases": [],
            "edge_cases_json": [],
            "rule_logic": "IF delivery_time_days > 10 THEN REJECT",
            "rule_logic_json": {
                "if": [{">": [{"var": "delivery_time_days"}, 10]}, "REJECT", None]
            },
        }
    )
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_response

    result = translate_rule(
        "reject when delivery time is longer than 10 days",
        "ecommerce",
        "Delivery Rule",
        "openai",
        "gpt-5.2",
        "fake_key",
        context_schema={"delivery_time_days": "number"},
    )

    assert result["datapoints"] == ["delivery_time_days"]


@patch("openai.OpenAI")
def test_translate_rule_filters_pseudo_datapoints_in_no_schema_mode(mock_openai):
    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    mock_message = MagicMock()
    mock_message.content = json.dumps(
        {
            "datapoints": ["time", "exists", "transaction_time_hour"],
            "edge_cases": [],
            "edge_cases_json": [],
            "rule_logic": "IF transaction_time_hour > 22 THEN REJECT",
            "rule_logic_json": {
                "if": [{">": [{"var": "transaction_time_hour"}, 22]}, "REJECT", None]
            },
        }
    )
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_response

    result = translate_rule(
        "reject transactions after 10pm",
        "finance",
        "Night Rule",
        "openai",
        "gpt-5.2",
        "fake_key",
    )

    assert result["datapoints"] == ["transaction_time_hour"]

@patch("anthropic.Anthropic")
def test_translate_rule_anthropic(mock_anthropic):
    mock_client = MagicMock()
    mock_anthropic.return_value = mock_client
    
    mock_block = MagicMock()
    mock_block.type = "tool_use"
    mock_block.name = "submit_rule"
    mock_block.input = {
        "datapoints": ["billing_amount"],
        "edge_cases": ["IF billing_amount < 0 THEN REJECT"],
        "rule_logic": "IF billing_amount > 100 THEN ASK_FOR_APPROVAL"
    }
    
    mock_response = MagicMock()
    mock_response.content = [mock_block]
    
    mock_client.messages.create.return_value = mock_response
    
    result = translate_rule("ask for approval if billing amount is > 100", "fraud", "Fraud Check", "anthropic", "claude-4.5-haiku", "fake_key")
    
    assert result["datapoints"] == ["billing_amount"]
    assert result["edge_cases"] == ["IF billing_amount < 0 THEN REJECT"]
    assert result["rule_logic"] == "IF billing_amount > 100 THEN ASK_FOR_APPROVAL"
    mock_client.messages.create.assert_called_once()

@patch("google.genai.Client")
def test_translate_rule_gemini(mock_genai):
    mock_client = MagicMock()
    mock_genai.return_value = mock_client
    
    mock_response = MagicMock()
    mock_response.text = '{"datapoints": ["billing_amount"], "edge_cases": ["IF billing_amount < 0 THEN REJECT"], "rule_logic": "IF billing_amount > 100 THEN ASK_FOR_APPROVAL"}'
    
    mock_client.models.generate_content.return_value = mock_response
    
    result = translate_rule("ask for approval if billing amount is > 100", "fraud", "Fraud Check", "gemini", "gemini-3.0-flash", "fake_key")
    
    assert result["datapoints"] == ["billing_amount"]
    assert result["edge_cases"] == ["IF billing_amount < 0 THEN REJECT"]
    assert result["rule_logic"] == "IF billing_amount > 100 THEN ASK_FOR_APPROVAL"
    mock_client.models.generate_content.assert_called_once()


# ---------------------------------------------------------------------------
# Schema hardening: prompt instructs the model on semantic concept matching
# ---------------------------------------------------------------------------

@patch("openai.OpenAI")
def test_schema_enforcement_prompt_forbids_concept_substitution(mock_openai):
    """System prompt must warn against mapping different concepts just because
    they share a unit (e.g. account_age_days ≠ delivery_time_days)."""
    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    mock_message = MagicMock()
    mock_message.content = json.dumps({
        "datapoints": ["delivery_time_days"],
        "edge_cases": [],
        "edge_cases_json": [],
        "rule_logic": "IF delivery_time_days > 10 THEN REJECT",
        "rule_logic_json": {"if": [{">": [{"var": "delivery_time_days"}, 10]}, "REJECT", None]},
    })
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_response

    translate_rule(
        "reject when delivery time is longer than 10 days",
        "ecommerce",
        "Delivery Rule",
        "openai",
        "gpt-5.2",
        "fake_key",
        context_schema={"delivery_time_days": "number", "account_age_days": "number"},
    )

    call = mock_client.chat.completions.create.call_args
    system_message = call.kwargs["messages"][0]["content"]
    # The prompt must contain a pre-ranked candidate hint to guide the model
    assert "ranked by relevance" in system_message
    # Both fields should appear in the prompt (full field list + possibly candidates)
    assert "account_age_days" in system_message
    assert "delivery_time_days" in system_message


@patch("openai.OpenAI")
def test_schema_enforcement_prompt_injects_candidate_fields_hint(mock_openai):
    """When the rule mentions 'delivery time', delivery_time_days should appear
    in the ranked-candidates section of the system prompt."""
    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    mock_message = MagicMock()
    mock_message.content = json.dumps({
        "datapoints": ["delivery_time_days"],
        "edge_cases": [],
        "edge_cases_json": [],
        "rule_logic": "IF delivery_time_days > 10 THEN REJECT",
        "rule_logic_json": {"if": [{">": [{"var": "delivery_time_days"}, 10]}, "REJECT", None]},
    })
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_response

    translate_rule(
        "reject when delivery time is longer than 10 days",
        "ecommerce",
        "Delivery Rule",
        "openai",
        "gpt-5.2",
        "fake_key",
        context_schema={
            "delivery_time_days": "number (actual or promised delivery duration in days)",
            "account_age_days": "number (days since user registration)",
        },
    )

    call = mock_client.chat.completions.create.call_args
    system_message = call.kwargs["messages"][0]["content"]
    # delivery_time_days must appear in the ranked candidate hint
    candidate_section = system_message.split("Most likely matching fields")[-1].split("All allowed schema")[0]
    assert "delivery_time_days" in candidate_section
    # account_age_days must NOT be the top candidate for a delivery-time rule
    lines = [l for l in candidate_section.splitlines() if l.strip().startswith("1.")]
    assert lines and "delivery_time_days" in lines[0]


@patch("openai.OpenAI")
def test_schema_enforcement_prompt_lists_fields_with_descriptions(mock_openai):
    """Schema fields must be presented as a readable list so the model can
    reason about semantics, not just pattern-match on names."""
    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    mock_message = MagicMock()
    mock_message.content = json.dumps({
        "datapoints": ["transaction_amount"],
        "edge_cases": [],
        "edge_cases_json": [],
        "rule_logic": "IF transaction_amount > 500 THEN REJECT",
        "rule_logic_json": {"if": [{">": [{"var": "transaction_amount"}, 500]}, "REJECT", None]},
    })
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_response

    translate_rule(
        "reject if transaction amount exceeds 500",
        "finance",
        "Amount Rule",
        "openai",
        "gpt-5.2",
        "fake_key",
        context_schema={
            "transaction_amount": "number (total transaction value)",
            "account_age_days": "number (days since account was created)",
        },
    )

    call = mock_client.chat.completions.create.call_args
    system_message = call.kwargs["messages"][0]["content"]
    # Fields should be listed line-by-line with their descriptions
    assert "transaction_amount" in system_message
    assert "account_age_days" in system_message
    # Description should appear (not just raw JSON)
    assert "days since account was created" in system_message


# ---------------------------------------------------------------------------
# _find_candidate_fields unit tests
# ---------------------------------------------------------------------------

def test_find_candidate_fields_returns_delivery_field_first_for_delivery_rule():
    schema = {
        "delivery_time_days": "number (actual or promised delivery duration in days)",
        "estimated_delivery_days": "number (estimated delivery duration in days)",
        "account_age_days": "number (days since user registration)",
        "transaction_amount": "number (total transaction value)",
    }
    candidates = _find_candidate_fields("delivery time is longer than 10 days", schema)
    assert candidates, "Should return at least one candidate"
    top_field = candidates[0][0]
    assert top_field in ("delivery_time_days", "estimated_delivery_days"), (
        f"Expected a delivery-related field first, got {top_field}"
    )
    # account_age_days must NOT be first
    assert top_field != "account_age_days"


def test_find_candidate_fields_returns_account_field_for_account_age_rule():
    schema = {
        "delivery_time_days": "number (actual or promised delivery duration in days)",
        "account_age_days": "number (days since user registration)",
        "transaction_amount": "number (total transaction value)",
    }
    candidates = _find_candidate_fields("reject if account is newer than 30 days", schema)
    fields = [f for f, _ in candidates]
    assert "account_age_days" in fields


def test_find_candidate_fields_empty_when_no_overlap():
    schema = {"transaction_amount": "number", "currency": "string"}
    result = _find_candidate_fields("reject huge shipments", schema)
    # No overlap between rule words and schema — result may be empty or low-score
    assert isinstance(result, list)


def test_find_candidate_fields_returns_at_most_top_n():
    schema = {f"field_{i}": f"description word delivery time days {i}" for i in range(10)}
    candidates = _find_candidate_fields("delivery time days", schema, top_n=3)
    assert len(candidates) <= 3


def test_find_candidate_fields_returns_tuples_of_field_and_description():
    schema = {"delivery_time_days": "number (delivery duration)"}
    candidates = _find_candidate_fields("delivery time", schema)
    if candidates:
        field, desc = candidates[0]
        assert field == "delivery_time_days"
        assert desc == "number (delivery duration)"


# ---------------------------------------------------------------------------
# Post-translation validators (unit tests)
# ---------------------------------------------------------------------------

def test_validate_schema_variables_passes_when_all_vars_in_schema():
    result = {
        "rule_logic_json": {"if": [{">": [{"var": "delivery_time_days"}, 10]}, "REJECT", None]},
        "edge_cases_json": [],
    }
    schema = {"delivery_time_days": "number"}
    # Should not raise
    _validate_schema_variables(result, schema)


def test_validate_schema_variables_raises_when_var_not_in_schema():
    result = {
        "rule_logic_json": {"if": [{">": [{"var": "account_age_days"}, 10]}, "REJECT", None]},
        "edge_cases_json": [],
    }
    schema = {"delivery_time_days": "number"}
    with pytest.raises(SchemaConceptMismatchError, match="account_age_days"):
        _validate_schema_variables(result, schema)


def test_validate_schema_variables_raises_for_edge_case_var_not_in_schema():
    result = {
        "rule_logic_json": {"if": [{">": [{"var": "delivery_time_days"}, 10]}, "REJECT", None]},
        "edge_cases_json": [
            {"if": [{"!=": [{"var": "unknown_field"}, "EUR"]}, "REJECT", None]}
        ],
    }
    schema = {"delivery_time_days": "number"}
    with pytest.raises(SchemaConceptMismatchError, match="unknown_field"):
        _validate_schema_variables(result, schema)


def test_validate_schema_variables_skips_when_no_schema():
    result = {
        "rule_logic_json": {"if": [{">": [{"var": "any_variable"}, 10]}, "REJECT", None]},
        "edge_cases_json": [],
    }
    # No schema → should not raise even for unknown variables
    _validate_schema_variables(result, None)
    _validate_schema_variables(result, {})


# ---------------------------------------------------------------------------
# _validate_rule_logic_json_populated unit tests
# ---------------------------------------------------------------------------

def test_validate_rule_logic_json_populated_raises_when_schema_and_empty_logic():
    result = {
        "rule_logic": "IF some_concept > 10 THEN REJECT",
        "rule_logic_json": {},
        "datapoints": [],
    }
    with pytest.raises(SchemaConceptMismatchError, match="does not map"):
        _validate_rule_logic_json_populated(result, {"delivery_time_days": "number"})


def test_validate_rule_logic_json_populated_passes_when_no_schema():
    result = {
        "rule_logic": "IF some_concept > 10 THEN REJECT",
        "rule_logic_json": {},
        "datapoints": [],
    }
    # No schema → not an error
    _validate_rule_logic_json_populated(result, None)
    _validate_rule_logic_json_populated(result, {})


def test_validate_rule_logic_json_populated_passes_when_logic_present():
    result = {
        "rule_logic": "IF delivery_time_days > 10 THEN REJECT",
        "rule_logic_json": {"if": [{">": [{"var": "delivery_time_days"}, 10]}, "REJECT", None]},
        "datapoints": ["delivery_time_days"],
    }
    _validate_rule_logic_json_populated(result, {"delivery_time_days": "number"})


def test_validate_rule_logic_json_populated_passes_when_no_condition_in_rule_text():
    # A rule with no IF/THEN condition and empty JSON is not a broken translation
    result = {
        "rule_logic": "Always REJECT",
        "rule_logic_json": {},
        "datapoints": [],
    }
    _validate_rule_logic_json_populated(result, {"delivery_time_days": "number"})


def test_detect_unsupported_sentinel_raises_on_unsupported_prefix():
    result = {
        "rule_logic": "UNSUPPORTED: 'delivery time in transit' is not available in the selected schema.",
        "rule_logic_json": {},
        "datapoints": [],
    }
    with pytest.raises(SchemaConceptMismatchError, match="UNSUPPORTED"):
        _detect_unsupported_sentinel(result)


def test_detect_unsupported_sentinel_passes_for_normal_rule():
    result = {
        "rule_logic": "IF delivery_time_days > 10 THEN REJECT",
        "rule_logic_json": {"if": [{">": [{"var": "delivery_time_days"}, 10]}, "REJECT", None]},
        "datapoints": ["delivery_time_days"],
    }
    # Should not raise
    _detect_unsupported_sentinel(result)


def test_detect_unsupported_sentinel_case_insensitive():
    result = {
        "rule_logic": "unsupported: concept not in schema",
        "rule_logic_json": {},
        "datapoints": [],
    }
    with pytest.raises(SchemaConceptMismatchError):
        _detect_unsupported_sentinel(result)


# ---------------------------------------------------------------------------
# Integration: translate_rule raises SchemaConceptMismatchError
# ---------------------------------------------------------------------------

@patch("openai.OpenAI")
def test_translate_rule_raises_when_llm_returns_variable_outside_schema(mock_openai):
    """If the LLM maps a concept to a schema field that is NOT in the provided
    schema, translate_rule must raise SchemaConceptMismatchError."""
    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    # LLM hallucinated account_age_days even though the active schema only has delivery_time_days
    mock_message = MagicMock()
    mock_message.content = json.dumps({
        "datapoints": ["account_age_days"],
        "edge_cases": [],
        "edge_cases_json": [],
        "rule_logic": "IF account_age_days > 10 THEN REJECT",
        "rule_logic_json": {"if": [{">": [{"var": "account_age_days"}, 10]}, "REJECT", None]},
    })
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_response

    with pytest.raises(SchemaConceptMismatchError, match="account_age_days"):
        translate_rule(
            "reject when delivery time is longer than 10 days",
            "ecommerce",
            "Delivery Rule",
            "openai",
            "gpt-5.2",
            "fake_key",
            context_schema={"delivery_time_days": "number"},
        )


@patch("openai.OpenAI")
def test_translate_rule_raises_when_rule_concept_has_no_schema_match(mock_openai):
    """When the LLM cannot map the concept and returns empty rule_logic_json
    with a condition in rule_logic, translate_rule must raise SchemaConceptMismatchError."""
    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    mock_message = MagicMock()
    mock_message.content = json.dumps({
        "datapoints": [],
        "edge_cases": [],
        "edge_cases_json": [],
        "rule_logic": "IF xenon_flux_density > 5 THEN REJECT",
        "rule_logic_json": {},
    })
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_response

    with pytest.raises(SchemaConceptMismatchError, match="does not map"):
        translate_rule(
            "reject when xenon flux density exceeds 5",
            "ecommerce",
            "Xenon Rule",
            "openai",
            "gpt-5.2",
            "fake_key",
            context_schema={"delivery_time_days": "number", "transaction_amount": "number"},
        )


@patch("openai.OpenAI")
def test_translate_rule_raises_when_llm_returns_empty_logic_with_condition(mock_openai):
    """Empty rule_logic_json combined with a conditional rule_logic string and
    an active schema means the concept could not be mapped — must raise."""
    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    mock_message = MagicMock()
    mock_message.content = json.dumps({
        "datapoints": [],
        "edge_cases": [],
        "edge_cases_json": [],
        "rule_logic": "IF in_transit_duration > 5 THEN REJECT",
        "rule_logic_json": {},
    })
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_response

    with pytest.raises(SchemaConceptMismatchError, match="does not map"):
        translate_rule(
            "reject when in-transit duration exceeds 5 days",
            "ecommerce",
            "Transit Rule",
            "openai",
            "gpt-5.2",
            "fake_key",
            context_schema={"delivery_time_days": "number"},
        )


@patch("openai.OpenAI")
def test_translate_rule_succeeds_when_llm_picks_correct_schema_field(mock_openai):
    """Sanity check: when the LLM returns a variable that IS in the schema,
    no error is raised and the result is returned normally."""
    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    mock_message = MagicMock()
    mock_message.content = json.dumps({
        "datapoints": ["delivery_time_days"],
        "edge_cases": [],
        "edge_cases_json": [],
        "rule_logic": "IF delivery_time_days > 10 THEN REJECT",
        "rule_logic_json": {"if": [{">": [{"var": "delivery_time_days"}, 10]}, "REJECT", None]},
    })
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_response

    result = translate_rule(
        "reject when delivery time is longer than 10 days",
        "ecommerce",
        "Delivery Rule",
        "openai",
        "gpt-5.2",
        "fake_key",
        context_schema={"delivery_time_days": "number", "account_age_days": "number"},
    )

    assert result["datapoints"] == ["delivery_time_days"]
    assert result["rule_logic"] == "IF delivery_time_days > 10 THEN REJECT"


def test_validate_candidate_alignment_autoswaps_when_both_fields_exist():
    """When both the wrong and better field exist in the schema, auto-swap."""
    schema = {
        "delivery_time_days": "number (actual or promised delivery duration in days)",
        "account_age_days": "number (days since user registration)",
    }
    result = {
        "rule_logic": "IF account_age_days > 10 THEN REJECT",
        "rule_logic_json": {"if": [{">": [{"var": "account_age_days"}, 10]}, "REJECT", None]},
        "datapoints": ["account_age_days"],
    }
    # Should NOT raise — auto-swaps account_age_days -> delivery_time_days
    _validate_candidate_alignment(
        result,
        "IF delivery_time is longer than 10 days THEN REJECT",
        schema,
    )
    assert result["datapoints"] == ["delivery_time_days"]
    assert result["rule_logic_json"] == {"if": [{">": [{"var": "delivery_time_days"}, 10]}, "REJECT", None]}


def test_validate_candidate_alignment_accepts_correct_field():
    """delivery_time_days is the best match and should pass."""
    schema = {
        "delivery_time_days": "number (actual or promised delivery duration in days)",
        "account_age_days": "number (days since user registration)",
    }
    result = {
        "rule_logic": "IF delivery_time_days > 10 THEN REJECT",
        "rule_logic_json": {"if": [{">": [{"var": "delivery_time_days"}, 10]}, "REJECT", None]},
        "datapoints": ["delivery_time_days"],
    }
    # Should not raise
    _validate_candidate_alignment(
        result,
        "IF delivery_time is longer than 10 days THEN REJECT",
        schema,
    )


def test_validate_candidate_alignment_skips_without_schema():
    result = {
        "rule_logic": "IF foo > 1 THEN REJECT",
        "rule_logic_json": {"if": [{">": [{"var": "foo"}, 1]}, "REJECT", None]},
        "datapoints": ["foo"],
    }
    # Should not raise when no schema
    _validate_candidate_alignment(result, "IF foo > 1 THEN REJECT", None)


def test_validate_candidate_alignment_skips_when_all_scores_zero():
    """If no field has any overlap the check should not reject."""
    schema = {
        "transaction_amount": "number",
        "user_country": "string",
    }
    result = {
        "rule_logic": "IF xyz > 5 THEN REJECT",
        "rule_logic_json": {"if": [{">": [{"var": "transaction_amount"}, 5]}, "REJECT", None]},
        "datapoints": ["transaction_amount"],
    }
    # "xyz" has zero overlap with everything, so top_score == 0 → skip
    _validate_candidate_alignment(result, "IF xyz > 5 THEN REJECT", schema)


def test_validate_candidate_alignment_raises_when_var_not_in_schema():
    """When the LLM invents a variable not in the schema, raise with the best match."""
    schema = {
        "delivery_time_days": "number (delivery duration in days)",
    }
    result = {
        "rule_logic": "IF shipping_delay > 10 THEN REJECT",
        "rule_logic_json": {"if": [{">": [{"var": "shipping_delay"}, 10]}, "REJECT", None]},
        "datapoints": ["shipping_delay"],
    }
    with pytest.raises(SchemaConceptMismatchError) as exc_info:
        _validate_candidate_alignment(
            result,
            "IF delivery_time is longer than 10 days THEN REJECT",
            schema,
        )
    assert exc_info.value.proposed_field is not None
    assert exc_info.value.proposed_field["name"] == "delivery_time_days"


def test_swap_variable_in_result_replaces_everywhere():
    result = {
        "datapoints": ["account_age_days", "currency"],
        "rule_logic": "IF account_age_days > 10 THEN REJECT",
        "rule_logic_json": {"if": [{">": [{"var": "account_age_days"}, 10]}, "REJECT", None]},
        "edge_cases": ["IF account_age_days < 0 THEN REJECT"],
        "edge_cases_json": [{"if": [{"<": [{"var": "account_age_days"}, 0]}, "REJECT", None]}],
    }
    swapped = swap_variable_in_result(result, "account_age_days", "delivery_time_days")
    assert swapped["datapoints"] == ["delivery_time_days", "currency"]
    assert "delivery_time_days" in swapped["rule_logic"]
    assert "account_age_days" not in swapped["rule_logic"]
    assert swapped["rule_logic_json"]["if"][0][">"][0] == {"var": "delivery_time_days"}
    assert "delivery_time_days" in swapped["edge_cases"][0]
    assert swapped["edge_cases_json"][0]["if"][0]["<"][0] == {"var": "delivery_time_days"}


def test_swap_variable_in_result_leaves_unrelated_vars_alone():
    result = {
        "datapoints": ["amount", "currency"],
        "rule_logic": "IF amount > 100 THEN ASK_FOR_APPROVAL",
        "rule_logic_json": {"if": [{">": [{"var": "amount"}, 100]}, "ASK_FOR_APPROVAL", None]},
        "edge_cases": [],
        "edge_cases_json": [],
    }
    swapped = swap_variable_in_result(result, "amount", "transaction_amount")
    assert swapped["datapoints"] == ["transaction_amount", "currency"]
    assert swapped["rule_logic_json"]["if"][0][">"][0] == {"var": "transaction_amount"}
    # currency must be unchanged — it wasn't swapped
    assert "currency" in swapped["datapoints"]

def test_swap_variable_replaces_repeated_occurrences():
    """Verify that multiple occurrences of the same variable in rule_logic
    and edge_cases are all replaced."""
    result = {
        "datapoints": ["amount", "currency"],
        "rule_logic": "IF amount > 100 AND amount < 500 THEN ASK_FOR_APPROVAL",
        "rule_logic_json": {
            "if": [
                {"and": [
                    {">": [{"var": "amount"}, 100]},
                    {"<": [{"var": "amount"}, 500]},
                ]},
                "ASK_FOR_APPROVAL",
                None,
            ]
        },
        "edge_cases": ["IF amount < 0 OR amount > 1000 THEN REJECT"],
        "edge_cases_json": [{
            "if": [
                {"or": [
                    {"<": [{"var": "amount"}, 0]},
                    {">": [{"var": "amount"}, 1000]},
                ]},
                "REJECT",
                None,
            ]
        }],
    }
    swapped = swap_variable_in_result(result, "amount", "price")
    
    # Check datapoints
    assert swapped["datapoints"] == ["price", "currency"]
    
    # Check rule_logic string has both occurrences replaced
    assert swapped["rule_logic"] == "IF price > 100 AND price < 500 THEN ASK_FOR_APPROVAL"
    assert "amount" not in swapped["rule_logic"]
    
    # Check rule_logic_json has both occurrences replaced
    assert swapped["rule_logic_json"]["if"][0]["and"][0][">"][0] == {"var": "price"}
    assert swapped["rule_logic_json"]["if"][0]["and"][1]["<"][0] == {"var": "price"}
    
    # Check edge_cases string has both occurrences replaced
    assert swapped["edge_cases"][0] == "IF price < 0 OR price > 1000 THEN REJECT"
    assert "amount" not in swapped["edge_cases"][0]
    
    # Check edge_cases_json has both occurrences replaced
    assert swapped["edge_cases_json"][0]["if"][0]["or"][0]["<"][0] == {"var": "price"}
    assert swapped["edge_cases_json"][0]["if"][0]["or"][1][">"][0] == {"var": "price"}


def test_swap_variable_does_not_replace_substrings():
    """Verify that swapping 'amount' does not replace it inside
    'transaction_amount' or other variables containing 'amount' as a substring."""
    result = {
        "datapoints": ["amount", "transaction_amount", "total_amount"],
        "rule_logic": "IF amount > 100 AND transaction_amount < 500 THEN ASK_FOR_APPROVAL",
        "rule_logic_json": {
            "if": [
                {"and": [
                    {">": [{"var": "amount"}, 100]},
                    {"<": [{"var": "transaction_amount"}, 500]},
                ]},
                "ASK_FOR_APPROVAL",
                None,
            ]
        },
        "edge_cases": ["IF total_amount > 1000 OR amount < 0 THEN REJECT"],
        "edge_cases_json": [{
            "if": [
                {"or": [
                    {">": [{"var": "total_amount"}, 1000]},
                    {"<": [{"var": "amount"}, 0]},
                ]},
                "REJECT",
                None,
            ]
        }],
    }
    swapped = swap_variable_in_result(result, "amount", "price")
    
    # Check datapoints: only "amount" should be swapped to "price"
    assert swapped["datapoints"] == ["price", "transaction_amount", "total_amount"]
    
    # Check rule_logic string: "amount" → "price", but "transaction_amount" unchanged
    assert "price > 100" in swapped["rule_logic"]
    assert "transaction_amount < 500" in swapped["rule_logic"]
    assert swapped["rule_logic"] == "IF price > 100 AND transaction_amount < 500 THEN ASK_FOR_APPROVAL"
    
    # Check rule_logic_json: only the standalone "amount" was replaced
    assert swapped["rule_logic_json"]["if"][0]["and"][0][">"][0] == {"var": "price"}
    assert swapped["rule_logic_json"]["if"][0]["and"][1]["<"][0] == {"var": "transaction_amount"}
    
    # Check edge_cases string: "amount" → "price", but "total_amount" unchanged
    assert "total_amount > 1000" in swapped["edge_cases"][0]
    assert "price < 0" in swapped["edge_cases"][0]
    assert swapped["edge_cases"][0] == "IF total_amount > 1000 OR price < 0 THEN REJECT"
    
    # Check edge_cases_json: only the standalone "amount" was replaced
    assert swapped["edge_cases_json"][0]["if"][0]["or"][0][">"][0] == {"var": "total_amount"}
    assert swapped["edge_cases_json"][0]["if"][0]["or"][1]["<"][0] == {"var": "price"}