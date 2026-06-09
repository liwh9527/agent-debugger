from __future__ import annotations

from agent_debugger.analysis.diff import compare_traces
from agent_debugger.core.schema import AgentTrace, Iteration, TokenUsage, ToolCall


def _make_trace_a() -> AgentTrace:
    return AgentTrace(
        agent_name="trace-a",
        model="model-a",
        iterations=[
            Iteration(
                index=0,
                token_usage=TokenUsage(
                    prompt_tokens=1000, completion_tokens=100, total_tokens=1100
                ),
                tool_calls=[ToolCall(name="read_file"), ToolCall(name="edit_file")],
            ),
            Iteration(
                index=1,
                token_usage=TokenUsage(
                    prompt_tokens=2000, completion_tokens=150, total_tokens=2150
                ),
                tool_calls=[ToolCall(name="read_file")],
            ),
        ],
    )


def _make_trace_b() -> AgentTrace:
    return AgentTrace(
        agent_name="trace-b",
        model="model-b",
        iterations=[
            Iteration(
                index=0,
                token_usage=TokenUsage(
                    prompt_tokens=1500, completion_tokens=200, total_tokens=1700
                ),
                tool_calls=[ToolCall(name="read_file"), ToolCall(name="bash")],
            ),
            Iteration(
                index=1,
                token_usage=TokenUsage(
                    prompt_tokens=2500, completion_tokens=300, total_tokens=2800
                ),
                tool_calls=[ToolCall(name="read_file"), ToolCall(name="bash")],
            ),
            Iteration(
                index=2,
                token_usage=TokenUsage(
                    prompt_tokens=3000, completion_tokens=250, total_tokens=3250
                ),
                tool_calls=[ToolCall(name="read_file")],
            ),
        ],
    )


class TestComparTraces:
    def test_iterations_delta(self):
        result = compare_traces(_make_trace_a(), _make_trace_b())
        assert result.iterations_delta == 1  # 3 - 2

    def test_tokens_delta(self):
        result = compare_traces(_make_trace_a(), _make_trace_b())
        tokens_a = 1100 + 2150
        tokens_b = 1700 + 2800 + 3250
        assert result.tokens_delta == tokens_b - tokens_a

    def test_cost_delta(self):
        result = compare_traces(_make_trace_a(), _make_trace_b())
        # cost_delta should be positive since trace_b uses more tokens
        assert result.cost_delta > 0

    def test_efficiency_delta(self):
        result = compare_traces(_make_trace_a(), _make_trace_b())
        # trace_a efficiency: 250 / 3000
        # trace_b efficiency: 750 / 7000
        eff_a = 250 / 3000
        eff_b = 750 / 7000
        assert abs(result.efficiency_delta - (eff_b - eff_a)) < 1e-9

    def test_tools_only_in_a(self):
        result = compare_traces(_make_trace_a(), _make_trace_b())
        assert result.tools_only_in_a == ["edit_file"]

    def test_tools_only_in_b(self):
        result = compare_traces(_make_trace_a(), _make_trace_b())
        assert result.tools_only_in_b == ["bash"]

    def test_tool_count_changes(self):
        result = compare_traces(_make_trace_a(), _make_trace_b())
        assert result.tool_count_changes["read_file"] == (2, 3)
        assert result.tool_count_changes["edit_file"] == (1, 0)
        assert result.tool_count_changes["bash"] == (0, 2)

    def test_summary_is_nonempty(self):
        result = compare_traces(_make_trace_a(), _make_trace_b())
        assert len(result.summary) > 0

    def test_summary_mentions_tokens(self):
        result = compare_traces(_make_trace_a(), _make_trace_b())
        assert "token" in result.summary.lower()

    def test_names(self):
        result = compare_traces(_make_trace_a(), _make_trace_b())
        assert result.trace_a_name == "trace-a"
        assert result.trace_b_name == "trace-b"


class TestIdenticalTraces:
    def test_identical_traces(self):
        trace = _make_trace_a()
        result = compare_traces(trace, trace)
        assert result.iterations_delta == 0
        assert result.tokens_delta == 0
        assert result.cost_delta == 0.0
        assert result.efficiency_delta == 0.0
        assert result.tools_only_in_a == []
        assert result.tools_only_in_b == []


class TestEmptyTraces:
    def test_empty_traces(self):
        trace = AgentTrace()
        result = compare_traces(trace, trace)
        assert result.iterations_delta == 0
        assert result.tokens_delta == 0
        assert result.summary == "Traces are identical."
