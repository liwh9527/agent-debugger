"""Diagnostic engine — actionable insights from agent traces."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agent_debugger.analysis.analyzer import TraceAnalyzer
from agent_debugger.core.schema import AgentTrace


@dataclass
class Finding:
    severity: str  # "warning", "info", "critical"
    category: str  # "context_pressure", "retry_loop", "cost_hotspot", "error"
    message: str
    iteration: int | None = None
    details: dict[str, Any] | None = None


@dataclass
class Recommendation:
    priority: int  # 1-3
    message: str
    estimated_savings: str | None = None
    how_to: str | None = None


@dataclass
class DiagnosticReport:
    findings: list[Finding] = field(default_factory=list)
    recommendations: list[Recommendation] = field(default_factory=list)
    summary: str = ""


class DiagnosticEngine:
    def __init__(self, trace: AgentTrace, analyzer: TraceAnalyzer) -> None:
        self.trace = trace
        self.analyzer = analyzer

    def run(self) -> DiagnosticReport:
        """Run all diagnostic checks and return a report."""
        findings: list[Finding] = []
        findings.extend(self._check_context_pressure())
        findings.extend(self._check_retry_loops())
        findings.extend(self._check_cost_hotspots())
        findings.extend(self._check_token_efficiency())
        findings.extend(self._check_idle_gaps())
        findings.extend(self._check_errors())

        recommendations = self._generate_recommendations(findings)
        summary = self._generate_summary(findings)

        return DiagnosticReport(
            findings=findings,
            recommendations=recommendations,
            summary=summary,
        )

    def _check_context_pressure(self) -> list[Finding]:
        """Find iterations where utilization > 80% and compaction events."""
        findings: list[Finding] = []
        utilization = self.analyzer.context_utilization_trend()

        # High utilization warnings
        for i, util in enumerate(utilization):
            if util > 0.80:
                findings.append(Finding(
                    severity="warning",
                    category="context_pressure",
                    message=f"Context utilization at {util * 100:.0f}% — approaching limit",
                    iteration=i,
                    details={"utilization": util},
                ))

        # Detect compaction events (utilization drops > 20% between consecutive iterations)
        for i in range(1, len(utilization)):
            drop = utilization[i - 1] - utilization[i]
            if drop > 0.20:
                findings.append(Finding(
                    severity="info",
                    category="context_pressure",
                    message=(
                        f"Context compaction detected: "
                        f"{utilization[i - 1] * 100:.0f}% → {utilization[i] * 100:.0f}%"
                    ),
                    iteration=i,
                    details={"drop": drop, "before": utilization[i - 1], "after": utilization[i]},
                ))

        return findings

    def _check_retry_loops(self) -> list[Finding]:
        """Detect 3+ consecutive iterations calling the same tool with similar arguments."""
        findings: list[Finding] = []
        iterations = self.trace.iterations

        if len(iterations) < 3:
            return findings

        i = 0
        while i < len(iterations) - 2:
            # Get tool names for current iteration
            current_tools = [tc.name for tc in iterations[i].tool_calls]
            if not current_tools:
                i += 1
                continue

            # Check consecutive iterations for same tool pattern
            streak = 1
            for j in range(i + 1, len(iterations)):
                next_tools = [tc.name for tc in iterations[j].tool_calls]
                if next_tools == current_tools:
                    streak += 1
                else:
                    break

            if streak >= 3:
                tool_name = current_tools[0] if len(current_tools) == 1 else str(current_tools)
                findings.append(Finding(
                    severity="warning",
                    category="retry_loop",
                    message=(
                        f"Possible retry loop: {tool_name} called "
                        f"{streak} times consecutively"
                    ),
                    iteration=i,
                    details={
                        "tool": tool_name, "streak": streak,
                        "start": i, "end": i + streak - 1,
                    },
                ))
                i += streak
            else:
                i += 1

        return findings

    def _check_cost_hotspots(self) -> list[Finding]:
        """Find iterations consuming > 10% of total tokens."""
        findings: list[Finding] = []
        total = self.analyzer.total_tokens
        if total == 0:
            return findings

        for it in self.trace.iterations:
            fraction = it.token_usage.total_tokens / total
            if fraction > 0.10 and len(self.trace.iterations) > 3:
                findings.append(Finding(
                    severity="info",
                    category="cost_hotspot",
                    message=(
                        f"Iteration consumed {fraction * 100:.0f}% of total tokens "
                        f"({it.token_usage.total_tokens:,} tokens)"
                    ),
                    iteration=it.index,
                    details={"fraction": fraction, "tokens": it.token_usage.total_tokens},
                ))

        return findings

    def _check_token_efficiency(self) -> list[Finding]:
        """Flag if token efficiency < 2%."""
        findings: list[Finding] = []
        efficiency = self.analyzer.token_efficiency()

        if efficiency < 0.02 and self.analyzer.total_tokens > 0:
            findings.append(Finding(
                severity="warning",
                category="token_efficiency",
                message=f"Token efficiency is very low: {efficiency * 100:.2f}%",
                details={"efficiency": efficiency},
            ))

        return findings

    def _check_idle_gaps(self) -> list[Finding]:
        """Detect long idle gaps (> 5 minutes) between iterations."""
        findings: list[Finding] = []
        iterations = self.trace.iterations

        sum_iteration_ms = sum(it.duration_ms or 0 for it in iterations)
        if sum_iteration_ms == 0:
            return findings  # No per-iteration timing data available

        for i in range(1, len(iterations)):
            prev_dur = iterations[i - 1].duration_ms
            curr_dur = iterations[i].duration_ms
            # If we have duration info and there's a large gap
            if prev_dur is not None and curr_dur is not None:
                # We can't directly compute inter-iteration gap from duration alone
                # unless we have timestamps. Skip if no timing info available.
                pass

        # Alternative: use start/end time if available per-iteration
        # For now, check total session duration vs sum of iteration durations
        if self.trace.start_time and self.trace.end_time:
            try:
                total_duration = (self.trace.end_time - self.trace.start_time).total_seconds()
            except TypeError:
                return findings  # Mixed timezone awareness
            sum_iteration_s = sum_iteration_ms / 1000.0
            idle_s = total_duration - sum_iteration_s
            if idle_s > 300 and total_duration > 0:  # > 5 minutes idle
                findings.append(Finding(
                    severity="info",
                    category="idle_gap",
                    message=(
                        f"Session had ~{idle_s / 60:.0f} minutes of idle time "
                        f"({idle_s:.0f}s out of {total_duration:.0f}s total)"
                    ),
                    details={"idle_seconds": idle_s, "total_seconds": total_duration},
                ))

        return findings

    def _check_errors(self) -> list[Finding]:
        """Flag all iterations with errors."""
        findings: list[Finding] = []
        for it in self.trace.iterations:
            if it.error:
                findings.append(Finding(
                    severity="critical",
                    category="error",
                    message=f"Error in iteration: {it.error}",
                    iteration=it.index,
                    details={"error": it.error},
                ))
        return findings

    def _generate_recommendations(self, findings: list[Finding]) -> list[Recommendation]:
        """Generate actionable recommendations from findings."""
        recommendations: list[Recommendation] = []

        # Count compaction events
        compactions = [
            f for f in findings
            if f.category == "context_pressure" and "compaction" in f.message.lower()
        ]
        if len(compactions) > 3:
            recommendations.append(Recommendation(
                priority=1,
                message=(
                    "Split this session into shorter conversations to avoid "
                    "repeated context compression"
                ),
                estimated_savings="30-50% fewer wasted tokens from re-summarization",
                how_to=(
                    "Start new sessions every 50-100 iterations, "
                    "or when context utilization exceeds 70%"
                ),
            ))

        # Retry loops
        retry_findings = [f for f in findings if f.category == "retry_loop"]
        for rf in retry_findings:
            details = rf.details or {}
            tool = details.get("tool", "unknown")
            streak = details.get("streak", 3)
            recommendations.append(Recommendation(
                priority=2,
                message=(
                    f"Tool '{tool}' was called {streak} times in a row — "
                    f"check if the tool is returning useful results"
                ),
                how_to=(
                    "Review the tool results in the timeline view "
                    "and fix error handling or validation logic"
                ),
            ))

        # Cost hotspots
        hotspots = [f for f in findings if f.category == "cost_hotspot"]
        for hf in hotspots:
            details = hf.details or {}
            fraction = details.get("fraction", 0)
            recommendations.append(Recommendation(
                priority=2,
                message=(
                    f"Iteration #{hf.iteration} consumed {fraction * 100:.0f}% of tokens — "
                    f"check for large file reads or verbose tool results"
                ),
                estimated_savings=f"~{fraction * 100:.0f}% token reduction if optimized",
                how_to=(
                    "Use agent-debugger inspect <trace> <iteration> "
                    "to view what tools returned large outputs"
                ),
            ))

        # Token efficiency
        efficiency_findings = [f for f in findings if f.category == "token_efficiency"]
        if efficiency_findings:
            details = efficiency_findings[0].details or {}
            eff = details.get("efficiency", 0)
            recommendations.append(Recommendation(
                priority=3,
                message=(
                    f"Token efficiency is very low ({eff * 100:.2f}%) — "
                    f"typical for long sessions. Shorter sessions would improve this to ~5-10%"
                ),
                estimated_savings="2-5x improvement in output per input token",
                how_to="Break complex tasks into multiple shorter sessions with focused goals",
            ))

        # Sort by priority
        recommendations.sort(key=lambda r: r.priority)
        return recommendations

    def _generate_summary(self, findings: list[Finding]) -> str:
        """Generate a one-line summary."""
        if not findings:
            return "No issues detected — session looks healthy."

        critical = sum(1 for f in findings if f.severity == "critical")
        warnings = sum(1 for f in findings if f.severity == "warning")
        info = sum(1 for f in findings if f.severity == "info")

        parts: list[str] = []
        if critical:
            parts.append(f"{critical} critical")
        if warnings:
            parts.append(f"{warnings} warnings")
        if info:
            parts.append(f"{info} info")

        return f"Found {', '.join(parts)} across {len(self.trace.iterations)} iterations."
