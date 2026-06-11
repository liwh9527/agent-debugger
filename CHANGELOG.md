# Changelog

All notable changes to this project will be documented in this file.

## [0.2.0] - 2026-06-10

### Added
- **`scan` command** — auto-discover Claude Code sessions on local machine
- **`diagnose` command** — smart diagnostic report with context pressure, retry loop, and cost hotspot detection
- **`diff` command** — side-by-side comparison of two traces
- **Web UI Diagnostics tab** — findings grouped by category with actionable recommendations
- **Web UI session picker** — sidebar to switch between sessions without restarting
- **Web UI search** — filter timeline iterations by tool name or text
- **Web UI export** — download self-contained HTML report
- **Web UI drag-and-drop** — drop trace files onto the page to load them
- **LangGraph/LangSmith adapter** — support for LangGraph trace JSON files
- **CI integration** — `--fail-if-cost-above`, `--fail-if-errors`, `--fail-if-efficiency-below` exit codes
- **Custom pricing** — `--input-price` and `--output-price` options for cost estimation
- **Timeline enhancements** — `--head`, `--tail`, `--filter`, `--anomalies-only` options
- **Context window analysis** — per-iteration utilization tracking with compaction detection
- **IQR-based anomaly detection** — replaces naive threshold approach
- **GitHub Actions CI** — Python 3.10/3.11/3.12 matrix testing
- **E2E tests** — 11 web server endpoint tests
- **`quickstart` command** — common usage examples

### Fixed
- Python 3.10 compatibility (ISO timestamp Z suffix handling)
- Claude Code adapter detection for real-world JSONL files
- Context utilization calculation (per-iteration instead of cumulative)
- Path traversal vulnerability in static file serving
- Server binds to 127.0.0.1 instead of 0.0.0.0
- CORS restricted to localhost origins
- File path validation in /api/switch endpoint

### Changed
- Package name: `agentloop-debugger` (CLI: `agent-debugger`)
- `serve` command now works with no arguments (auto-selects recent session)
- Web UI dark theme with frosted glass header, token-colored timeline cards
- Diagnostics aggregates findings by category instead of listing every occurrence

## [0.1.0] - 2026-05-28

### Added
- Initial release
- AgentTrace JSON schema (Pydantic models)
- `info` command for trace summaries
- Claude Code JSONL adapter
- CLI with Rich terminal output
- Basic test suite
