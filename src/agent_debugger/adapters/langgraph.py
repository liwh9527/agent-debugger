"""Adapter for LangGraph/LangSmith trace exports."""

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


class LangGraphAdapter(BaseAdapter):
    name = "langgraph"

    def detect(self, path: Path) -> bool:
        if path.suffix != ".json":
            return False
        try:
            with open(path, encoding="utf-8") as f:
                # Read only first 8KB to check for LangGraph markers
                head = f.read(8192)
            if "child_runs" not in head or "run_type" not in head:
                return False
            if "langgraph" not in head:
                return False
            return True
        except (OSError, UnicodeDecodeError):
            return False

    def load(self, path: Path) -> AgentTrace:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        agent_name = data.get("name", "langgraph-agent")
        child_runs = data.get("child_runs", [])
        model = self._extract_model(child_runs)
        start_time, end_time = self._extract_time_range(data)
        iterations = self._build_iterations(child_runs)

        return AgentTrace(
            agent_name=agent_name,
            model=model,
            start_time=start_time,
            end_time=end_time,
            iterations=iterations,
            metadata={"source": "langgraph", "source_file": str(path)},
        )

    def _extract_model(self, child_runs: list[dict[str, Any]]) -> str:
        for run in child_runs:
            if run.get("run_type") != "llm":
                continue
            llm_output = run.get("outputs", {}).get("llm_output", {})
            if llm_output and llm_output.get("model_name"):
                return str(llm_output["model_name"])
            invocation = run.get("extra", {}).get("invocation_params", {})
            if invocation.get("model_name"):
                return str(invocation["model_name"])
        return "unknown"

    def _extract_time_range(
        self, data: dict[str, Any]
    ) -> tuple[datetime | None, datetime | None]:
        start = self._parse_timestamp(data.get("start_time"))
        end = self._parse_timestamp(data.get("end_time"))
        return start, end

    def _parse_timestamp(self, ts: str | None) -> datetime | None:
        if not ts:
            return None
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None

    def _build_iterations(
        self, child_runs: list[dict[str, Any]]
    ) -> list[Iteration]:
        groups = self._group_into_iterations(child_runs)
        iterations: list[Iteration] = []
        for idx, group in enumerate(groups):
            iteration = self._build_single_iteration(idx, group)
            iterations.append(iteration)
        return iterations

    def _group_into_iterations(
        self, child_runs: list[dict[str, Any]]
    ) -> list[list[dict[str, Any]]]:
        """Group child_runs into iterations: each LLM call + its following tool calls."""
        groups: list[list[dict[str, Any]]] = []
        current: list[dict[str, Any]] = []

        for run in child_runs:
            run_type = run.get("run_type", "")
            if run_type == "llm":
                if current:
                    groups.append(current)
                current = [run]
            elif run_type == "tool":
                current.append(run)
            else:
                current.append(run)

        if current:
            groups.append(current)

        return groups

    def _build_single_iteration(
        self, index: int, group: list[dict[str, Any]]
    ) -> Iteration:
        think: str | None = None
        tool_calls: list[ToolCall] = []
        token_usage = TokenUsage()

        for run in group:
            run_type = run.get("run_type", "")
            if run_type == "llm":
                think = self._extract_llm_content(run)
                token_usage = self._extract_token_usage(run)
            elif run_type == "tool":
                tc = self._extract_tool_call(run)
                if tc:
                    tool_calls.append(tc)

        return Iteration(
            index=index,
            think=think,
            tool_calls=tool_calls,
            token_usage=token_usage,
        )

    def _extract_llm_content(self, run: dict[str, Any]) -> str | None:
        generations = run.get("outputs", {}).get("generations", [])
        if not generations:
            return None
        for gen_list in generations:
            if not isinstance(gen_list, list):
                continue
            for gen in gen_list:
                if not isinstance(gen, dict):
                    continue
                text = gen.get("text")
                if text:
                    return str(text)
                message = gen.get("message", {})
                content = message.get("content")
                if content:
                    return str(content)
        return None

    def _extract_token_usage(self, run: dict[str, Any]) -> TokenUsage:
        llm_output = run.get("outputs", {}).get("llm_output", {})
        usage = llm_output.get("token_usage", {}) if llm_output else {}
        if not usage:
            return TokenUsage()
        return TokenUsage(
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
        )

    def _extract_tool_call(self, run: dict[str, Any]) -> ToolCall | None:
        name = run.get("name", "unknown")
        raw_input = run.get("inputs", {}).get("input", "")
        arguments: dict[str, Any] = {}
        if isinstance(raw_input, str):
            try:
                arguments = json.loads(raw_input)
            except (json.JSONDecodeError, TypeError):
                arguments = {"input": raw_input}
        elif isinstance(raw_input, dict):
            arguments = raw_input

        result = run.get("outputs", {}).get("output")

        duration_ms: int | None = None
        start = self._parse_timestamp(run.get("start_time"))
        end = self._parse_timestamp(run.get("end_time"))
        if start and end:
            duration_ms = int((end - start).total_seconds() * 1000)

        return ToolCall(
            name=name,
            arguments=arguments,
            result=result,
            duration_ms=duration_ms,
        )
