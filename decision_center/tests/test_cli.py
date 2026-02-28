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

@patch("builtins.input", side_effect=["My Rule", "Fraud Check", "amount, user_idx", "", "IF amount > 500 THEN REJECT"])
@patch("httpx.Client.post")
def test_prompt_rule_creation(mock_post, mock_input):
    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.json.return_value = {
        "id": "rule_1", 
        "name": "My Rule", 
        "rule_logic": "IF amount > 500 THEN REJECT", 
        "edge_cases": []
    }
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
        "edge_cases_json": [],
        "rule_logic": "IF amount > 500 THEN REJECT",
        "rule_logic_json": {}
    }

@patch("builtins.input", side_effect=["750", "user_123", "test description"])
@patch("httpx.Client.get")
def test_prompt_auto_test(mock_get, mock_input):
    # First call fetches group datapoint definitions, second call is the decide endpoint
    group_resp = MagicMock()
    group_resp.status_code = 200
    group_resp.json.return_value = {"datapoint_definitions": []}

    decide_resp = MagicMock()
    decide_resp.status_code = 200
    decide_resp.json.return_value = {"outcome": "ASK_FOR_APPROVAL", "matched_rules": ["rule_1"], "request_id": "req_1", "matched_details": []}

    mock_get.side_effect = [group_resp, decide_resp]

    rule = {"id": "rule_1", "name": "My Rule", "datapoints": ["amount", "user_idx"]}

    prompt_auto_test("group_123", rule)

    assert mock_get.call_count == 2
    # Second call is the decide endpoint
    url = str(mock_get.call_args_list[1][0][0])
    assert "v1/decide" in url
    assert "request_description=test%20description" in url
    assert "750" in url
    assert "user_123" in url
    assert "group_123" in url


@patch("builtins.input", side_effect=["y", "1", "2"])
@patch("getpass.getpass", return_value="test_key")
@patch("decision_center.cli.check_llm_connection", return_value=True)
def test_prompt_llm_setup_yes(mock_check, mock_getpass, mock_input):
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

@patch("builtins.input", side_effect=["My LLM Rule", "Fraud Feature", "if they owe more than 100 then ask them", "A"])
@patch("decision_center.cli.translate_rule")
@patch("httpx.Client.post")
@patch("httpx.Client.get")
def test_prompt_rule_creation_with_llm(mock_get, mock_post, mock_translate, mock_input):
    llm_config = {"provider": "openai", "model": "gpt-5.2", "api_key": "test_key"}

    # Group has one pre-existing datapoint definition
    mock_get_resp = MagicMock()
    mock_get_resp.status_code = 200
    mock_get_resp.json.return_value = {
        "rules": [],
        "datapoint_definitions": [{"name": "existing_dp", "type": "text", "values": []}]
    }
    mock_get.return_value = mock_get_resp

    # Only uses the known datapoint — no new ones, so no extra input() calls needed
    mock_translate.return_value = {
        "datapoints": ["existing_dp"],
        "edge_cases": ["IF currency <> eur THEN REJECT"],
        "edge_cases_json": [{"if": [{"!=": [{"var": "currency"}, "eur"]}, "REJECT", None]}],
        "rule_logic": "IF amount_owed > 100 THEN ASK_FOR_APPROVAL",
        "rule_logic_json": {"if": [{">": [{"var": "amount_owed"}, 100]}, "ASK_FOR_APPROVAL", "APPROVE"]}
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.json.return_value = {
        "id": "rule_llm_1",
        "name": "My LLM Rule",
        "rule_logic": "IF amount_owed > 100 THEN ASK_FOR_APPROVAL",
        "rule_logic_json": {"if": [{">": [{"var": "amount_owed"}, 100]}, "ASK_FOR_APPROVAL", "APPROVE"]},
        "edge_cases": ["IF currency <> eur THEN REJECT"],
        "edge_cases_json": [{"if": [{"!=": [{"var": "currency"}, "eur"]}, "REJECT", None]}],
    }
    mock_post.return_value = mock_resp

    rule = prompt_rule_creation("group_123", llm_config=llm_config)

    assert rule["id"] == "rule_llm_1"
    # KEY ASSERTION: datapoint_definitions must be forwarded to the LLM
    mock_translate.assert_called_once_with(
        natural_language="if they owe more than 100 then ask them",
        feature="Fraud Feature",
        name="My LLM Rule",
        provider="openai",
        model="gpt-5.2",
        api_key="test_key",
        datapoint_definitions=[{"name": "existing_dp", "type": "text", "values": []}],
    )


@patch("builtins.input", side_effect=[
    # prompt_rule_creation: name, feature, natural language, accept
    "New Rule", "Fraud", "rule with new dp", "A",
    # _prompt_datapoint_type for 'new_dp': type = number (2)
    "2",
])
@patch("decision_center.cli.translate_rule")
@patch("httpx.Client.patch")
@patch("httpx.Client.post")
@patch("httpx.Client.get")
def test_prompt_rule_creation_saves_new_datapoints(mock_get, mock_post, mock_patch, mock_translate, mock_input):
    llm_config = {"provider": "openai", "model": "gpt-5.2", "api_key": "test_key"}

    mock_get_resp = MagicMock()
    mock_get_resp.status_code = 200
    mock_get_resp.json.return_value = {"rules": [], "datapoint_definitions": []}
    mock_get.return_value = mock_get_resp

    mock_translate.return_value = {
        "datapoints": ["new_dp"],
        "edge_cases": [],
        "edge_cases_json": [],
        "rule_logic": "IF new_dp > 50 THEN REJECT",
        "rule_logic_json": {"if": [{">": [{"var": "new_dp"}, 50]}, "REJECT", "APPROVE"]}
    }

    mock_post_resp = MagicMock()
    mock_post_resp.status_code = 201
    mock_post_resp.json.return_value = {
        "id": "rule_new", "name": "New Rule",
        "rule_logic": "IF new_dp > 50 THEN REJECT", "edge_cases": [],
        "rule_logic_json": {}, "edge_cases_json": [],
    }
    mock_post.return_value = mock_post_resp

    mock_patch_resp = MagicMock()
    mock_patch_resp.status_code = 200
    mock_patch.return_value = mock_patch_resp

    rule = prompt_rule_creation("group_123", llm_config=llm_config)
    assert rule["id"] == "rule_new"

    # Verify PATCH was called to save the new datapoint definition
    mock_patch.assert_called_once()
    patch_args, patch_kwargs = mock_patch.call_args
    assert "datapoints" in str(patch_args[0])
    saved_defs = patch_kwargs["json"]
    assert len(saved_defs) == 1
    assert saved_defs[0]["name"] == "new_dp"
    assert saved_defs[0]["type"] == "number"


@patch("builtins.input", side_effect=["EUR", "Test purchase"])
@patch("httpx.Client.get")
def test_prompt_auto_test_enum_aware(mock_get, mock_input):
    """Enum-typed values must be kept as strings (not coerced to int/float)."""
    group_resp = MagicMock()
    group_resp.status_code = 200
    group_resp.json.return_value = {
        "datapoint_definitions": [
            {"name": "currency", "type": "enum", "values": ["EUR", "USD", "GBP"]}
        ]
    }
    decide_resp = MagicMock()
    decide_resp.status_code = 200
    decide_resp.json.return_value = {
        "outcome": "APPROVE", "matched_rules": [],
        "request_id": "req_1", "matched_details": []
    }
    mock_get.side_effect = [group_resp, decide_resp]

    rule = {"name": "Currency Rule", "datapoints": ["currency"]}
    prompt_auto_test("group_123", rule)

    # The context sent to the decide endpoint must contain currency as string "EUR"
    decide_call_args = mock_get.call_args_list[1]
    url = str(decide_call_args[0][0])
    import urllib.parse, json as _json
    parsed = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    context = _json.loads(parsed["context"][0])
    assert context["currency"] == "EUR"
    assert isinstance(context["currency"], str)

