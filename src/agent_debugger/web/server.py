"""HTTP server for the agent-debugger web UI."""

from __future__ import annotations

import json
import mimetypes
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Timer
from typing import Any

from agent_debugger.analysis.analyzer import TraceAnalyzer
from agent_debugger.core.schema import AgentTrace

STATIC_DIR = Path(__file__).parent / "static"
TEMPLATE_DIR = Path(__file__).parent / "templates"

# Mutable server state container for session switching
_server_state: dict[str, Any] = {}


def _serialize_trace(trace: AgentTrace) -> dict:
    return {
        "agent_name": trace.agent_name,
        "model": trace.model,
        "start_time": trace.start_time.isoformat() if trace.start_time else None,
        "end_time": trace.end_time.isoformat() if trace.end_time else None,
        "iterations": [
            {
                "index": it.index,
                "think": it.think,
                "tool_calls": [
                    {
                        "name": tc.name,
                        "arguments": tc.arguments,
                        "result": tc.result,
                        "duration_ms": tc.duration_ms,
                    }
                    for tc in it.tool_calls
                ],
                "token_usage": {
                    "prompt_tokens": it.token_usage.prompt_tokens,
                    "completion_tokens": it.token_usage.completion_tokens,
                    "total_tokens": it.token_usage.total_tokens,
                },
                "context_window": (
                    {
                        "used_tokens": it.context_window.used_tokens,
                        "max_tokens": it.context_window.max_tokens,
                    }
                    if it.context_window
                    else None
                ),
                "duration_ms": it.duration_ms,
                "error": it.error,
            }
            for it in trace.iterations
        ],
        "metadata": trace.metadata,
    }


def _serialize_analysis(analyzer: TraceAnalyzer) -> dict:
    return {
        "total_iterations": analyzer.total_iterations,
        "total_tokens": analyzer.total_tokens,
        "tool_call_counts": analyzer.tool_call_counts,
        "has_errors": analyzer.has_errors,
        "context_utilization": analyzer.context_utilization_trend(),
        "context_growth_rate": analyzer.context_growth_rate(),
        "token_efficiency": analyzer.token_efficiency(),
        "cost_estimate": analyzer.cost_estimate(),
        "timeline": analyzer.timeline_summary(),
        "anomalies": analyzer.detect_anomalies(),
    }


class TraceRequestHandler(BaseHTTPRequestHandler):
    trace: AgentTrace
    analyzer: TraceAnalyzer

    def log_message(self, format: str, *args: object) -> None:
        pass

    def _cors_origin(self) -> str:
        """Return an appropriate CORS origin, restricted to localhost."""
        origin = self.headers.get("Origin", "")
        if origin.startswith("http://localhost:") or origin.startswith("http://127.0.0.1:"):
            return origin
        return "http://localhost"

    def _send_json(self, data: dict | list, status: int = 200) -> None:
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", self._cors_origin())
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path, content_type: str | None = None) -> None:
        if not path.exists():
            self._send_error(404)
            return
        body = path.read_bytes()
        if content_type is None:
            content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", self._cors_origin())
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, status: int, message: str = "") -> None:
        body = json.dumps({"error": message or f"HTTP {status}"}).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", self._cors_origin())
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        """Handle CORS preflight requests."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", self._cors_origin())
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        path = self.path.split("?")[0]

        if path == "/":
            self._send_file(TEMPLATE_DIR / "index.html", "text/html; charset=utf-8")
        elif path == "/api/trace":
            self._send_json(_serialize_trace(_server_state["trace"]))
        elif path == "/api/analysis":
            self._send_json(_serialize_analysis(_server_state["analyzer"]))
        elif path == "/api/sessions":
            self._handle_sessions()
        elif path == "/api/diagnose":
            self._handle_diagnose()
        elif path.startswith("/api/iteration/"):
            self._handle_iteration(path)
        elif path.startswith("/static/"):
            rel = path[len("/static/"):]
            file_path = (STATIC_DIR / rel).resolve()
            if not str(file_path).startswith(str(STATIC_DIR.resolve())):
                self._send_error(403)
                return
            if not file_path.exists():
                self._send_error(404)
            else:
                self._send_file(file_path)
        else:
            self._send_error(404)

    def do_POST(self) -> None:
        path = self.path.split("?")[0]

        if path == "/api/switch":
            self._handle_switch()
        elif path == "/api/load-inline":
            self._handle_load_inline()
        else:
            self._send_error(404)

    def _handle_sessions(self) -> None:
        from agent_debugger.core.scanner import scan_sessions

        sessions = scan_sessions(include_subagents=False)
        current_path = _server_state.get("path", "")
        for s in sessions:
            s["is_current"] = s["path"] == current_path
        # Sort: current first, then by last_modified descending
        sessions.sort(key=lambda s: s.get("last_modified", ""), reverse=True)
        sessions.sort(key=lambda s: not s["is_current"])
        self._send_json(sessions)

    def _handle_switch(self) -> None:
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0 or content_length > 1_000_000:
            self._send_json({"error": "Invalid request body"}, status=400)
            return
        try:
            body = json.loads(self.rfile.read(content_length))
        except (json.JSONDecodeError, ValueError):
            self._send_json({"error": "Invalid JSON"}, status=400)
            return
        new_path = body.get("path")
        if not new_path or not Path(new_path).exists():
            self._send_json({"error": "File not found"}, status=404)
            return

        allowed_base = Path.home() / ".claude" / "projects"
        new_path_resolved = Path(new_path).resolve()
        if not str(new_path_resolved).startswith(str(allowed_base.resolve())):
            self._send_json(
                {"error": "Path not allowed — only sessions in ~/.claude/projects/ can be loaded"},
                status=403,
            )
            return

        from agent_debugger.core.loader import load_trace

        try:
            new_trace = load_trace(new_path)
            new_analyzer = TraceAnalyzer(new_trace)
            _server_state["trace"] = new_trace
            _server_state["analyzer"] = new_analyzer
            _server_state["path"] = new_path
            self._send_json({
                "success": True,
                "agent_name": new_trace.agent_name,
                "model": new_trace.model,
            })
        except Exception as e:
            self._send_json({"error": str(e)}, status=500)

    def _handle_load_inline(self) -> None:
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0 or content_length > 50_000_000:  # 50MB max
            self._send_json({"error": "File too large or empty"}, status=400)
            return
        try:
            body = json.loads(self.rfile.read(content_length))
        except (json.JSONDecodeError, ValueError):
            self._send_json({"error": "Invalid request"}, status=400)
            return

        content = body.get("content", "")
        filename = body.get("filename", "uploaded.json")

        import tempfile

        suffix = ".jsonl" if filename.endswith(".jsonl") else ".json"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=suffix, delete=False, encoding="utf-8"
        ) as f:
            f.write(content)
            temp_path = f.name

        try:
            from agent_debugger.core.loader import load_trace

            new_trace = load_trace(temp_path)
            new_analyzer = TraceAnalyzer(new_trace)
            _server_state["trace"] = new_trace
            _server_state["analyzer"] = new_analyzer
            _server_state["path"] = temp_path
            self._send_json({"success": True})
        except Exception as e:
            self._send_json({"error": str(e)}, status=400)

    def _handle_iteration(self, path: str) -> None:
        try:
            index = int(path.split("/")[-1])
        except ValueError:
            self._send_error(400, "Invalid iteration index")
            return

        trace = _server_state["trace"]
        matching = [it for it in trace.iterations if it.index == index]
        if not matching:
            self._send_error(404, f"Iteration {index} not found")
            return

        it = matching[0]
        data = {
            "index": it.index,
            "think": it.think,
            "tool_calls": [
                {
                    "name": tc.name,
                    "arguments": tc.arguments,
                    "result": tc.result,
                    "duration_ms": tc.duration_ms,
                }
                for tc in it.tool_calls
            ],
            "token_usage": {
                "prompt_tokens": it.token_usage.prompt_tokens,
                "completion_tokens": it.token_usage.completion_tokens,
                "total_tokens": it.token_usage.total_tokens,
            },
            "context_window": (
                {
                    "used_tokens": it.context_window.used_tokens,
                    "max_tokens": it.context_window.max_tokens,
                }
                if it.context_window
                else None
            ),
            "duration_ms": it.duration_ms,
            "error": it.error,
        }
        self._send_json(data)

    def _handle_diagnose(self) -> None:
        from agent_debugger.analysis.diagnostics import DiagnosticEngine

        trace = _server_state["trace"]
        analyzer = _server_state["analyzer"]
        engine = DiagnosticEngine(trace, analyzer)
        report = engine.run()
        data = {
            "findings": [
                {
                    "severity": f.severity,
                    "category": f.category,
                    "message": f.message,
                    "iteration": f.iteration,
                }
                for f in report.findings
            ],
            "recommendations": [
                {
                    "priority": r.priority,
                    "message": r.message,
                    "estimated_savings": r.estimated_savings,
                    "how_to": r.how_to,
                }
                for r in report.recommendations
            ],
            "summary": report.summary,
            "stats": {
                "input_output_ratio": round(
                    sum(
                        it.token_usage.prompt_tokens
                        for it in trace.iterations
                    )
                    / max(
                        sum(
                            it.token_usage.completion_tokens
                            for it in trace.iterations
                        ),
                        1,
                    ),
                    1,
                ),
                "input_pct": round(
                    sum(
                        it.token_usage.prompt_tokens
                        for it in trace.iterations
                    )
                    / max(
                        sum(
                            it.token_usage.total_tokens
                            for it in trace.iterations
                        ),
                        1,
                    )
                    * 100,
                    1,
                ),
                "compaction_count": len(
                    [
                        i
                        for i in range(1, len(trace.iterations))
                        if (
                            trace.iterations[i].token_usage.prompt_tokens
                            > 0
                            and trace.iterations[
                                i - 1
                            ].token_usage.prompt_tokens
                            > 0
                            and trace.iterations[
                                i
                            ].token_usage.prompt_tokens
                            < trace.iterations[
                                i - 1
                            ].token_usage.prompt_tokens
                            * 0.7
                        )
                    ]
                ),
            },
        }
        self._send_json(data)


def start_server(
    trace: AgentTrace,
    port: int = 8080,
    open_browser: bool = True,
    trace_path: str | None = None,
) -> None:
    analyzer = TraceAnalyzer(trace)

    # Initialize mutable server state for session switching
    _server_state["trace"] = trace
    _server_state["analyzer"] = analyzer
    _server_state["path"] = str(trace_path) if trace_path else ""

    handler_class = type("BoundHandler", (TraceRequestHandler,), {})

    server = HTTPServer(("127.0.0.1", port), handler_class)

    if open_browser:
        Timer(0.5, webbrowser.open, args=[f"http://localhost:{port}"]).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
