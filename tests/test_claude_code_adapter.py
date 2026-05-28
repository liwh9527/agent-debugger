from pathlib import Path

from agent_debugger.adapters.claude_code import ClaudeCodeAdapter
from agent_debugger.core.loader import load_trace
from agent_debugger.core.schema import AgentTrace

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"
SAMPLE_JSONL = EXAMPLES_DIR / "sample_claude_code.jsonl"


def test_detect_jsonl():
    adapter = ClaudeCodeAdapter()
    assert adapter.detect(SAMPLE_JSONL)


def test_detect_rejects_json():
    adapter = ClaudeCodeAdapter()
    assert not adapter.detect(EXAMPLES_DIR / "sample_trace.json")


def test_detect_rejects_nonexistent(tmp_path):
    adapter = ClaudeCodeAdapter()
    assert not adapter.detect(tmp_path / "nope.jsonl")


def test_load_returns_agent_trace():
    adapter = ClaudeCodeAdapter()
    trace = adapter.load(SAMPLE_JSONL)
    assert isinstance(trace, AgentTrace)


def test_load_agent_name():
    adapter = ClaudeCodeAdapter()
    trace = adapter.load(SAMPLE_JSONL)
    assert trace.agent_name == "claude-code"


def test_load_model():
    adapter = ClaudeCodeAdapter()
    trace = adapter.load(SAMPLE_JSONL)
    assert "claude" in trace.model.lower() or "sonnet" in trace.model.lower()


def test_load_iterations():
    adapter = ClaudeCodeAdapter()
    trace = adapter.load(SAMPLE_JSONL)
    assert len(trace.iterations) >= 2


def test_load_tool_calls():
    adapter = ClaudeCodeAdapter()
    trace = adapter.load(SAMPLE_JSONL)
    all_tools = []
    for it in trace.iterations:
        all_tools.extend(tc.name for tc in it.tool_calls)
    assert "Read" in all_tools
    assert "Edit" in all_tools


def test_load_tool_results_matched():
    adapter = ClaudeCodeAdapter()
    trace = adapter.load(SAMPLE_JSONL)
    for it in trace.iterations:
        for tc in it.tool_calls:
            assert tc.result is not None


def test_load_thinking():
    adapter = ClaudeCodeAdapter()
    trace = adapter.load(SAMPLE_JSONL)
    has_thinking = any(it.think is not None for it in trace.iterations)
    assert has_thinking


def test_load_token_usage():
    adapter = ClaudeCodeAdapter()
    trace = adapter.load(SAMPLE_JSONL)
    total = sum(it.token_usage.total_tokens for it in trace.iterations)
    assert total > 0


def test_load_timestamps():
    adapter = ClaudeCodeAdapter()
    trace = adapter.load(SAMPLE_JSONL)
    assert trace.start_time is not None
    assert trace.end_time is not None
    assert trace.end_time >= trace.start_time


def test_load_metadata_source():
    adapter = ClaudeCodeAdapter()
    trace = adapter.load(SAMPLE_JSONL)
    assert trace.metadata["source"] == "claude_code"


def test_load_trace_auto_detects_jsonl():
    trace = load_trace(SAMPLE_JSONL)
    assert isinstance(trace, AgentTrace)
    assert trace.agent_name == "claude-code"


def test_load_trace_json_still_works():
    trace = load_trace(EXAMPLES_DIR / "sample_trace.json")
    assert isinstance(trace, AgentTrace)
    assert trace.agent_name == "coding-assistant"
