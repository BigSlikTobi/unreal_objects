"""Tests for the Tool Agent AST-based code validation."""

from mcp_server.tool_agent import _validate_generated_code, _validate_tool_parameters


# --- _validate_generated_code ---

def test_valid_guarded_function():
    code = '''
async def guarded_send_email(
    recipient: str,
    subject: str,
    request_description: str,
    ctx: Context = None,
):
    """Send an email. Evaluated against business rules before execution."""
    if ctx:
        await ctx.info(f"guarded_send_email: {request_description}")
    return {"outcome": "APPROVE", "result": "sent"}
'''
    ok, reason = _validate_generated_code(code)
    assert ok, reason


def test_rejects_os_import():
    code = '''
async def guarded_bad(request_description: str):
    import os
    os.system("rm -rf /")
    return {}
'''
    ok, reason = _validate_generated_code(code)
    assert not ok
    assert "os" in reason


def test_rejects_subprocess_import():
    code = '''
async def guarded_bad(request_description: str):
    import subprocess
    return {}
'''
    ok, reason = _validate_generated_code(code)
    assert not ok
    assert "subprocess" in reason


def test_rejects_from_import():
    code = '''
async def guarded_bad(request_description: str):
    from shutil import rmtree
    return {}
'''
    ok, reason = _validate_generated_code(code)
    assert not ok
    assert "shutil" in reason


def test_rejects_eval_call():
    code = '''
async def guarded_bad(request_description: str):
    return eval("1+1")
'''
    ok, reason = _validate_generated_code(code)
    assert not ok
    assert "eval" in reason


def test_rejects_exec_call():
    code = '''
async def guarded_bad(request_description: str):
    exec("print('hi')")
    return {}
'''
    ok, reason = _validate_generated_code(code)
    assert not ok
    assert "exec" in reason


def test_rejects_open_call():
    code = '''
async def guarded_bad(request_description: str):
    f = open("/etc/passwd")
    return {}
'''
    ok, reason = _validate_generated_code(code)
    assert not ok
    assert "open" in reason


def test_rejects_builtins_reference():
    code = '''
async def guarded_bad(request_description: str):
    return __builtins__
'''
    ok, reason = _validate_generated_code(code)
    assert not ok
    assert "__builtins__" in reason


def test_rejects_builtins_subscript_import():
    code = '''
async def guarded_bad(request_description: str):
    __builtins__["__import__"]("os")
    return {}
'''
    ok, reason = _validate_generated_code(code)
    assert not ok
    assert "__import__" in reason


def test_rejects_dunder_access():
    code = '''
async def guarded_bad(request_description: str):
    x = request_description.__class__.__mro__
    return {}
'''
    ok, reason = _validate_generated_code(code)
    assert not ok
    assert "blocked" in reason.lower()


def test_rejects_non_guarded_function_name():
    code = '''
async def evil_tool(request_description: str):
    return {}
'''
    ok, reason = _validate_generated_code(code)
    assert not ok
    assert "guarded_" in reason


def test_rejects_top_level_assignment():
    code = '''
x = 1

async def guarded_ok(request_description: str):
    return {}
'''
    ok, reason = _validate_generated_code(code)
    assert not ok
    assert "top-level" in reason.lower()


def test_rejects_syntax_error():
    code = "def guarded_bad(:\n    return"
    ok, reason = _validate_generated_code(code)
    assert not ok
    assert "syntax" in reason.lower()


# --- _validate_tool_parameters ---

def test_valid_parameters():
    params = [
        {"name": "recipient", "type": "str"},
        {"name": "amount", "type": "float"},
    ]
    ok, reason = _validate_tool_parameters(params)
    assert ok, reason


def test_rejects_keyword_parameter():
    params = [{"name": "class", "type": "str"}]
    ok, reason = _validate_tool_parameters(params)
    assert not ok
    assert "class" in reason


def test_rejects_invalid_identifier():
    params = [{"name": "my-param", "type": "str"}]
    ok, reason = _validate_tool_parameters(params)
    assert not ok


def test_rejects_invalid_type():
    params = [{"name": "x", "type": "os.path"}]
    ok, reason = _validate_tool_parameters(params)
    assert not ok
    assert "type" in reason.lower()
