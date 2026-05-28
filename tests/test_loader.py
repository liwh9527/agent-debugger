from pathlib import Path

import pytest
from pydantic import ValidationError

from agent_debugger.core.loader import load_trace
from agent_debugger.core.schema import AgentTrace

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"


def test_load_sample_trace():
    trace = load_trace(EXAMPLES_DIR / "sample_trace.json")
    assert isinstance(trace, AgentTrace)
    assert trace.agent_name == "coding-assistant"
    assert len(trace.iterations) == 3


def test_load_file_not_found():
    with pytest.raises(FileNotFoundError, match="not found"):
        load_trace("/nonexistent/path.json")


def test_load_wrong_extension(tmp_path):
    txt_file = tmp_path / "trace.txt"
    txt_file.write_text("{}")
    with pytest.raises(ValueError, match="Expected .json"):
        load_trace(txt_file)


def test_load_invalid_json(tmp_path):
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("not json at all")
    with pytest.raises(Exception):
        load_trace(bad_file)


def test_load_schema_mismatch(tmp_path):
    bad_schema = tmp_path / "bad_schema.json"
    bad_schema.write_text('{"iterations": [{"index": "not_a_number"}]}')
    with pytest.raises(ValidationError):
        load_trace(bad_schema)
