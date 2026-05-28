# Agent Debugger

Interactive debugger for AI Agent loops — timeline visualization, context window analysis, breakpoints & replay.

## Why?

Existing LLM observability tools (LangSmith, Langfuse, etc.) track **individual LLM calls**. But when debugging an AI Agent, the real question is:

> *"At which iteration did the Agent go off track, and why?"*

Agent Debugger operates at the **Agent Loop iteration level** — showing you what the Agent was thinking, which tools it called, how the context window filled up, and where things went wrong.

## Install

```bash
pip install agent-debugger
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
uv add agent-debugger
```

## Quick Start

```bash
# View summary of an Agent trace
agent-debugger info examples/sample_trace.json
```

Output:
```
Agent: coding-assistant
Model: claude-sonnet-4-6
Iterations: 3
Total Tokens: 6,450

       Tool Calls
┌───────────┬───────┐
│ Tool      │ Count │
├───────────┼───────┤
│ read_file │   2   │
│ edit_file │   1   │
└───────────┴───────┘
```

## AgentTrace Schema

Agent Debugger uses a simple JSON format to describe Agent loop executions:

```json
{
  "agent_name": "my-agent",
  "model": "claude-sonnet-4-6",
  "iterations": [
    {
      "index": 0,
      "think": "I need to read the config file...",
      "tool_calls": [
        {
          "name": "read_file",
          "arguments": {"path": "config.yaml"},
          "result": "...",
          "duration_ms": 50
        }
      ],
      "observation": "Found the config file.",
      "token_usage": {
        "prompt_tokens": 1200,
        "completion_tokens": 150,
        "total_tokens": 1350
      }
    }
  ]
}
```

Any Agent framework can export traces in this format. See `examples/sample_trace.json` for a complete example.

## Development

```bash
# Clone and install
git clone https://github.com/liwh9527/agent-debugger.git
cd agent-debugger
uv sync --extra dev

# Run tests
uv run pytest

# Run linter
uv run ruff check src/
```

## Roadmap

- [x] AgentTrace JSON schema (Pydantic models)
- [x] CLI with `info` command
- [ ] Terminal UI (TUI) with iteration timeline
- [ ] Context window usage visualization
- [ ] Breakpoints & replay
- [ ] Framework adapters (Claude Code, LangGraph, CrewAI)
- [ ] Trace comparison (diff two runs)

## License

MIT
