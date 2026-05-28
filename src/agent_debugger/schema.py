"""AgentTrace schema — the core data model for Agent loop traces."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    result: str | None = None
    duration_ms: int | None = None


class TokenUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class Iteration(BaseModel):
    index: int
    think: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    observation: str | None = None
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    duration_ms: int | None = None
    error: str | None = None


class AgentTrace(BaseModel):
    agent_name: str = "unknown"
    model: str = "unknown"
    start_time: datetime | None = None
    end_time: datetime | None = None
    iterations: list[Iteration] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return sum(it.token_usage.total_tokens for it in self.iterations)

    @property
    def total_iterations(self) -> int:
        return len(self.iterations)

    @property
    def tool_call_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for it in self.iterations:
            for tc in it.tool_calls:
                counts[tc.name] = counts.get(tc.name, 0) + 1
        return counts

    @property
    def has_errors(self) -> bool:
        return any(it.error is not None for it in self.iterations)
