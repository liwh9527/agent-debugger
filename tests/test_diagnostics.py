"""Tests for the diagnostic engine."""

from __future__ import annotations

from agent_debugger.analysis.analyzer import TraceAnalyzer
from agent_debugger.analysis.diagnostics import DiagnosticEngine
from agent_debugger.core.schema import (
    AgentTrace,
    Iteration,
    TokenUsage,
    ToolCall,
)


def _make_trace(iterations: list[Iteration], **kwargs) -> AgentTrace:
    """Helper to build an AgentTrace with given iterations."""
    return AgentTrace(
        agent_name=kwargs.get("agent_name", "test-agent"),
        model=kwargs.get("model", "test-model"),
        iterations=iterations,
    )


def _tokens(prompt: int, completion: int) -> TokenUsage:
    """Shorthand to build TokenUsage."""
    return TokenUsage(
        prompt_tokens=prompt,
        completion_tokens=completion,
        total_tokens=prompt + completion,
    )


class TestDiagnosticEngineNormal:
    """Test with a normal trace that should produce no findings."""

    def test_no_findings_for_healthy_trace(self) -> None:
        iterations = [
            Iteration(
                index=i,
                tool_calls=[ToolCall(name=f"tool_{i}", arguments={"x": i})],
                token_usage=TokenUsage(
                    prompt_tokens=1000 + i * 100,
                    completion_tokens=100 + i * 10,
                    total_tokens=1100 + i * 110,
                ),
            )
            for i in range(15)
        ]
        trace = _make_trace(iterations)
        analyzer = TraceAnalyzer(trace)
        engine = DiagnosticEngine(trace, analyzer)
        report = engine.run()

        # With 15 iterations of similar size and different tools, no findings expected
        assert len(report.findings) == 0
        assert report.summary == "No issues detected — session looks healthy."

    def test_report_has_empty_recommendations_when_clean(self) -> None:
        iterations = [
            Iteration(
                index=0,
                tool_calls=[ToolCall(name="read_file", arguments={"path": "a.py"})],
                token_usage=TokenUsage(prompt_tokens=500, completion_tokens=100, total_tokens=600),
            ),
        ]
        trace = _make_trace(iterations)
        analyzer = TraceAnalyzer(trace)
        engine = DiagnosticEngine(trace, analyzer)
        report = engine.run()

        assert report.recommendations == []


class TestContextPressure:
    def test_detects_high_utilization(self) -> None:
        # Create iterations with high prompt_tokens relative to default 200k context
        iterations = [
            Iteration(
                index=i,
                token_usage=TokenUsage(
                    prompt_tokens=170000,  # 85% of 200k
                    completion_tokens=1000,
                    total_tokens=171000,
                ),
            )
            for i in range(3)
        ]
        trace = _make_trace(iterations)
        analyzer = TraceAnalyzer(trace)
        engine = DiagnosticEngine(trace, analyzer)
        report = engine.run()

        context_findings = [
            f for f in report.findings if f.category == "context_pressure"
        ]
        assert len(context_findings) >= 1
        assert any("85%" in f.message for f in context_findings)

    def test_detects_compaction_event(self) -> None:
        # Utilization drops significantly between iterations
        iterations = [
            Iteration(
                index=0,
                token_usage=_tokens(180000, 1000),
            ),
            Iteration(
                index=1,
                token_usage=_tokens(80000, 1000),
            ),
        ]
        trace = _make_trace(iterations)
        analyzer = TraceAnalyzer(trace)
        engine = DiagnosticEngine(trace, analyzer)
        report = engine.run()

        compaction_findings = [
            f for f in report.findings
            if f.category == "context_pressure" and "compaction" in f.message.lower()
        ]
        assert len(compaction_findings) >= 1


class TestRetryLoops:
    def test_detects_three_consecutive_same_tool(self) -> None:
        iterations = [
            Iteration(
                index=i,
                tool_calls=[ToolCall(name="read_file", arguments={"path": "a.py"})],
                token_usage=_tokens(1000, 100),
            )
            for i in range(5)
        ]
        trace = _make_trace(iterations)
        analyzer = TraceAnalyzer(trace)
        engine = DiagnosticEngine(trace, analyzer)
        report = engine.run()

        retry_findings = [f for f in report.findings if f.category == "retry_loop"]
        assert len(retry_findings) >= 1
        assert "read_file" in retry_findings[0].message
        assert "5" in retry_findings[0].message

    def test_no_retry_loop_with_different_tools(self) -> None:
        iterations = [
            Iteration(
                index=i,
                tool_calls=[ToolCall(name=f"tool_{i}", arguments={})],
                token_usage=_tokens(1000, 100),
            )
            for i in range(5)
        ]
        trace = _make_trace(iterations)
        analyzer = TraceAnalyzer(trace)
        engine = DiagnosticEngine(trace, analyzer)
        report = engine.run()

        retry_findings = [f for f in report.findings if f.category == "retry_loop"]
        assert len(retry_findings) == 0

    def test_no_retry_with_only_two_consecutive(self) -> None:
        iterations = [
            Iteration(
                index=0,
                tool_calls=[ToolCall(name="read_file", arguments={})],
                token_usage=_tokens(1000, 100),
            ),
            Iteration(
                index=1,
                tool_calls=[ToolCall(name="read_file", arguments={})],
                token_usage=_tokens(1000, 100),
            ),
            Iteration(
                index=2,
                tool_calls=[ToolCall(name="edit_file", arguments={})],
                token_usage=_tokens(1000, 100),
            ),
        ]
        trace = _make_trace(iterations)
        analyzer = TraceAnalyzer(trace)
        engine = DiagnosticEngine(trace, analyzer)
        report = engine.run()

        retry_findings = [f for f in report.findings if f.category == "retry_loop"]
        assert len(retry_findings) == 0


class TestCostHotspot:
    def test_detects_cost_hotspot(self) -> None:
        # One iteration has > 10% of total tokens, and we have > 3 iterations
        iterations = [
            Iteration(
                index=0,
                token_usage=_tokens(50000, 5000),
            ),
        ] + [
            Iteration(
                index=i,
                token_usage=_tokens(1000, 100),
            )
            for i in range(1, 5)
        ]
        trace = _make_trace(iterations)
        analyzer = TraceAnalyzer(trace)
        engine = DiagnosticEngine(trace, analyzer)
        report = engine.run()

        hotspot_findings = [f for f in report.findings if f.category == "cost_hotspot"]
        assert len(hotspot_findings) >= 1
        assert hotspot_findings[0].iteration == 0


class TestRecommendations:
    def test_retry_loop_generates_recommendation(self) -> None:
        iterations = [
            Iteration(
                index=i,
                tool_calls=[ToolCall(name="failing_tool", arguments={})],
                token_usage=_tokens(1000, 100),
            )
            for i in range(4)
        ]
        trace = _make_trace(iterations)
        analyzer = TraceAnalyzer(trace)
        engine = DiagnosticEngine(trace, analyzer)
        report = engine.run()

        assert len(report.recommendations) >= 1
        assert any("failing_tool" in r.message for r in report.recommendations)

    def test_low_efficiency_generates_recommendation(self) -> None:
        # Very low efficiency: high prompt, tiny completion
        iterations = [
            Iteration(
                index=i,
                token_usage=TokenUsage(
                    prompt_tokens=100000,
                    completion_tokens=100,
                    total_tokens=100100,
                ),
            )
            for i in range(3)
        ]
        trace = _make_trace(iterations)
        analyzer = TraceAnalyzer(trace)
        engine = DiagnosticEngine(trace, analyzer)
        report = engine.run()

        eff_recs = [r for r in report.recommendations if "efficiency" in r.message.lower()]
        assert len(eff_recs) >= 1

    def test_recommendations_sorted_by_priority(self) -> None:
        # Trigger both retry loop (priority 2) and efficiency (priority 3)
        iterations = [
            Iteration(
                index=i,
                tool_calls=[ToolCall(name="bad_tool", arguments={})],
                token_usage=TokenUsage(
                    prompt_tokens=100000,
                    completion_tokens=50,
                    total_tokens=100050,
                ),
            )
            for i in range(4)
        ]
        trace = _make_trace(iterations)
        analyzer = TraceAnalyzer(trace)
        engine = DiagnosticEngine(trace, analyzer)
        report = engine.run()

        if len(report.recommendations) >= 2:
            for i in range(len(report.recommendations) - 1):
                assert report.recommendations[i].priority <= report.recommendations[i + 1].priority


class TestErrorDetection:
    def test_detects_errors(self) -> None:
        iterations = [
            Iteration(
                index=0,
                token_usage=_tokens(1000, 100),
                error="Tool execution failed",
            ),
            Iteration(
                index=1,
                token_usage=_tokens(1000, 100),
            ),
        ]
        trace = _make_trace(iterations)
        analyzer = TraceAnalyzer(trace)
        engine = DiagnosticEngine(trace, analyzer)
        report = engine.run()

        error_findings = [f for f in report.findings if f.category == "error"]
        assert len(error_findings) == 1
        assert error_findings[0].severity == "critical"
        assert error_findings[0].iteration == 0


class TestDiagnosticSummary:
    def test_summary_includes_counts(self) -> None:
        iterations = [
            Iteration(
                index=0,
                token_usage=_tokens(1000, 100),
                error="fail",
            ),
        ]
        trace = _make_trace(iterations)
        analyzer = TraceAnalyzer(trace)
        engine = DiagnosticEngine(trace, analyzer)
        report = engine.run()

        assert "critical" in report.summary.lower() or "1" in report.summary
