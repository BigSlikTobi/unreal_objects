import pytest
import json
from unittest.mock import patch, MagicMock
from decision_center.translator import check_llm_connection, translate_rule

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
