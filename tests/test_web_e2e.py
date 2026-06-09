"""Basic end-to-end tests for the web server."""
from __future__ import annotations

import json
import threading
import time
from http.client import HTTPConnection
from pathlib import Path

import pytest

from agent_debugger.core.loader import load_trace
from agent_debugger.web.server import start_server

SAMPLE_TRACE = str(Path(__file__).parent.parent / "examples" / "sample_trace.json")


@pytest.fixture()
def server():
    """Start a test server on a random port."""
    if not Path(SAMPLE_TRACE).exists():
        pytest.skip("Sample trace file not found")

    trace = load_trace(SAMPLE_TRACE)
    port = 18765

    def run():
        try:
            start_server(trace, port=port, open_browser=False, trace_path=SAMPLE_TRACE)
        except OSError:
            pass  # Port already in use

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    time.sleep(1)

    # Verify server is up
    try:
        conn = HTTPConnection("127.0.0.1", port, timeout=2)
        conn.request("GET", "/")
        resp = conn.getresponse()
        resp.read()
        conn.close()
    except (OSError, ConnectionRefusedError):
        pytest.skip("Server failed to start (port may be in use)")

    yield port


def _get(port, path):
    conn = HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request("GET", path)
    resp = conn.getresponse()
    body = resp.read().decode()
    conn.close()
    return resp.status, body


class TestWebEndpoints:
    def test_index_returns_html(self, server):
        status, body = _get(server, "/")
        assert status == 200
        assert "<html" in body

    def test_api_trace(self, server):
        status, body = _get(server, "/api/trace")
        assert status == 200
        data = json.loads(body)
        assert "agent_name" in data
        assert "iterations" in data
        assert isinstance(data["iterations"], list)

    def test_api_analysis(self, server):
        status, body = _get(server, "/api/analysis")
        assert status == 200
        data = json.loads(body)
        assert "total_iterations" in data
        assert "cost_estimate" in data

    def test_api_diagnose(self, server):
        status, body = _get(server, "/api/diagnose")
        assert status == 200
        data = json.loads(body)
        assert "findings" in data
        assert "recommendations" in data
        assert "summary" in data

    def test_api_iteration(self, server):
        status, body = _get(server, "/api/iteration/0")
        assert status == 200
        data = json.loads(body)
        assert data["index"] == 0

    def test_api_iteration_not_found(self, server):
        status, _ = _get(server, "/api/iteration/999")
        assert status == 404

    def test_api_sessions(self, server):
        status, body = _get(server, "/api/sessions")
        assert status == 200
        data = json.loads(body)
        assert isinstance(data, list)

    def test_static_css(self, server):
        status, body = _get(server, "/static/style.css")
        assert status == 200
        assert "var(--" in body

    def test_static_not_found(self, server):
        status, _ = _get(server, "/static/nonexist.xyz")
        assert status == 404

    def test_cors_headers(self, server):
        conn = HTTPConnection("127.0.0.1", server, timeout=5)
        conn.request("GET", "/api/trace", headers={"Origin": "http://localhost:18765"})
        resp = conn.getresponse()
        resp.read()
        headers_dict = {k.lower(): v for k, v in resp.getheaders()}
        assert "access-control-allow-origin" in headers_dict
        conn.close()

    def test_load_inline(self, server):
        """Test the drag-and-drop inline file load endpoint."""
        # Read the sample trace to use as content
        with open(SAMPLE_TRACE) as f:
            content = f.read()

        payload = json.dumps({"content": content, "filename": "test.json"}).encode()
        conn = HTTPConnection("127.0.0.1", server, timeout=5)
        conn.request(
            "POST",
            "/api/load-inline",
            body=payload,
            headers={"Content-Type": "application/json"},
        )
        resp = conn.getresponse()
        body = resp.read().decode()
        conn.close()
        assert resp.status == 200
        data = json.loads(body)
        assert data["success"] is True
