"""AgentTrace schema — pure data models for Agent loop traces."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    result: str | dict[str, Any] | None = None
    duration_ms: int | None = None


class TokenUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ContextWindow(BaseModel):
    used_tokens: int = 0
    max_tokens: int | None = None


class Iteration(BaseModel):
    index: int
    think: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    observation: str | None = None
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    context_window: ContextWindow | None = None
    duration_ms: int | None = None
    error: str | None = None


class AgentTrace(BaseModel):
    agent_name: str = "unknown"
    model: str = "unknown"
    start_time: datetime | None = None
    end_time: datetime | None = None
    iterations: list[Iteration] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
