from agent_debugger.adapters.base import BaseAdapter
from agent_debugger.adapters.claude_code import ClaudeCodeAdapter

ADAPTERS: list[BaseAdapter] = [ClaudeCodeAdapter()]

__all__ = ["ADAPTERS", "BaseAdapter", "ClaudeCodeAdapter"]
