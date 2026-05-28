"""Adapter for Claude Code JSONL transcripts."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from agent_debugger.adapters.base import BaseAdapter
from agent_debugger.core.schema import (
    AgentTrace,
    Iteration,
    TokenUsage,
    ToolCall,
)


class ClaudeCodeAdapter(BaseAdapter):
    name = "claude_code"

    def detect(self, path: Path) -> bool:
        if path.suffix != ".jsonl":
            return False
        try:
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    obj = json.loads(line)
                    if obj.get("type") in ("assistant", "user", "last-prompt"):
                        return True
                    break
        except (json.JSONDecodeError, OSError):
            return False
        return False

    def load(self, path: Path) -> AgentTrace:
        raw_messages = self._read_messages(path)
        model = self._extract_model(raw_messages)
        start_time, end_time = self._extract_time_range(raw_messages)
        iterations = self._build_iterations(raw_messages)

        return AgentTrace(
            agent_name="claude-code",
            model=model,
            start_time=start_time,
            end_time=end_time,
            iterations=iterations,
            metadata={"source": "claude_code", "source_file": str(path)},
        )

    def _read_messages(self, path: Path) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if obj.get("type") in ("assistant", "user"):
                    messages.append(obj)
        return messages

    def _extract_model(self, messages: list[dict[str, Any]]) -> str:
        for msg in messages:
            model = msg.get("message", {}).get("model")
            if model:
                return model
        return "unknown"

    def _extract_time_range(
        self, messages: list[dict[str, Any]]
    ) -> tuple[datetime | None, datetime | None]:
        timestamps: list[datetime] = []
        for msg in messages:
            ts = msg.get("timestamp")
            if ts:
                try:
                    timestamps.append(datetime.fromisoformat(ts))
                except (ValueError, TypeError):
                    continue
        if not timestamps:
            return None, None
        return min(timestamps), max(timestamps)

    def _build_iterations(
        self, messages: list[dict[str, Any]]
    ) -> list[Iteration]:
        assistant_groups = self._group_by_assistant(messages)
        iterations: list[Iteration] = []

        tool_results = self._collect_tool_results(messages)

        for idx, group in enumerate(assistant_groups):
            iteration = self._build_single_iteration(
                idx, group, tool_results
            )
            if iteration:
                iterations.append(iteration)

        return iterations

    def _group_by_assistant(
        self, messages: list[dict[str, Any]]
    ) -> list[list[dict[str, Any]]]:
        """Group messages into chunks, each starting with an assistant message."""
        groups: list[list[dict[str, Any]]] = []
        current: list[dict[str, Any]] = []

        for msg in messages:
            if msg.get("type") == "assistant" and current:
                if any(
                    self._has_meaningful_content(m)
                    for m in current
                    if m.get("type") == "assistant"
                ):
                    groups.append(current)
                current = []
            current.append(msg)

        if current and any(
            self._has_meaningful_content(m)
            for m in current
            if m.get("type") == "assistant"
        ):
            groups.append(current)

        return groups

    def _has_meaningful_content(self, msg: dict[str, Any]) -> bool:
        content = msg.get("message", {}).get("content", [])
        if not isinstance(content, list):
            return False
        return any(
            isinstance(c, dict) and c.get("type") in ("text", "tool_use", "thinking")
            for c in content
        )

    def _collect_tool_results(
        self, messages: list[dict[str, Any]]
    ) -> dict[str, str | dict[str, Any]]:
        results: dict[str, str | dict[str, Any]] = {}
        for msg in messages:
            if msg.get("type") != "user":
                continue
            content = msg.get("message", {}).get("content", [])
            if not isinstance(content, list):
                continue
            for c in content:
                if isinstance(c, dict) and c.get("type") == "tool_result":
                    tool_id = c.get("tool_use_id", "")
                    result = c.get("content", "")
                    if isinstance(result, list):
                        texts = [
                            item.get("text", "")
                            for item in result
                            if isinstance(item, dict) and item.get("type") == "text"
                        ]
                        result = "\n".join(texts) if texts else str(result)
                    results[tool_id] = result
        return results

    def _build_single_iteration(
        self,
        index: int,
        group: list[dict[str, Any]],
        tool_results: dict[str, str | dict[str, Any]],
    ) -> Iteration | None:
        think_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        total_input = 0
        total_output = 0

        for msg in group:
            if msg.get("type") != "assistant":
                continue
            content = msg.get("message", {}).get("content", [])
            if not isinstance(content, list):
                continue

            usage = msg.get("message", {}).get("usage", {})
            total_input += usage.get("input_tokens", 0)
            total_output += usage.get("output_tokens", 0)

            for c in content:
                if not isinstance(c, dict):
                    continue
                if c.get("type") == "thinking":
                    think_parts.append(c.get("thinking", ""))
                elif c.get("type") == "tool_use":
                    tc_id = c.get("id", "")
                    result = tool_results.get(tc_id)
                    tool_calls.append(
                        ToolCall(
                            name=c.get("name", "unknown"),
                            arguments=c.get("input", {}),
                            result=result,
                        )
                    )

        if not think_parts and not tool_calls and total_input == 0:
            return None

        return Iteration(
            index=index,
            think="\n".join(think_parts) if think_parts else None,
            tool_calls=tool_calls,
            token_usage=TokenUsage(
                prompt_tokens=total_input,
                completion_tokens=total_output,
                total_tokens=total_input + total_output,
            ),
        )
