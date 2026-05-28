from agent_debugger.core.schema import (
    AgentTrace,
    ContextWindow,
    Iteration,
    TokenUsage,
    ToolCall,
)


def test_tool_call_model():
    tc = ToolCall(name="read_file", arguments={"path": "foo.txt"}, result="hello")
    assert tc.name == "read_file"
    assert tc.arguments == {"path": "foo.txt"}


def test_tool_call_result_dict():
    tc = ToolCall(name="api_call", result={"status": 200, "body": "ok"})
    assert isinstance(tc.result, dict)
    assert tc.result["status"] == 200


def test_token_usage_defaults():
    tu = TokenUsage()
    assert tu.prompt_tokens == 0
    assert tu.total_tokens == 0


def test_context_window():
    cw = ContextWindow(used_tokens=80000, max_tokens=128000)
    assert cw.used_tokens == 80000
    assert cw.max_tokens == 128000


def test_context_window_defaults():
    cw = ContextWindow()
    assert cw.used_tokens == 0
    assert cw.max_tokens is None


def test_iteration_defaults():
    it = Iteration(index=0)
    assert it.think is None
    assert it.tool_calls == []
    assert it.token_usage.total_tokens == 0
    assert it.context_window is None


def test_iteration_with_context_window():
    it = Iteration(
        index=0,
        context_window=ContextWindow(used_tokens=5000, max_tokens=128000),
    )
    assert it.context_window is not None
    assert it.context_window.used_tokens == 5000


def test_agent_trace_defaults():
    trace = AgentTrace()
    assert trace.agent_name == "unknown"
    assert trace.model == "unknown"
    assert trace.iterations == []
