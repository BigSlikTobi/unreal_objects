import pytest
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
    
    # Mocking the Pydantic parsed response from beta.chat.completions.parse
    mock_parsed = MagicMock()
    mock_parsed.model_dump.return_value = {
        "datapoints": ["billing_amount"],
        "edge_cases": ["IF billing_amount < 0 THEN REJECT"],
        "rule_logic": "IF billing_amount > 100 THEN ASK_FOR_APPROVAL"
    }
    
    mock_message = MagicMock()
    mock_message.parsed = mock_parsed
    
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    
    mock_client.beta.chat.completions.parse.return_value = mock_response
    
    result = translate_rule("ask for approval if billing amount is > 100", "fraud", "Fraud Check", "openai", "gpt-5.2", "fake_key")
    
    assert result["datapoints"] == ["billing_amount"]
    assert result["edge_cases"] == ["IF billing_amount < 0 THEN REJECT"]
    assert result["rule_logic"] == "IF billing_amount > 100 THEN ASK_FOR_APPROVAL"
    mock_client.beta.chat.completions.parse.assert_called_once()

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
