"""Session scanner — auto-discovers Claude Code sessions on disk."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def extract_project_name(path_str: str) -> str:
    """Extract a human-readable project name from Claude Code session path.

    Path pattern: ~/.claude/projects/-Users-x-Documents-project-myapp/abc.jsonl
    The directory name encodes the original project path with dashes.
    Subagent paths contain /subagents/ and get prefixed with parent project name.
    """
    parts = Path(path_str).parts

    # Find the project directory (the one under .claude/projects/)
    project_dir = None
    for i, part in enumerate(parts):
        if part == "projects" and i + 1 < len(parts):
            project_dir = parts[i + 1]
            break

    if not project_dir:
        return Path(path_str).stem[:20]

    # Check if this is a subagent
    is_subagent = "subagents" in parts

    # Decode project dir: "-Users-liwh-Documents-project-myapp" -> "myapp"
    segments = project_dir.lstrip("-").split("-")
    # Skip common prefixes
    skip = {"Users", "Documents", "home", "project", "projects", "src", "code"}
    # Also skip the username (typically the segment after "Users")
    meaningful: list[str] = []
    skip_next = False
    for s in segments:
        if s in skip:
            skip_next = s == "Users"  # skip username after "Users"
            continue
        if skip_next:
            skip_next = False
            continue
        if not s or len(s) <= 2:
            continue
        # Skip UUID-like segments (hex chars and dashes, length > 8)
        if len(s) > 8 and all(c in "0123456789abcdef-" for c in s.lower()):
            continue
        meaningful.append(s)

    if meaningful:
        name = "/".join(meaningful[-2:]) if len(meaningful) > 1 else meaningful[0]
    else:
        # Fallback: use session file's first few chars for uniqueness
        stem = Path(path_str).stem
        name = f"project-{stem[:6]}"

    if is_subagent:
        name = f"{name} (subagent)"

    return name


def scan_sessions(
    base_dir: Path | None = None,
    include_subagents: bool = False,
) -> list[dict[str, Any]]:
    """Scan for Claude Code JSONL session files.

    Args:
        base_dir: Directory to search. Defaults to ~/.claude/projects/
        include_subagents: If False (default), skip sessions in subagents/ dirs.

    Returns:
        List of session summary dicts.
    """
    if base_dir is None:
        base_dir = Path.home() / ".claude" / "projects"

    if not base_dir.exists():
        return []

    sessions: list[dict[str, Any]] = []
    for jsonl_path in base_dir.rglob("*.jsonl"):
        # Filter out subagent sessions unless explicitly requested
        if not include_subagents and "subagents" in jsonl_path.parts:
            continue
        summary = _extract_session_summary(jsonl_path)
        if summary is not None:
            sessions.append(summary)

    return sessions


def _extract_session_summary(path: Path) -> dict[str, Any] | None:
    """Extract basic session info from a JSONL file without full parsing."""
    try:
        file_size = path.stat().st_size
        if file_size == 0:
            return None

        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    except OSError:
        return None

    lines_count = 0
    start_time: datetime | None = None
    end_time: datetime | None = None
    agent_name = "claude-code"
    model = "unknown"

    try:
        with open(path, encoding="utf-8") as f:
            first_lines: list[str] = []
            last_lines: list[str] = []

            for i, line in enumerate(f):
                lines_count += 1
                stripped = line.strip()
                if not stripped:
                    continue
                if i < 30:
                    first_lines.append(stripped)
                last_lines.append(stripped)
                # Keep only last 10 lines in memory
                if len(last_lines) > 10:
                    last_lines.pop(0)

        # Parse first lines for start_time and model
        for raw in first_lines:
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError:
                continue

            # Check if it's a Claude Code session
            if obj.get("type") not in (
                "assistant", "user", "last-prompt", "permission-mode"
            ):
                continue

            ts = obj.get("timestamp")
            if ts and start_time is None:
                start_time = _parse_timestamp(ts)

            msg_model = obj.get("message", {}).get("model")
            if msg_model and model == "unknown":
                model = str(msg_model)

        # If no assistant/user messages found in first lines, not a valid session
        if start_time is None and model == "unknown":
            # Quick check: is this even a Claude Code file?
            has_cc_type = False
            for raw in first_lines:
                try:
                    obj = json.loads(raw)
                    if obj.get("type") in ("assistant", "user", "last-prompt", "permission-mode"):
                        has_cc_type = True
                        break
                except json.JSONDecodeError:
                    continue
            if not has_cc_type:
                return None

        # Parse last lines for end_time
        for raw in reversed(last_lines):
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError:
                continue
            ts = obj.get("timestamp")
            if ts:
                end_time = _parse_timestamp(ts)
                if end_time is not None:
                    break

    except OSError:
        return None

    # Try to sum actual usage from parsed lines for a better token estimate
    total_tokens = 0
    for raw in first_lines + last_lines:
        if '"usage"' in raw:
            try:
                obj = json.loads(raw)
                usage = obj.get("message", {}).get("usage", {})
                if not usage:
                    usage = obj.get("usage", {})
                input_t = usage.get("input_tokens", 0)
                output_t = usage.get("output_tokens", 0)
                total_tokens += input_t + output_t
            except (json.JSONDecodeError, AttributeError):
                pass

    # If we found actual usage data, extrapolate from sampled lines
    if total_tokens > 0 and lines_count > 0:
        sampled_lines = len(first_lines) + len(last_lines)
        estimated_tokens = int(total_tokens * (lines_count / max(sampled_lines, 1)))
    else:
        # Fallback to rough heuristic (~4 bytes per token)
        estimated_tokens = file_size // 4

    # Estimate cost (using claude-sonnet-4 pricing as default: $3/M input, $15/M output)
    # Rough split: 80% input, 20% output
    input_tokens = int(estimated_tokens * 0.8)
    output_tokens = int(estimated_tokens * 0.2)
    estimated_cost = (input_tokens / 1_000_000) * 3.0 + (output_tokens / 1_000_000) * 15.0

    return {
        "path": str(path),
        "project_name": extract_project_name(str(path)),
        "file_size": file_size,
        "lines": lines_count,
        "start_time": start_time.isoformat() if start_time else None,
        "end_time": end_time.isoformat() if end_time else None,
        "last_modified": mtime.isoformat(),
        "agent_name": agent_name,
        "model": model,
        "estimated_tokens": estimated_tokens,
        "estimated_cost": estimated_cost,
    }


def shorten_path(path_str: str) -> str:
    """Shorten a session path for display.

    ~/.claude/projects/-Users-foo-myproject/abc123.jsonl
    -> ~/myproject/abc123.jsonl
    """
    home = str(Path.home())
    display = path_str
    if display.startswith(home):
        display = "~" + display[len(home):]

    # Try to extract project name from the encoded directory path
    parts = Path(display).parts
    for i, part in enumerate(parts):
        if part.startswith("-") and len(part) > 5:
            # This is likely the encoded project path like -Users-foo-project
            # Extract last segment as project name
            segments = part.split("-")
            project_name = segments[-1] if segments else part
            filename = Path(display).name
            return f"~/{project_name}/{filename}"

    return display


def _parse_timestamp(ts: Any) -> datetime | None:
    """Parse a timestamp string safely."""
    if not isinstance(ts, str):
        return None
    try:
        ts_clean = ts.replace("Z", "+00:00")
        return datetime.fromisoformat(ts_clean)
    except (ValueError, TypeError):
        return None
