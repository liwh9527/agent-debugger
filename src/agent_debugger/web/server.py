"""HTTP server for the agent-debugger web UI."""

from __future__ import annotations

import json
import mimetypes
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Timer

from agent_debugger.analysis.analyzer import TraceAnalyzer
from agent_debugger.core.schema import AgentTrace

STATIC_DIR = Path(__file__).parent / "static"
TEMPLATE_DIR = Path(__file__).parent / "templates"


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

    def _send_json(self, data: dict | list, status: int = 200) -> None:
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
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
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, status: int, message: str = "") -> None:
        body = json.dumps({"error": message or f"HTTP {status}"}).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        """Handle CORS preflight requests."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        path = self.path.split("?")[0]

        if path == "/":
            self._send_file(TEMPLATE_DIR / "index.html", "text/html; charset=utf-8")
        elif path == "/api/trace":
            self._send_json(_serialize_trace(self.trace))
        elif path == "/api/analysis":
            self._send_json(_serialize_analysis(self.analyzer))
        elif path == "/api/diagnose":
            self._handle_diagnose()
        elif path.startswith("/api/iteration/"):
            self._handle_iteration(path)
        elif path.startswith("/static/"):
            rel = path[len("/static/"):]
            file_path = STATIC_DIR / rel
            if ".." in rel or not file_path.exists():
                self._send_error(404)
            else:
                self._send_file(file_path)
        else:
            self._send_error(404)

    def _handle_iteration(self, path: str) -> None:
        try:
            index = int(path.split("/")[-1])
        except ValueError:
            self._send_error(400, "Invalid iteration index")
            return

        matching = [it for it in self.trace.iterations if it.index == index]
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

        engine = DiagnosticEngine(self.trace, self.analyzer)
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
                }
                for r in report.recommendations
            ],
            "summary": report.summary,
            "stats": {
                "input_output_ratio": round(
                    sum(
                        it.token_usage.prompt_tokens
                        for it in self.trace.iterations
                    )
                    / max(
                        sum(
                            it.token_usage.completion_tokens
                            for it in self.trace.iterations
                        ),
                        1,
                    ),
                    1,
                ),
                "input_pct": round(
                    sum(
                        it.token_usage.prompt_tokens
                        for it in self.trace.iterations
                    )
                    / max(
                        sum(
                            it.token_usage.total_tokens
                            for it in self.trace.iterations
                        ),
                        1,
                    )
                    * 100,
                    1,
                ),
                "compaction_count": len(
                    [
                        i
                        for i in range(1, len(self.trace.iterations))
                        if (
                            self.trace.iterations[i].token_usage.prompt_tokens
                            > 0
                            and self.trace.iterations[
                                i - 1
                            ].token_usage.prompt_tokens
                            > 0
                            and self.trace.iterations[
                                i
                            ].token_usage.prompt_tokens
                            < self.trace.iterations[
                                i - 1
                            ].token_usage.prompt_tokens
                            * 0.7
                        )
                    ]
                ),
            },
        }
        self._send_json(data)


def start_server(trace: AgentTrace, port: int = 8080, open_browser: bool = True) -> None:
    analyzer = TraceAnalyzer(trace)

    handler_class = type(
        "BoundHandler",
        (TraceRequestHandler,),
        {"trace": trace, "analyzer": analyzer},
    )

    server = HTTPServer(("0.0.0.0", port), handler_class)

    if open_browser:
        Timer(0.5, webbrowser.open, args=[f"http://localhost:{port}"]).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
