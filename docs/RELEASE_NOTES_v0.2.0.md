# v0.2.0 Release Notes

## Highlights

Agent Debugger v0.2.0 turns the project from a basic timeline viewer into a complete
Agent-loop profiling toolkit.

### New Commands
- `scan` — auto-discover all Claude Code sessions on your machine
- `diagnose` — smart diagnostic report (context pressure, retry loops, cost hotspots)
- `diff` — side-by-side comparison of two traces
- `quickstart` — common usage examples

### Web UI Overhaul
- Diagnostics tab with grouped findings + actionable recommendations
- Session picker sidebar (switch sessions without restarting)
- Timeline search, token-colored cards, dual-column tool inspection
- Export to self-contained HTML report
- Drag-and-drop trace loading
- Insight banner surfacing the #1 issue at a glance

### Frameworks & Integration
- LangGraph/LangSmith adapter
- CI gates: `--fail-if-cost-above`, `--fail-if-errors`, `--fail-if-efficiency-below`
- Custom pricing: `--input-price` / `--output-price`

### Quality
- 147 tests (incl. 11 E2E web tests), Python 3.10/3.11/3.12 CI
- Security hardening: localhost-only binding, path-traversal guards, CORS restriction
- IQR-based anomaly detection

## Install
```bash
pip install agentloop-debugger
agent-debugger serve   # opens your most recent Claude Code session
```
