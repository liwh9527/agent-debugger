from pathlib import Path

from click.testing import CliRunner

from agent_debugger.ui.cli import main

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"


def test_info_command():
    runner = CliRunner()
    result = runner.invoke(main, ["info", str(EXAMPLES_DIR / "sample_trace.json")])
    assert result.exit_code == 0
    assert "coding-assistant" in result.output
    assert "3" in result.output
    assert "6,450" in result.output


def test_info_file_not_found():
    runner = CliRunner()
    result = runner.invoke(main, ["info", "/nonexistent/file.json"])
    assert result.exit_code != 0


def test_version():
    from agent_debugger import __version__
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output
