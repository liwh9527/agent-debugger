from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from agent_debugger.ui.cli import main

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"
SAMPLE_TRACE = str(EXAMPLES_DIR / "sample_trace.json")
SAMPLE_CLAUDE_CODE = str(EXAMPLES_DIR / "sample_claude_code.jsonl")


SAMPLE_LANGGRAPH = str(EXAMPLES_DIR / "sample_langgraph_trace.json")


class TestTimelineCommand:
    def test_basic_output(self):
        runner = CliRunner()
        result = runner.invoke(main, ["timeline", SAMPLE_TRACE])
        assert result.exit_code == 0
        assert "Iteration 0" in result.output
        assert "Iteration 1" in result.output
        assert "Iteration 2" in result.output
        assert "read_file" in result.output

    def test_verbose(self):
        runner = CliRunner()
        result = runner.invoke(main, ["timeline", SAMPLE_TRACE, "--verbose"])
        assert result.exit_code == 0
        assert "loclahost" in result.output

    def test_json_format(self):
        runner = CliRunner()
        result = runner.invoke(main, ["timeline", SAMPLE_TRACE, "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 3
        assert data[0]["index"] == 0
        assert data[0]["thinking_preview"].startswith("The user wants")
        assert data[0]["tool_names"] == ["read_file"]

    def test_json_format_verbose(self):
        runner = CliRunner()
        result = runner.invoke(
            main, ["timeline", SAMPLE_TRACE, "--verbose", "--format", "json"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data[0]["think"] is not None
        assert data[0]["tool_calls"][0]["result"] is not None

    def test_file_not_found(self):
        runner = CliRunner()
        result = runner.invoke(main, ["timeline", "/nonexistent/file.json"])
        assert result.exit_code != 0

    def test_anomalies_only(self):
        runner = CliRunner()
        result = runner.invoke(
            main, ["timeline", SAMPLE_TRACE, "--anomalies-only", "--format", "json"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        # All returned items should be anomalies
        for item in data:
            assert item.get("is_anomaly") is True


class TestAnalyzeCommand:
    def test_basic_output(self):
        runner = CliRunner()
        result = runner.invoke(main, ["analyze", SAMPLE_TRACE])
        assert result.exit_code == 0
        assert "Context Utilization Trend" in result.output
        assert "Token Efficiency" in result.output
        assert "Cost Estimate" in result.output

    def test_json_format(self):
        runner = CliRunner()
        result = runner.invoke(main, ["analyze", SAMPLE_TRACE, "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "context_utilization" in data
        assert "context_growth_rate" in data
        assert "token_efficiency" in data
        assert "cost_estimate" in data
        assert "anomalies" in data
        assert len(data["context_utilization"]) == 3
        assert len(data["context_growth_rate"]) == 2

    def test_max_context_option(self):
        runner = CliRunner()
        result = runner.invoke(
            main, ["analyze", SAMPLE_TRACE, "--max-context", "100000", "--format", "json"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["context_utilization"][0] == 1200 / 100000

    def test_file_not_found(self):
        runner = CliRunner()
        result = runner.invoke(main, ["analyze", "/nonexistent/file.json"])
        assert result.exit_code != 0

    def test_fail_if_cost_above(self):
        runner = CliRunner()
        # Very low threshold should trigger failure
        result = runner.invoke(
            main, ["analyze", SAMPLE_TRACE, "--fail-if-cost-above", "0.001"]
        )
        assert result.exit_code == 1
        assert "FAIL" in result.output

    def test_fail_if_cost_above_passes(self):
        runner = CliRunner()
        # Very high threshold should pass
        result = runner.invoke(
            main, ["analyze", SAMPLE_TRACE, "--fail-if-cost-above", "100"]
        )
        assert result.exit_code == 0

    def test_fail_if_errors(self):
        runner = CliRunner()
        # sample_trace has no errors, so this should pass
        result = runner.invoke(
            main, ["analyze", SAMPLE_TRACE, "--fail-if-errors"]
        )
        assert result.exit_code == 0

    def test_fail_if_efficiency_below(self):
        runner = CliRunner()
        # Very high threshold should trigger failure
        result = runner.invoke(
            main, ["analyze", SAMPLE_TRACE, "--fail-if-efficiency-below", "1.0"]
        )
        assert result.exit_code == 1
        assert "FAIL" in result.output


class TestInspectCommand:
    def test_basic_output(self):
        runner = CliRunner()
        result = runner.invoke(main, ["inspect", SAMPLE_TRACE, "0"])
        assert result.exit_code == 0
        assert "Iteration 0" in result.output
        assert "Thinking" in result.output
        assert "read_file" in result.output
        assert "1,350" in result.output

    def test_json_format(self):
        runner = CliRunner()
        result = runner.invoke(
            main, ["inspect", SAMPLE_TRACE, "1", "--format", "json"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["index"] == 1
        assert data["think"] is not None
        assert data["tool_calls"][0]["name"] == "edit_file"
        assert data["token_usage"]["prompt_tokens"] == 2100

    def test_invalid_index(self):
        runner = CliRunner()
        result = runner.invoke(main, ["inspect", SAMPLE_TRACE, "99"])
        assert result.exit_code == 1

    def test_file_not_found(self):
        runner = CliRunner()
        result = runner.invoke(main, ["inspect", "/nonexistent/file.json", "0"])
        assert result.exit_code != 0


class TestInfoCommand:
    def test_basic_output(self):
        runner = CliRunner()
        result = runner.invoke(main, ["info", SAMPLE_TRACE])
        assert result.exit_code == 0
        assert "Agent:" in result.output
        assert "Iterations:" in result.output

    def test_json_format(self):
        runner = CliRunner()
        result = runner.invoke(main, ["info", SAMPLE_TRACE, "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "agent_name" in data
        assert "model" in data
        assert "total_iterations" in data
        assert "total_tokens" in data
        assert "tool_call_counts" in data
        assert "start_time" in data
        assert "end_time" in data
        assert "has_errors" in data
        assert "source" in data
        assert isinstance(data["tool_call_counts"], dict)
        assert data["total_iterations"] == 3


class TestDiagnoseCommand:
    def test_basic_output_json(self):
        runner = CliRunner()
        result = runner.invoke(main, ["diagnose", SAMPLE_TRACE, "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "findings" in data
        assert "recommendations" in data
        assert "summary" in data
        assert isinstance(data["findings"], list)
        assert isinstance(data["recommendations"], list)

    def test_basic_output_rich(self):
        runner = CliRunner()
        result = runner.invoke(main, ["diagnose", SAMPLE_TRACE])
        assert result.exit_code == 0
        assert "Diagnostics" in result.output

    def test_diagnose_claude_code_trace(self):
        runner = CliRunner()
        result = runner.invoke(main, ["diagnose", SAMPLE_CLAUDE_CODE])
        assert result.exit_code == 0

    def test_file_not_found(self):
        runner = CliRunner()
        result = runner.invoke(main, ["diagnose", "/nonexistent/file.json"])
        assert result.exit_code != 0


class TestScanCommand:
    def test_json_format_with_mock(self):
        mock_sessions = [
            {
                "path": "/tmp/test.jsonl",
                "file_size": 1024,
                "lines": 10,
                "start_time": "2026-06-01T10:00:00+00:00",
                "end_time": "2026-06-01T10:05:00+00:00",
                "last_modified": "2026-06-01T10:05:00",
                "agent_name": "claude-code",
                "model": "claude-sonnet-4",
                "estimated_tokens": 256,
                "estimated_cost": 0.0015,
            },
        ]
        runner = CliRunner()
        with patch("agent_debugger.ui.cli.scan_sessions", return_value=mock_sessions):
            result = runner.invoke(main, ["scan", "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1
        assert data[0]["agent_name"] == "claude-code"

    def test_rich_format_with_mock(self):
        mock_sessions = [
            {
                "path": "/tmp/test.jsonl",
                "file_size": 1024,
                "lines": 10,
                "start_time": "2026-06-01T10:00:00+00:00",
                "end_time": "2026-06-01T10:05:00+00:00",
                "last_modified": "2026-06-01T10:05:00",
                "agent_name": "claude-code",
                "model": "claude-sonnet-4",
                "estimated_tokens": 256,
                "estimated_cost": 0.0015,
            },
        ]
        runner = CliRunner()
        with patch("agent_debugger.ui.cli.scan_sessions", return_value=mock_sessions):
            result = runner.invoke(main, ["scan"])
        assert result.exit_code == 0
        assert "Claude Code Sessions" in result.output

    def test_empty_scan(self):
        runner = CliRunner()
        with patch("agent_debugger.ui.cli.scan_sessions", return_value=[]):
            result = runner.invoke(main, ["scan"])
        assert result.exit_code == 0
        assert "No Claude Code sessions found" in result.output

    def test_limit_option(self):
        mock_sessions = [
            {
                "path": f"/tmp/test_{i}.jsonl",
                "file_size": 1024,
                "lines": 10,
                "start_time": None,
                "end_time": None,
                "last_modified": f"2026-06-0{i + 1}T10:00:00",
                "agent_name": "claude-code",
                "model": "claude-sonnet-4",
                "estimated_tokens": 256,
                "estimated_cost": 0.001,
            }
            for i in range(5)
        ]
        runner = CliRunner()
        with patch("agent_debugger.ui.cli.scan_sessions", return_value=mock_sessions):
            result = runner.invoke(main, ["scan", "--limit", "2", "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 2


class TestDiffCommand:
    def test_basic_output(self):
        runner = CliRunner()
        result = runner.invoke(main, ["diff", SAMPLE_TRACE, SAMPLE_LANGGRAPH])
        assert result.exit_code == 0
        assert "Diff:" in result.output
        assert "Iterations" in result.output
        assert "Total Tokens" in result.output
        assert "Summary:" in result.output

    def test_json_format(self):
        runner = CliRunner()
        result = runner.invoke(
            main, ["diff", SAMPLE_TRACE, SAMPLE_LANGGRAPH, "--format", "json"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "trace_a_name" in data
        assert "trace_b_name" in data
        assert "iterations_delta" in data
        assert "tokens_delta" in data
        assert "cost_delta" in data
        assert "efficiency_delta" in data
        assert "tools_only_in_a" in data
        assert "tools_only_in_b" in data
        assert "tool_count_changes" in data
        assert "summary" in data

    def test_file_not_found(self):
        runner = CliRunner()
        result = runner.invoke(main, ["diff", "/nonexistent/a.json", SAMPLE_TRACE])
        assert result.exit_code != 0
