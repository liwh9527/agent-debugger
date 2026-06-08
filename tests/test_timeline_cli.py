from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from agent_debugger.ui.cli import main

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"
SAMPLE_TRACE = str(EXAMPLES_DIR / "sample_trace.json")


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
