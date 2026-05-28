# Agent Debugger 架构重组设计

**日期**：2026-05-28
**状态**：已确认

## 背景

Agent Debugger 当前是 MVP 骨架阶段，代码不到 100 行，模块平铺在 `src/agent_debugger/` 下。为了支持后续协作开发（TUI、context window 分析、框架适配器等），需要在代码量还小的时候建立清晰的模块边界。

### 当前架构问题

1. **schema.py 职责混合**：既定义数据模型，又包含 4 个分析计算属性（total_tokens、tool_call_counts 等），随着分析逻辑增长会膨胀
2. **Schema 字段缺失**：缺少 context window 状态记录（产品核心差异化点）；`ToolCall.result` 类型过窄（只支持 str）
3. **测试组织粗粒度**：所有测试在一个文件里，缺少 loader 异常路径测试和 CLI 测试
4. **缺少 py.typed 标记**：下游用户无法做类型检查

## 架构设计

### 目录结构

```
src/agent_debugger/
├── __init__.py          # 版本号 + 顶层 API 导出
├── __main__.py          # python -m agent_debugger 入口
├── py.typed             # PEP 561 类型标记
├── core/
│   ├── __init__.py      # 导出 AgentTrace, Iteration, ToolCall, TokenUsage, ContextWindow, load_trace
│   ├── schema.py        # 纯 Pydantic 数据模型，无业务逻辑
│   └── loader.py        # JSON trace 文件加载和验证
├── analysis/
│   ├── __init__.py      # 导出 TraceAnalyzer
│   └── analyzer.py      # 所有分析/统计逻辑
└── ui/
    ├── __init__.py
    └── cli.py           # Click CLI + Rich 输出

tests/
├── __init__.py
├── test_schema.py       # 数据模型构造、序列化、默认值
├── test_loader.py       # 加载成功 + 异常路径（文件不存在、格式错误、schema 不匹配）
├── test_analyzer.py     # 统计属性、错误检测
└── test_cli.py          # CliRunner 端到端测试
```

### 依赖方向

```
ui/ → analysis/ → core/
```

严格单向。`core/` 不依赖 `analysis/` 或 `ui/`，`analysis/` 不依赖 `ui/`。

### Schema 改动

#### 新增 ContextWindow 模型

```python
class ContextWindow(BaseModel):
    used_tokens: int = 0
    max_tokens: int | None = None
```

#### Iteration 新增字段

```python
class Iteration(BaseModel):
    ...
    context_window: ContextWindow | None = None  # 新增
```

#### ToolCall.result 类型放宽

```python
class ToolCall(BaseModel):
    ...
    result: str | dict[str, Any] | None = None  # 原来是 str | None
```

#### AgentTrace 移除计算属性

`total_tokens`、`total_iterations`、`tool_call_counts`、`has_errors` 全部移到 `TraceAnalyzer`。`AgentTrace` 变成纯数据容器。

### TraceAnalyzer

```python
class TraceAnalyzer:
    def __init__(self, trace: AgentTrace): ...

    @property
    def total_tokens(self) -> int: ...

    @property
    def total_iterations(self) -> int: ...

    @property
    def tool_call_counts(self) -> dict[str, int]: ...

    @property
    def has_errors(self) -> bool: ...
```

后续新增的分析能力（context window 水位趋势、异常迭代检测、token 预算预测等）全部加在这个类上。

### CLI 调整

```python
# ui/cli.py
from agent_debugger.core.loader import load_trace
from agent_debugger.analysis.analyzer import TraceAnalyzer

@main.command()
def info(trace_file):
    trace = load_trace(trace_file)
    analyzer = TraceAnalyzer(trace)
    # 使用 analyzer.total_tokens 等属性输出
```

### 顶层 __init__.py 导出

```python
from agent_debugger.core.schema import AgentTrace, Iteration, ToolCall, TokenUsage, ContextWindow
from agent_debugger.core.loader import load_trace
from agent_debugger.analysis.analyzer import TraceAnalyzer
```

外部用户可以直接 `from agent_debugger import AgentTrace, load_trace, TraceAnalyzer`。

## 测试计划

| 文件 | 覆盖内容 |
|------|---------|
| test_schema.py | 模型构造、字段默认值、ContextWindow、ToolCall.result 多类型 |
| test_loader.py | 加载 sample_trace.json 成功；文件不存在 → FileNotFoundError；非 JSON → ValueError；schema 不匹配 → ValidationError |
| test_analyzer.py | total_tokens、total_iterations、tool_call_counts、has_errors |
| test_cli.py | `agent-debugger info sample_trace.json` 输出包含 Agent 名、迭代数、token 数 |

## 不做的

- 不引入 Protocol/ABC 抽象层 — 目前只有一种 loader 实现
- 不做 `core/` 内的进一步拆分 — schema.py 和 loader.py 各自代码量很小
- 不改 pyproject.toml 的依赖和构建配置
- 不做适配器相关的架构预留

## 验证方式

1. `uv run pytest -v` — 所有测试通过
2. `uv run agent-debugger info examples/sample_trace.json` — 输出正常
3. `uv run ruff check src/` — 无 lint 错误
