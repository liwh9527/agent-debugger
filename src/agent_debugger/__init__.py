"""Agent Debugger — Interactive debugger for AI Agent loops."""

__version__ = "0.2.0"

from agent_debugger.analysis.analyzer import TraceAnalyzer
from agent_debugger.core.loader import load_trace
from agent_debugger.core.schema import (
    AgentTrace,
    ContextWindow,
    Iteration,
    TokenUsage,
    ToolCall,
)

__all__ = [
    "AgentTrace",
    "ContextWindow",
    "Iteration",
    "TokenUsage",
    "ToolCall",
    "TraceAnalyzer",
    "load_trace",
]
