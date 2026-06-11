# Contributing to Agent Debugger

Thank you for your interest in contributing! Here's how to get started.

## Development Setup

```bash
git clone https://github.com/liwh9527/agent-debugger.git
cd agent-debugger
uv sync --dev
```

## Running Tests

```bash
uv run pytest                    # all tests
uv run pytest --tb=short -q      # quick summary
uv run ruff check src/ tests/    # linting
uv run mypy src/agent_debugger/  # type checking
```

## Making Changes

1. Fork the repository
2. Create a branch: `git checkout -b my-feature`
3. Make your changes
4. Run tests: `uv run pytest && uv run ruff check src/ tests/`
5. Commit: `git commit -m "feat: add my feature"`
6. Push: `git push origin my-feature`
7. Open a Pull Request

## Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):
- `feat:` new feature
- `fix:` bug fix
- `docs:` documentation
- `refactor:` code restructuring
- `test:` adding tests

## Adding a New Adapter

To support a new Agent framework:

1. Create `src/agent_debugger/adapters/your_framework.py`
2. Implement `BaseAdapter` with `detect()` and `load()` methods
3. Register in `src/agent_debugger/adapters/__init__.py`
4. Add tests in `tests/test_your_framework_adapter.py`
5. Add a sample trace in `examples/`

See `adapters/claude_code.py` as a reference implementation.

## Code Style

- Python 3.10+ with `from __future__ import annotations`
- No comments unless the WHY is non-obvious
- All files use `encoding="utf-8"` for file operations
- Type annotations on all public functions
- Run `ruff` and `mypy` before submitting

## Questions?

Open an issue or start a discussion on GitHub.
