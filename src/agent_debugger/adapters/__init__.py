from agent_debugger.adapters.base import BaseAdapter
from agent_debugger.adapters.claude_code import ClaudeCodeAdapter
from agent_debugger.adapters.langgraph import LangGraphAdapter

ADAPTERS: list[BaseAdapter] = [ClaudeCodeAdapter(), LangGraphAdapter()]

__all__ = ["ADAPTERS", "BaseAdapter", "ClaudeCodeAdapter", "LangGraphAdapter"]
