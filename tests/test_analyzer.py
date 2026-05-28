from agent_debugger.analysis.analyzer import TraceAnalyzer
from agent_debugger.core.schema import AgentTrace, Iteration, TokenUsage, ToolCall


def test_total_tokens():
    trace = AgentTrace(
        iterations=[
            Iteration(index=0, token_usage=TokenUsage(total_tokens=100)),
            Iteration(index=1, token_usage=TokenUsage(total_tokens=200)),
        ],
    )
    analyzer = TraceAnalyzer(trace)
    assert analyzer.total_tokens == 300


def test_total_iterations():
    trace = AgentTrace(
        iterations=[Iteration(index=0), Iteration(index=1), Iteration(index=2)],
    )
    analyzer = TraceAnalyzer(trace)
    assert analyzer.total_iterations == 3


def test_tool_call_counts():
    trace = AgentTrace(
        iterations=[
            Iteration(
                index=0,
                tool_calls=[ToolCall(name="read_file"), ToolCall(name="edit_file")],
            ),
            Iteration(
                index=1,
                tool_calls=[ToolCall(name="read_file")],
            ),
        ],
    )
    analyzer = TraceAnalyzer(trace)
    assert analyzer.tool_call_counts == {"read_file": 2, "edit_file": 1}


def test_has_errors_false():
    trace = AgentTrace(iterations=[Iteration(index=0)])
    assert not TraceAnalyzer(trace).has_errors


def test_has_errors_true():
    trace = AgentTrace(
        iterations=[Iteration(index=0, error="Something went wrong")],
    )
    assert TraceAnalyzer(trace).has_errors


def test_empty_trace():
    trace = AgentTrace()
    analyzer = TraceAnalyzer(trace)
    assert analyzer.total_tokens == 0
    assert analyzer.total_iterations == 0
    assert analyzer.tool_call_counts == {}
    assert not analyzer.has_errors
