"""Tests for the session scanner."""

from __future__ import annotations

import json
from pathlib import Path

from agent_debugger.core.scanner import scan_sessions, shorten_path


class TestScanSessions:
    def test_returns_list(self, tmp_path: Path) -> None:
        result = scan_sessions(base_dir=tmp_path)
        assert isinstance(result, list)

    def test_empty_directory(self, tmp_path: Path) -> None:
        result = scan_sessions(base_dir=tmp_path)
        assert result == []

    def test_nonexistent_directory(self, tmp_path: Path) -> None:
        result = scan_sessions(base_dir=tmp_path / "nonexistent")
        assert result == []

    def test_finds_jsonl_files(self, tmp_path: Path) -> None:
        # Create a mock Claude Code session JSONL
        session_dir = tmp_path / "-Users-test-myproject"
        session_dir.mkdir()
        jsonl_file = session_dir / "session123.jsonl"
        lines = [
            json.dumps({"type": "last-prompt", "sessionId": "s1"}),
            json.dumps({
                "type": "user",
                "message": {"role": "user", "content": [{"type": "text", "text": "hello"}]},
                "timestamp": "2026-06-01T10:00:00.000Z",
            }),
            json.dumps({
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "model": "claude-sonnet-4-20250514",
                    "content": [{"type": "text", "text": "Hi!"}],
                    "usage": {"input_tokens": 100, "output_tokens": 20},
                },
                "timestamp": "2026-06-01T10:00:05.000Z",
            }),
        ]
        jsonl_file.write_text("\n".join(lines))

        result = scan_sessions(base_dir=tmp_path)
        assert len(result) == 1
        assert result[0]["agent_name"] == "claude-code"
        assert result[0]["model"] == "claude-sonnet-4-20250514"
        assert result[0]["lines"] == 3
        assert result[0]["file_size"] > 0
        assert result[0]["estimated_tokens"] > 0
        assert result[0]["estimated_cost"] > 0
        assert result[0]["start_time"] is not None
        assert result[0]["end_time"] is not None

    def test_ignores_non_claude_jsonl(self, tmp_path: Path) -> None:
        # Create a JSONL file that is NOT a Claude Code session
        jsonl_file = tmp_path / "other.jsonl"
        lines = [
            json.dumps({"event": "click", "value": 42}),
            json.dumps({"event": "scroll", "value": 100}),
        ]
        jsonl_file.write_text("\n".join(lines))

        result = scan_sessions(base_dir=tmp_path)
        assert len(result) == 0

    def test_skips_empty_files(self, tmp_path: Path) -> None:
        empty_file = tmp_path / "empty.jsonl"
        empty_file.write_text("")

        result = scan_sessions(base_dir=tmp_path)
        assert len(result) == 0

    def test_nested_discovery(self, tmp_path: Path) -> None:
        # Create nested directory structure
        nested = tmp_path / "a" / "b" / "c"
        nested.mkdir(parents=True)
        jsonl_file = nested / "deep_session.jsonl"
        lines = [
            json.dumps({"type": "last-prompt", "sessionId": "s2"}),
            json.dumps({
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "model": "claude-sonnet-4",
                    "content": [{"type": "text", "text": "ok"}],
                    "usage": {"input_tokens": 50, "output_tokens": 10},
                },
                "timestamp": "2026-06-01T12:00:00+00:00",
            }),
        ]
        jsonl_file.write_text("\n".join(lines))

        result = scan_sessions(base_dir=tmp_path)
        assert len(result) == 1


class TestShortenPath:
    def test_shortens_claude_projects_path(self) -> None:
        home = str(Path.home())
        path = f"{home}/.claude/projects/-Users-foo-myproject/abc123.jsonl"
        short = shorten_path(path)
        assert "myproject" in short
        assert "abc123.jsonl" in short

    def test_handles_simple_path(self) -> None:
        result = shorten_path("/tmp/test.jsonl")
        assert result == "/tmp/test.jsonl"

    def test_replaces_home_with_tilde(self) -> None:
        home = str(Path.home())
        path = f"{home}/somefile.jsonl"
        result = shorten_path(path)
        assert result.startswith("~")
