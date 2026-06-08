from pathlib import Path

from agent_debugger.adapters.langgraph import LangGraphAdapter
from agent_debugger.core.loader import load_trace
from agent_debugger.core.schema import AgentTrace

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"
SAMPLE_LANGGRAPH = EXAMPLES_DIR / "sample_langgraph_trace.json"
SAMPLE_NATIVE = EXAMPLES_DIR / "sample_trace.json"
SAMPLE_JSONL = EXAMPLES_DIR / "sample_claude_code.jsonl"


def test_detect_accepts_langgraph():
    adapter = LangGraphAdapter()
    assert adapter.detect(SAMPLE_LANGGRAPH)


def test_detect_rejects_native_json():
    adapter = LangGraphAdapter()
    assert not adapter.detect(SAMPLE_NATIVE)


def test_detect_rejects_jsonl():
    adapter = LangGraphAdapter()
    assert not adapter.detect(SAMPLE_JSONL)


def test_detect_rejects_nonexistent(tmp_path):
    adapter = LangGraphAdapter()
    assert not adapter.detect(tmp_path / "nope.json")


def test_load_returns_agent_trace():
    adapter = LangGraphAdapter()
    trace = adapter.load(SAMPLE_LANGGRAPH)
    assert isinstance(trace, AgentTrace)


def test_load_agent_name():
    adapter = LangGraphAdapter()
    trace = adapter.load(SAMPLE_LANGGRAPH)
    assert trace.agent_name == "agent"


def test_load_model():
    adapter = LangGraphAdapter()
    trace = adapter.load(SAMPLE_LANGGRAPH)
    assert trace.model == "gpt-4o"


def test_load_iterations():
    adapter = LangGraphAdapter()
    trace = adapter.load(SAMPLE_LANGGRAPH)
    assert len(trace.iterations) == 3


def test_load_tool_calls():
    adapter = LangGraphAdapter()
    trace = adapter.load(SAMPLE_LANGGRAPH)
    all_tools = []
    for it in trace.iterations:
        all_tools.extend(tc.name for tc in it.tool_calls)
    assert "tavily_search" in all_tools
    assert "calculator" in all_tools


def test_load_tool_call_results():
    adapter = LangGraphAdapter()
    trace = adapter.load(SAMPLE_LANGGRAPH)
    for it in trace.iterations:
        for tc in it.tool_calls:
            assert tc.result is not None


def test_load_tool_call_duration():
    adapter = LangGraphAdapter()
    trace = adapter.load(SAMPLE_LANGGRAPH)
    for it in trace.iterations:
        for tc in it.tool_calls:
            assert tc.duration_ms is not None
            assert tc.duration_ms > 0


def test_load_token_usage():
    adapter = LangGraphAdapter()
    trace = adapter.load(SAMPLE_LANGGRAPH)
    total = sum(it.token_usage.total_tokens for it in trace.iterations)
    assert total > 0


def test_load_token_usage_per_iteration():
    adapter = LangGraphAdapter()
    trace = adapter.load(SAMPLE_LANGGRAPH)
    assert trace.iterations[0].token_usage.prompt_tokens == 185
    assert trace.iterations[0].token_usage.completion_tokens == 62
    assert trace.iterations[0].token_usage.total_tokens == 247


def test_load_timestamps():
    adapter = LangGraphAdapter()
    trace = adapter.load(SAMPLE_LANGGRAPH)
    assert trace.start_time is not None
    assert trace.end_time is not None
    assert trace.end_time >= trace.start_time


def test_load_metadata_source():
    adapter = LangGraphAdapter()
    trace = adapter.load(SAMPLE_LANGGRAPH)
    assert trace.metadata["source"] == "langgraph"


def test_load_thinking_content():
    adapter = LangGraphAdapter()
    trace = adapter.load(SAMPLE_LANGGRAPH)
    assert trace.iterations[2].think is not None
    assert "population" in trace.iterations[2].think.lower()


def test_load_trace_auto_detects_langgraph():
    trace = load_trace(SAMPLE_LANGGRAPH)
    assert isinstance(trace, AgentTrace)
    assert trace.agent_name == "agent"
    assert trace.metadata["source"] == "langgraph"


def test_load_trace_native_json_still_works():
    trace = load_trace(SAMPLE_NATIVE)
    assert isinstance(trace, AgentTrace)
    assert trace.agent_name == "coding-assistant"
