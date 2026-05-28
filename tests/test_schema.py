from pathlib import Path

from agent_debugger.loader import load_trace
from agent_debugger.schema import AgentTrace, Iteration, TokenUsage, ToolCall

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"


def test_tool_call_model():
    tc = ToolCall(name="read_file", arguments={"path": "foo.txt"}, result="hello")
    assert tc.name == "read_file"
    assert tc.arguments == {"path": "foo.txt"}


def test_iteration_defaults():
    it = Iteration(index=0)
    assert it.think is None
    assert it.tool_calls == []
    assert it.token_usage.total_tokens == 0


def test_agent_trace_properties():
    trace = AgentTrace(
        agent_name="test",
        model="test-model",
        iterations=[
            Iteration(
                index=0,
                tool_calls=[ToolCall(name="read_file"), ToolCall(name="edit_file")],
                token_usage=TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150),
            ),
            Iteration(
                index=1,
                tool_calls=[ToolCall(name="read_file")],
                token_usage=TokenUsage(prompt_tokens=200, completion_tokens=80, total_tokens=280),
            ),
        ],
    )
    assert trace.total_iterations == 2
    assert trace.total_tokens == 430
    assert trace.tool_call_counts == {"read_file": 2, "edit_file": 1}
    assert not trace.has_errors


def test_agent_trace_with_error():
    trace = AgentTrace(
        iterations=[Iteration(index=0, error="Something went wrong")],
    )
    assert trace.has_errors


def test_load_sample_trace():
    trace = load_trace(EXAMPLES_DIR / "sample_trace.json")
    assert isinstance(trace, AgentTrace)
    assert trace.agent_name == "coding-assistant"
    assert trace.total_iterations == 3
    assert trace.total_tokens == 6450
    assert "read_file" in trace.tool_call_counts
