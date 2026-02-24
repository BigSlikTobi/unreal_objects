import pytest
from unittest.mock import patch, MagicMock

# We will implement these in decision_center.cli shortly
try:
    from decision_center.cli import prompt_start_servers, prompt_group_selection, prompt_llm_setup, prompt_rule_creation, prompt_auto_test
except ImportError:
    # Dummy implementations so test collection doesn't instantly crash,
    # but the tests will still fail because they aren't fully implemented.
    def prompt_start_servers():
        raise NotImplementedError()
    def prompt_group_selection():
        raise NotImplementedError()
    def prompt_llm_setup():
        raise NotImplementedError()
    def prompt_rule_creation(group_id: str, llm_config: dict | None = None):
        raise NotImplementedError()
    def prompt_auto_test(group_id: str, rule: dict):
        raise NotImplementedError()

@patch("builtins.input", side_effect=["y"])
@patch("subprocess.Popen")
def test_prompt_start_servers_yes(mock_popen, mock_input):
    prompt_start_servers()
    assert mock_popen.call_count == 2
    
@patch("builtins.input", side_effect=["n"])
@patch("subprocess.Popen")
def test_prompt_start_servers_no(mock_popen, mock_input):
    prompt_start_servers()
    mock_popen.assert_not_called()

@patch("builtins.input", side_effect=["CREATE", "My Group", "A test group"])
@patch("httpx.Client.post")
@patch("httpx.Client.get")
def test_prompt_group_selection_create(mock_get, mock_post, mock_input):
    # Mock GET for listing groups initially returning empty
    mock_get_resp = MagicMock()
    mock_get_resp.status_code = 200
    mock_get_resp.json.return_value = []
    mock_get.return_value = mock_get_resp

    mock_post_resp = MagicMock()
    mock_post_resp.status_code = 201
    mock_post_resp.json.return_value = {"id": "123", "name": "My Group", "description": "A test group", "rules": []}
    mock_post.return_value = mock_post_resp
    
    group_id = prompt_group_selection()
    
    assert group_id == "123"
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert "json" in kwargs
    assert kwargs["json"] == {"name": "My Group", "description": "A test group"}

@patch("builtins.input", side_effect=["My Rule", "Fraud Check", "amount, user_idx", "IF amount > 500 THEN REJECT"])
@patch("httpx.Client.post")
def test_prompt_rule_creation(mock_post, mock_input):
    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.json.return_value = {"id": "rule_1", "name": "My Rule"}
    mock_post.return_value = mock_resp
    
    rule = prompt_rule_creation("group_123", llm_config=None)
    assert rule["id"] == "rule_1"
    
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert "json" in kwargs
    assert kwargs["json"] == {
        "name": "My Rule",
        "feature": "Fraud Check",
        "datapoints": ["amount", "user_idx"],
        "edge_cases": [],
        "rule_logic": "IF amount > 500 THEN REJECT"
    }

@patch("builtins.input", side_effect=["750", "user_123", "test description"])
@patch("httpx.Client.get")
def test_prompt_auto_test(mock_get, mock_input):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"outcome": "ASK_FOR_APPROVAL", "matched_rules": ["rule_1"], "request_id": "req_1"}
    mock_get.return_value = mock_resp
    
    rule = {"id": "rule_1", "name": "My Rule", "datapoints": ["amount", "user_idx"]}
    
    prompt_auto_test("group_123", rule)
    
    mock_get.assert_called_once()
    args, kwargs = mock_get.call_args
    url = str(args[0])
    assert "v1/decide" in url
    assert "request_description=test%20description" in url
    assert "750" in url
    assert "user_123" in url
    assert "group_123" in url

@patch("builtins.input", side_effect=["y", "1", "2", "test_key"])
@patch("decision_center.cli.check_llm_connection", return_value=True)
def test_prompt_llm_setup_yes(mock_check, mock_input):
    config = prompt_llm_setup()
    assert config is not None
    assert config["provider"] == "openai"
    assert config["model"] == "gpt-5-mini"
    assert config["api_key"] == "test_key"
    mock_check.assert_called_once_with("openai", "gpt-5-mini", "test_key")

@patch("builtins.input", side_effect=["n"])
def test_prompt_llm_setup_no(mock_input):
    config = prompt_llm_setup()
    assert config is None

@patch("builtins.input", side_effect=["My LLM Rule", "Fraud Feature", "if they owe more than 100 then ask them"])
@patch("decision_center.cli.translate_rule")
@patch("httpx.Client.post")
def test_prompt_rule_creation_with_llm(mock_post, mock_translate, mock_input):
    llm_config = {"provider": "openai", "model": "gpt-5.2", "api_key": "test_key"}
    
    # Mock the LLM translator output
    mock_translate.return_value = {
        "datapoints": ["amount_owed"],
        "rule_logic": "IF amount_owed > 100 THEN ASK_FOR_APPROVAL"
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.json.return_value = {"id": "rule_llm_1", "name": "My LLM Rule"}
    mock_post.return_value = mock_resp

    rule = prompt_rule_creation("group_123", llm_config=llm_config)
    
    assert rule["id"] == "rule_llm_1"
    mock_translate.assert_called_once_with(
        natural_language="if they owe more than 100 then ask them",
        feature="Fraud Feature",
        name="My LLM Rule",
        provider="openai",
        model="gpt-5.2",
        api_key="test_key"
    )
    
    args, kwargs = mock_post.call_args
    assert kwargs["json"] == {
        "name": "My LLM Rule",
        "feature": "Fraud Feature",
        "datapoints": ["amount_owed"],
        "edge_cases": [],
        "rule_logic": "IF amount_owed > 100 THEN ASK_FOR_APPROVAL"
    }
