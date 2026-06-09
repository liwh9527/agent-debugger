(function () {
    "use strict";

    let traceData = null;
    let analysisData = null;

    async function fetchJSON(url) {
        const res = await fetch(url);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
    }

    async function init() {
        try {
            [traceData, analysisData] = await Promise.all([
                fetchJSON("/api/trace"),
                fetchJSON("/api/analysis"),
            ]);
            document.getElementById('loading').style.display = 'none';
            document.title = `${traceData.agent_name} (${traceData.model}) — Agent Debugger`;
            renderHeaderMeta();
            renderOverview();
            setupStatCardNavigation();
            renderTimeline();
            renderContextChart();
            renderIterationsTable();
            renderDiagnostics();
            setupTabs();
            setupTimelineSearch();
            setupBackToTop();
            setupKeyboardShortcuts();
            setupSidebar();
            loadSessions();
        } catch (err) {
            document.getElementById('loading').style.display = 'none';
            document.querySelector(".content").innerHTML =
                `<div class="stat-card" style="text-align:center;padding:3rem">
                    <p style="color:var(--error);margin-bottom:1rem">Failed to load data: ${err.message}</p>
                    <button onclick="location.reload()" class="page-btn">Retry</button>
                </div>`;
        }
    }

    function setupTabs() {
        const tabs = document.querySelectorAll(".tab");
        const panels = document.querySelectorAll(".tab-panel");
        tabs.forEach((tab) => {
            tab.addEventListener("click", () => {
                tabs.forEach((t) => t.classList.remove("active"));
                panels.forEach((p) => p.classList.remove("active"));
                tab.classList.add("active");
                document.getElementById(`panel-${tab.dataset.tab}`).classList.add("active");
            });
        });
    }

    function renderHeaderMeta() {
        const meta = document.getElementById("header-meta");
        meta.innerHTML = `
            <span>${traceData.agent_name}</span>
            <span>${traceData.model}</span>
            <span>${analysisData.total_iterations} iterations</span>
        `;
    }

    function formatNumber(n) {
        return n.toLocaleString();
    }

    function renderOverview() {
        const grid = document.getElementById("stats-grid");
        const cost = analysisData.cost_estimate;
        const duration = computeTotalDuration();
        const effPercent = (analysisData.token_efficiency * 100).toFixed(1);
        const effColor = effPercent >= 10 ? '#10b981' : effPercent >= 3 ? '#f59e0b' : '#ef4444';

        grid.innerHTML = `
            <div class="stat-card">
                <div class="stat-label">Agent</div>
                <div class="stat-value">${traceData.agent_name}</div>
                <div class="stat-sub">${traceData.model}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Iterations</div>
                <div class="stat-value">${analysisData.total_iterations}</div>
                <div class="stat-sub">${analysisData.has_errors ? "Has errors" : "No errors"}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Total Tokens</div>
                <div class="stat-value">${formatNumber(analysisData.total_tokens)}</div>
                <div class="stat-sub">Efficiency: <span style="color:${effColor}">${effPercent}%</span></div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Estimated Cost</div>
                <div class="stat-value">$${cost.total_cost.toFixed(4)}</div>
                <div class="stat-sub">In: $${cost.input_cost.toFixed(4)} / Out: $${cost.output_cost.toFixed(4)}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Duration</div>
                <div class="stat-value">${duration}</div>
                <div class="stat-sub">${traceData.start_time ? new Date(traceData.start_time).toLocaleString() : "N/A"}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Tools Used</div>
                <div class="stat-value">${Object.keys(analysisData.tool_call_counts).length}</div>
                <div class="stat-sub">${Object.values(analysisData.tool_call_counts).reduce((a, b) => a + b, 0)} total calls</div>
            </div>
        `;

        renderToolChart();
        renderTokensBarChart();
    }

    function computeTotalDuration() {
        let ms;
        if (traceData.start_time && traceData.end_time) {
            ms = new Date(traceData.end_time) - new Date(traceData.start_time);
        } else {
            ms = traceData.iterations.reduce((sum, it) => sum + (it.duration_ms || 0), 0);
        }
        if (ms === 0) return "N/A";
        if (ms < 1000) return `${ms}ms`;
        if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
        if (ms < 3600000) return `${(ms / 60000).toFixed(1)}m`;
        if (ms < 86400000) {
            const h = Math.floor(ms / 3600000);
            const m = Math.floor((ms % 3600000) / 60000);
            return `${h}h ${m}m`;
        }
        const d = Math.floor(ms / 86400000);
        const h = Math.floor((ms % 86400000) / 3600000);
        const m = Math.floor((ms % 3600000) / 60000);
        return `${d}d ${h}h ${m}m`;
    }

    function renderToolChart() {
        const ctx = document.getElementById("chart-tools").getContext("2d");
        const counts = analysisData.tool_call_counts;

        // Sort by count descending, keep top 7, merge rest into "Other"
        const sorted = Object.entries(counts).sort((a, b) => b[1] - a[1]);
        let labels, values;
        if (sorted.length > 8) {
            const top = sorted.slice(0, 7);
            const otherSum = sorted.slice(7).reduce((sum, [_, v]) => sum + v, 0);
            labels = [...top.map(([k]) => k), "Other"];
            values = [...top.map(([_, v]) => v), otherSum];
        } else {
            labels = sorted.map(([k]) => k);
            values = sorted.map(([_, v]) => v);
        }

        const palette = [
            "#7c3aed", "#3b82f6", "#10b981", "#f59e0b", "#ef4444",
            "#ec4899", "#06b6d4", "#84cc16", "#f97316", "#8b5cf6",
        ];

        new Chart(ctx, {
            type: "doughnut",
            data: {
                labels: labels,
                datasets: [{
                    data: values,
                    backgroundColor: palette.slice(0, labels.length),
                    borderColor: "transparent",
                    borderWidth: 0,
                }],
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        position: "right",
                        labels: { color: "#94a3b8", font: { size: 11 } },
                    },
                },
            },
        });
    }

    function scrollToIteration(idx) {
        document.querySelector('[data-tab="timeline"]').click();
        setTimeout(function () {
            var card = document.querySelector('[data-index="' + idx + '"]');
            if (card) card.scrollIntoView({ behavior: "smooth", block: "center" });
        }, 300);
    }
    window.scrollToIteration = scrollToIteration;

    function renderTokensBarChart() {
        const ctx = document.getElementById("chart-tokens").getContext("2d");
        let iterations = traceData.iterations;

        if (iterations.length > 100) {
            const step = Math.ceil(iterations.length / 100);
            iterations = iterations.filter((_, i) => i % step === 0);
        }

        new Chart(ctx, {
            type: "bar",
            data: {
                labels: iterations.map((it) => `#${it.index}`),
                datasets: [{
                    label: "Tokens",
                    data: iterations.map((it) => it.token_usage.total_tokens),
                    backgroundColor: "rgba(124, 58, 237, 0.6)",
                    borderColor: "#7c3aed",
                    borderWidth: 1,
                    borderRadius: 4,
                }],
            },
            options: {
                responsive: true,
                plugins: { legend: { display: false } },
                scales: {
                    x: { ticks: { color: "#64748b", maxTicksLimit: 20 }, grid: { color: "rgba(63,63,95,0.3)" } },
                    y: { ticks: { color: "#64748b" }, grid: { color: "rgba(63,63,95,0.3)" } },
                },
                onHover: (event, elements) => {
                    event.native.target.style.cursor = elements.length > 0 ? 'pointer' : 'default';
                },
                onClick: function (event, elements) {
                    if (elements.length > 0) {
                        var idx = iterations[elements[0].index].index;
                        scrollToIteration(idx);
                    }
                },
            },
        });
    }

    function renderContextChart() {
        const ctx = document.getElementById("chart-context").getContext("2d");
        const utilization = analysisData.context_utilization;
        const labels = utilization.map((_, i) => `#${i}`);
        const percentData = utilization.map((v) => Math.min(v * 100, 100));
        const maxUtil = Math.max(...utilization) * 100;
        const yMax = maxUtil <= 100 ? 100 : 100;

        const overflowIndices = [];
        utilization.forEach((v, i) => {
            if (v > 1.0) overflowIndices.push(i);
        });

        const overflowAnnotation = overflowIndices.length > 0
            ? `<div class="context-overflow-note">⚠️ Context exceeded 100% at iteration #${overflowIndices[0]} — compaction likely active (${overflowIndices.length} iterations above limit)</div>`
            : "";

        const chartContainer = document.getElementById("chart-context").closest(".chart-card") || document.getElementById("chart-context").parentElement;
        const existingNote = chartContainer.querySelector(".context-overflow-note");
        if (existingNote) existingNote.remove();
        if (overflowAnnotation) {
            chartContainer.insertAdjacentHTML("beforeend", overflowAnnotation);
        }

        new Chart(ctx, {
            type: "line",
            data: {
                labels: labels,
                datasets: [
                    {
                        label: "Context Utilization %",
                        data: percentData,
                        borderColor: "#7c3aed",
                        backgroundColor: "rgba(124, 58, 237, 0.1)",
                        fill: true,
                        tension: 0.3,
                        pointRadius: utilization.length > 50 ? 0 : 3,
                        pointBackgroundColor: "#a78bfa",
                    },
                    {
                        label: "80% Threshold",
                        data: utilization.map(() => 80),
                        borderColor: "rgba(239, 68, 68, 0.7)",
                        borderDash: [8, 4],
                        borderWidth: 2,
                        pointRadius: 0,
                        fill: false,
                    },
                ],
            },
            options: {
                responsive: true,
                plugins: {
                    legend: { labels: { color: "#94a3b8" } },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const idx = context.dataIndex;
                                const actual = (utilization[idx] * 100).toFixed(1);
                                const tokens = (traceData.iterations[idx] && traceData.iterations[idx].token_usage)
                                    ? traceData.iterations[idx].token_usage.prompt_tokens
                                    : 0;
                                if (context.datasetIndex === 0) {
                                    return `Iteration #${idx}: ${actual}% (${formatNumber(tokens)} prompt tokens)`;
                                }
                                return context.dataset.label;
                            }
                        }
                    }
                },
                scales: {
                    x: { ticks: { color: "#64748b", maxTicksLimit: 30 }, grid: { color: "rgba(63,63,95,0.3)" } },
                    y: {
                        min: 0,
                        max: yMax,
                        ticks: { color: "#64748b", callback: (v) => v + "%" },
                        grid: { color: "rgba(63,63,95,0.3)" },
                    },
                },
                onClick: function (event, elements) {
                    if (elements.length > 0 && elements[0].datasetIndex === 0) {
                        scrollToIteration(elements[0].index);
                    }
                },
            },
        });

        // Add context metrics below chart
        let metricsEl = chartContainer.querySelector('.context-metrics');
        if (!metricsEl) {
            metricsEl = document.createElement('div');
            metricsEl.className = 'context-metrics';
            chartContainer.appendChild(metricsEl);
        }

        const nonZero = utilization.filter(v => v > 0);
        const peak = nonZero.length > 0 ? Math.max(...nonZero) * 100 : 0;
        const avg = nonZero.length > 0 ? (nonZero.reduce((a, b) => a + b, 0) / nonZero.length) * 100 : 0;
        const overThreshold = nonZero.filter(v => v > 0.8).length;

        metricsEl.innerHTML = `
            <div class="context-metric">
                <span class="context-metric-label">Peak Utilization</span>
                <span class="context-metric-value" style="color: ${peak > 80 ? '#ef4444' : '#10b981'}">${peak.toFixed(1)}%</span>
            </div>
            <div class="context-metric">
                <span class="context-metric-label">Average</span>
                <span class="context-metric-value">${avg.toFixed(1)}%</span>
            </div>
            <div class="context-metric">
                <span class="context-metric-label">Above 80% Threshold</span>
                <span class="context-metric-value">${overThreshold} iterations</span>
            </div>
            <div class="context-metric">
                <span class="context-metric-label">Data Points</span>
                <span class="context-metric-value">${nonZero.length} / ${utilization.length}</span>
            </div>
        `;
    }

    function renderTimeline() {
        const container = document.getElementById("timeline-container");
        const timeline = analysisData.timeline;

        const totalIterations = traceData.iterations.length;
        const shownIterations = timeline.length;
        let timelineHeader = '';
        if (shownIterations < totalIterations) {
            timelineHeader = `<div class="timeline-header-note">${shownIterations} of ${totalIterations} iterations shown (${totalIterations - shownIterations} empty iterations hidden)</div>`;
        }

        // Calculate max tokens for color gradient
        const maxTokens = Math.max(...timeline.map(item => item.tokens), 1);

        container.innerHTML = timelineHeader + timeline
            .map((item) => {
                const toolChips = item.tool_names
                    .map((t) => `<span class="chip">${escapeHtml(t)}</span>`)
                    .join("");
                const errorChip = item.has_error ? '<span class="chip chip-error">error</span>' : "";
                const thinkPreview = item.thinking_preview
                    ? `<div class="thinking-preview">${escapeHtml(item.thinking_preview)}${item.thinking_preview.length >= 80 ? "..." : ""}</div>`
                    : "";

                // Token-based border color
                const ratio = item.tokens / maxTokens;
                let borderColor;
                if (ratio < 0.3) borderColor = '#10b981';
                else if (ratio < 0.6) borderColor = '#7c3aed';
                else if (ratio < 0.8) borderColor = '#f59e0b';
                else borderColor = '#ef4444';

                return `
                <div class="timeline-item ${item.has_error ? "has-error" : ""}" data-index="${item.index}">
                    <div class="timeline-card" style="border-left-color: ${borderColor}">
                        <div class="timeline-card-header">
                            <span class="iter-index">Iteration ${item.index}</span>
                            <span class="iter-tokens">${formatNumber(item.tokens)} tokens${item.duration_ms ? ` / ${item.duration_ms}ms` : ""}</span>
                        </div>
                        ${thinkPreview}
                        <div class="tool-chips">${toolChips}${errorChip}</div>
                        <div class="timeline-detail" id="detail-${item.index}"></div>
                    </div>
                </div>`;
            })
            .join("");

        container.querySelectorAll(".timeline-card").forEach((card) => {
            card.addEventListener("click", () => {
                const idx = card.closest(".timeline-item").dataset.index;
                toggleTimelineDetail(parseInt(idx));
            });
        });
    }

    async function toggleTimelineDetail(index) {
        const el = document.getElementById(`detail-${index}`);
        if (el.classList.contains("expanded")) {
            el.classList.remove("expanded");
            return;
        }

        try {
            const data = await fetchJSON(`/api/iteration/${index}`);
            let html = "";

            if (data.think) {
                html += '<div class="detail-section"><div class="detail-section-title">Thinking</div>';
                html += `<pre>${escapeHtml(data.think)}</pre></div>`;
            }

            if (data.tool_calls.length > 0) {
                html += '<div class="detail-section"><div class="detail-section-title">Tool Calls</div>';
                data.tool_calls.forEach((tc) => {
                    let resultStr = typeof tc.result === "string" ? tc.result : JSON.stringify(tc.result, null, 2);
                    const maxLen = 500;
                    let truncated = false;
                    if (resultStr && resultStr.length > maxLen) {
                        resultStr = resultStr.substring(0, maxLen);
                        truncated = true;
                    }
                    const resultHtml = tc.result
                        ? `<div class="tool-result"><pre>${escapeHtml(resultStr)}${truncated ? '\n...(truncated)' : ''}</pre></div>`
                        : '';
                    html += `<div class="tool-result-card">
                        <div class="tool-name">${escapeHtml(tc.name)}${tc.duration_ms ? ` <span class="tool-duration">(${tc.duration_ms}ms)</span>` : ""}</div>
                        <div class="tool-args"><pre>${escapeHtml(JSON.stringify(tc.arguments, null, 2))}</pre></div>
                        ${resultHtml}
                    </div>`;
                });
                html += '</div>';
            }

            if (data.error) {
                html += '<div class="detail-section"><div class="detail-section-title">Error</div>';
                html += `<pre style="color:var(--error)">${escapeHtml(data.error)}</pre></div>`;
            }

            if (!html) {
                html = `<p style="color:var(--text-dim);font-style:italic">No detailed content available for this iteration.</p>`;
            }

            // Always show token info
            html += `<div class="tool-duration" style="margin-top:0.5rem">Tokens: ${formatNumber(data.token_usage?.total_tokens || 0)}</div>`;

            el.innerHTML = html;
            el.classList.add("expanded");
        } catch (err) {
            el.innerHTML = `<p style="color:var(--error)">Failed to load: ${err.message}</p>`;
            el.classList.add("expanded");
        }
    }

    let iterationsPage = 0;
    const ITEMS_PER_PAGE = 50;

    function renderIterationsTable() {
        requestAnimationFrame(() => {
        const iterations = traceData.iterations;
        const totalPages = Math.ceil(iterations.length / ITEMS_PER_PAGE);
        const start = iterationsPage * ITEMS_PER_PAGE;
        const end = Math.min(start + ITEMS_PER_PAGE, iterations.length);
        const pageItems = iterations.slice(start, end);

        const tbody = document.querySelector("#iterations-table tbody");
        tbody.innerHTML = pageItems.map((it) => {
            const toolNames = it.tool_calls.map((tc) => tc.name).join(", ");
            return `<tr data-index="${it.index}">
                <td>${it.index}</td>
                <td>${escapeHtml(toolNames) || "<em style='color:var(--text-dim)'>none</em>"}</td>
                <td>${formatNumber(it.token_usage.total_tokens)}</td>
                <td>${it.duration_ms != null ? it.duration_ms + "ms" : "—"}</td>
                <td class="${it.error ? "status-err" : "status-ok"}">${it.error ? "Error" : "OK"}</td>
            </tr>`;
        }).join("");

        // Pagination controls
        let paginationEl = document.getElementById("iterations-pagination");
        if (!paginationEl) {
            paginationEl = document.createElement("div");
            paginationEl.id = "iterations-pagination";
            paginationEl.className = "pagination";
            document.querySelector("#iterations-table").parentElement.appendChild(paginationEl);
        }

        if (totalPages > 1) {
            paginationEl.innerHTML = `
                <button class="page-btn" onclick="changeIterationsPage(-1)" ${iterationsPage === 0 ? "disabled" : ""}>&#8592; Prev</button>
                <span class="page-info">Page ${iterationsPage + 1} of ${totalPages} (${iterations.length} iterations)</span>
                <button class="page-btn" onclick="changeIterationsPage(1)" ${iterationsPage >= totalPages - 1 ? "disabled" : ""}>Next &#8594;</button>
            `;
        } else {
            paginationEl.innerHTML = "";
        }

        // Row click handlers
        tbody.querySelectorAll("tr").forEach((row) => {
            row.addEventListener("click", () => {
                showIterationDetail(parseInt(row.dataset.index));
            });
        });

        document.querySelectorAll("#iterations-table th").forEach((th) => {
            th.addEventListener("click", () => sortTable(th.dataset.sort));
        });
        });
    }

    window.changeIterationsPage = function (delta) {
        const totalPages = Math.ceil(traceData.iterations.length / ITEMS_PER_PAGE);
        iterationsPage = Math.max(0, Math.min(totalPages - 1, iterationsPage + delta));
        renderIterationsTable();
    };

    let currentSort = { field: null, asc: true };

    function sortTable(field) {
        if (currentSort.field === field) {
            currentSort.asc = !currentSort.asc;
        } else {
            currentSort.field = field;
            currentSort.asc = true;
        }

        const iterations = [...traceData.iterations];
        iterations.sort((a, b) => {
            let va, vb;
            switch (field) {
                case "index": va = a.index; vb = b.index; break;
                case "tools": va = a.tool_calls.length; vb = b.tool_calls.length; break;
                case "tokens": va = a.token_usage.total_tokens; vb = b.token_usage.total_tokens; break;
                case "duration": va = a.duration_ms || 0; vb = b.duration_ms || 0; break;
                case "error": va = a.error ? 1 : 0; vb = b.error ? 1 : 0; break;
                default: return 0;
            }
            return currentSort.asc ? va - vb : vb - va;
        });

        traceData.iterations = iterations;
        renderIterationsTable();
        updateSortIndicators();
    }

    function updateSortIndicators() {
        document.querySelectorAll('#iterations-table th').forEach(th => {
            th.textContent = th.textContent.replace(/ [▲▼]$/, '');
            if (th.dataset.sort === currentSort.field) {
                th.textContent += currentSort.asc ? ' ▲' : ' ▼';
            }
        });
    }

    async function showIterationDetail(index) {
        const el = document.getElementById("iteration-detail");
        try {
            const data = await fetchJSON(`/api/iteration/${index}`);
            let html = `<h3>Iteration ${data.index}</h3>`;

            html += `<div class="section">
                <div class="section-title">Token Usage</div>
                <p>Prompt: ${formatNumber(data.token_usage.prompt_tokens)} | Completion: ${formatNumber(data.token_usage.completion_tokens)} | Total: ${formatNumber(data.token_usage.total_tokens)}</p>
            </div>`;

            if (data.think) {
                html += `<div class="section">
                    <div class="section-title">Thinking</div>
                    <pre>${escapeHtml(data.think)}</pre>
                </div>`;
            }

            if (data.tool_calls.length > 0) {
                html += `<div class="section"><div class="section-title">Tool Calls</div>`;
                data.tool_calls.forEach((tc) => {
                    html += `<div class="tool-result-card">
                        <div class="tool-name">${escapeHtml(tc.name)}${tc.duration_ms ? ` <span class="tool-duration">(${tc.duration_ms}ms)</span>` : ""}</div>
                        <pre>${escapeHtml(JSON.stringify(tc.arguments, null, 2))}</pre>
                        ${tc.result ? `<pre>${escapeHtml(typeof tc.result === "string" ? tc.result : JSON.stringify(tc.result, null, 2))}</pre>` : ""}
                    </div>`;
                });
                html += "</div>";
            }

            if (data.error) {
                html += `<div class="section">
                    <div class="section-title">Error</div>
                    <pre style="color:var(--error)">${escapeHtml(data.error)}</pre>
                </div>`;
            }

            el.innerHTML = html;
            el.classList.add("visible");
        } catch (err) {
            el.innerHTML = `<p style="color:var(--error)">Failed to load: ${err.message}</p>`;
            el.classList.add("visible");
        }
    }

    function escapeHtml(str) {
        if (!str) return "";
        return str
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
    }

    function setupTimelineSearch() {
        const input = document.getElementById("timeline-search");
        const countEl = document.getElementById("search-count");
        const clearBtn = document.getElementById("search-clear");
        const hideZeroCheckbox = document.getElementById("hide-zero-tokens");
        if (!input || !countEl) return;

        let debounceTimer = null;

        function filterTimeline() {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(function () {
                const query = input.value.trim().toLowerCase();
                const items = document.querySelectorAll("#timeline-container .timeline-item");
                let shown = 0;
                const total = items.length;

                items.forEach(function (item) {
                    let visible = true;

                    if (query) {
                        const text = item.textContent.toLowerCase();
                        if (text.indexOf(query) === -1) {
                            visible = false;
                        }
                    }

                    if (visible && hideZeroCheckbox && hideZeroCheckbox.checked) {
                        const tokensText = item.querySelector(".iter-tokens");
                        if (tokensText && tokensText.textContent.match(/^0 tokens/)) {
                            visible = false;
                        }
                    }

                    if (visible) {
                        item.classList.remove("search-hidden");
                        shown++;
                    } else {
                        item.classList.add("search-hidden");
                    }
                });

                if (query || (hideZeroCheckbox && hideZeroCheckbox.checked)) {
                    countEl.textContent = "Showing " + shown + " of " + total + " iterations";
                } else {
                    countEl.textContent = "";
                }
            }, 300);
        }

        input.addEventListener("input", function () {
            if (clearBtn) {
                clearBtn.style.display = input.value ? 'block' : 'none';
            }
            filterTimeline();
        });

        if (clearBtn) {
            clearBtn.addEventListener("click", function () {
                input.value = '';
                clearBtn.style.display = 'none';
                input.dispatchEvent(new Event('input'));
            });
        }

        if (hideZeroCheckbox) {
            hideZeroCheckbox.addEventListener("change", function () {
                filterTimeline();
            });
        }
    }

    function setupBackToTop() {
        const btn = document.getElementById('back-to-top');
        window.addEventListener('scroll', () => {
            btn.classList.toggle('visible', window.scrollY > 300);
        });
        btn.addEventListener('click', () => {
            window.scrollTo({ top: 0, behavior: 'smooth' });
        });
    }

    function setupKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            if (e.target.tagName === 'INPUT') return;
            const tabs = ['overview', 'timeline', 'context', 'iterations', 'diagnostics'];
            if (e.key >= '1' && e.key <= '5') {
                const tabName = tabs[parseInt(e.key) - 1];
                const tab = document.querySelector(`[data-tab="${tabName}"]`);
                if (tab) tab.click();
            }
        });
    }

    function setupStatCardNavigation() {
        const cards = document.querySelectorAll('.stat-card');
        cards.forEach((card, i) => {
            if (i === 1) {
                card.style.cursor = 'pointer';
                card.addEventListener('click', () => {
                    document.querySelector('[data-tab="iterations"]').click();
                });
            }
            if (i === 5) {
                card.style.cursor = 'pointer';
                card.addEventListener('click', () => {
                    document.querySelector('[data-tab="timeline"]').click();
                });
            }
        });
    }

    async function renderDiagnostics() {
        const container = document.getElementById('diagnostics-container');
        try {
            const data = await fetchJSON('/api/diagnose');
            let html = '';

            // Summary card at top
            const summaryClass = data.findings.length === 0 ? 'diag-healthy' : 'diag-warning';
            html += `<div class="diag-summary ${summaryClass}">
                <h3>${data.findings.length === 0 ? '✓' : '⚠'} ${data.summary}</h3>
                <div class="diag-stats">
                    <span>Input/Output ratio: <strong>${data.stats.input_output_ratio}:1</strong></span>
                    <span>Input tokens: <strong>${data.stats.input_pct}%</strong> of total</span>
                    <span>Compaction events: <strong>${data.stats.compaction_count}</strong></span>
                </div>
            </div>`;

            // Findings section - grouped by category
            if (data.findings.length > 0) {
                const grouped = {};
                data.findings.forEach(f => {
                    if (!grouped[f.category]) grouped[f.category] = [];
                    grouped[f.category].push(f);
                });

                const categoryLabels = {
                    'context_pressure': { label: 'Context Pressure', icon: '📊', color: '#f59e0b' },
                    'retry_loop': { label: 'Retry Loops', icon: '🔄', color: '#ef4444' },
                    'cost_hotspot': { label: 'Cost Hotspots', icon: '💰', color: '#f97316' },
                    'token_efficiency': { label: 'Token Efficiency', icon: '📉', color: '#8b5cf6' },
                    'idle_gap': { label: 'Idle Gaps', icon: '⏸', color: '#06b6d4' },
                    'error': { label: 'Errors', icon: '❌', color: '#ef4444' },
                };

                html += '<h3 class="diag-section-title">Findings</h3>';
                html += '<div class="diag-findings">';

                for (const [category, findings] of Object.entries(grouped)) {
                    const meta = categoryLabels[category] || { label: category, icon: '•', color: '#94a3b8' };
                    html += `<div class="diag-category">
                        <div class="diag-category-header" style="border-left-color: ${meta.color}">
                            <span class="diag-category-icon">${meta.icon}</span>
                            <span class="diag-category-label">${meta.label}</span>
                            <span class="diag-category-count">${findings.length}</span>
                        </div>
                        <div class="diag-category-items">`;

                    // Show first 5, collapse rest
                    const show = findings.slice(0, 5);
                    const rest = findings.slice(5);

                    show.forEach(f => {
                        const iterLink = f.iteration != null
                            ? `<span class="diag-iter-link" onclick="scrollToIteration(${f.iteration})">Iteration #${f.iteration}</span>`
                            : '';
                        html += `<div class="diag-item diag-${f.severity}">
                            <span class="diag-severity">${f.severity}</span>
                            ${iterLink}
                            <span class="diag-message">${escapeHtml(f.message)}</span>
                        </div>`;
                    });

                    if (rest.length > 0) {
                        const catId = category.replace(/[^a-z]/g, '');
                        html += `<div class="diag-more" id="more-${catId}" onclick="document.getElementById('hidden-${catId}').style.display='block'; this.style.display='none'">&#9660; Show ${rest.length} more</div>`;
                        html += `<div id="hidden-${catId}" style="display:none">`;
                        rest.forEach(f => {
                            const iterLink = f.iteration != null
                                ? `<span class="diag-iter-link" onclick="scrollToIteration(${f.iteration})">Iteration #${f.iteration}</span>`
                                : '';
                            html += `<div class="diag-item diag-${f.severity}">
                                <span class="diag-severity">${f.severity}</span>
                                ${iterLink}
                                <span class="diag-message">${escapeHtml(f.message)}</span>
                            </div>`;
                        });
                        html += '</div>';
                    }

                    html += '</div></div>';
                }
                html += '</div>';
            }

            // Recommendations section
            if (data.recommendations.length > 0) {
                html += '<h3 class="diag-section-title">Recommendations</h3>';
                html += '<div class="diag-recommendations">';

                // Deduplicate: group similar tool recommendations
                const seen = new Set();
                const uniqueRecs = [];
                data.recommendations.forEach(r => {
                    const key = r.message.substring(0, 50);
                    if (!seen.has(key)) {
                        seen.add(key);
                        uniqueRecs.push(r);
                    }
                });

                uniqueRecs.slice(0, 10).forEach((r) => {
                    const savings = r.estimated_savings
                        ? `<span class="diag-savings">${escapeHtml(r.estimated_savings)}</span>`
                        : '';
                    html += `<div class="diag-rec">
                        <span class="diag-rec-num">P${r.priority}</span>
                        <span class="diag-rec-message">${escapeHtml(r.message)}</span>
                        ${savings}
                    </div>`;
                });

                if (uniqueRecs.length > 10) {
                    html += `<div class="diag-more">${uniqueRecs.length - 10} more recommendations...</div>`;
                }

                html += '</div>';
            }

            container.innerHTML = html;
        } catch (err) {
            container.innerHTML = `<div class="stat-card"><p style="color:var(--error)">Failed to load diagnostics: ${err.message}</p>
                <button onclick="renderDiagnostics()" class="page-btn" style="margin-top:1rem">Retry</button></div>`;
        }
    }
    window.renderDiagnostics = renderDiagnostics;

    // Session Sidebar
    function shortenPath(path) {
        const parts = path.split('/');
        if (parts.length > 3) {
            return '.../' + parts.slice(-2).join('/');
        }
        return path;
    }

    function formatTokens(n) {
        if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
        if (n >= 1000) return (n / 1000).toFixed(0) + 'K';
        return n.toString();
    }

    async function loadSessions() {
        try {
            const sessions = await fetchJSON('/api/sessions');
            const container = document.getElementById('sidebar-sessions');
            if (!container) return;

            if (sessions.length === 0) {
                container.innerHTML = '<div style="padding:1rem;color:var(--text-dim);text-align:center">No sessions found</div>';
                return;
            }

            container.innerHTML = sessions.map(function (s) {
                var name = s.project_name || shortenPath(s.path);
                var tokens = formatTokens(s.estimated_tokens);
                var date = s.last_modified ? new Date(s.last_modified).toLocaleDateString() : '';
                var model = s.model || '';

                return '<div class="session-item ' + (s.is_current ? 'active' : '') + '" data-path="' + escapeHtml(s.path) + '" data-name="' + escapeHtml(name.toLowerCase()) + '">'
                    + '<span class="session-item-name">' + escapeHtml(name) + '</span>'
                    + '<div class="session-item-meta">'
                    + '<span>' + escapeHtml(model) + '</span>'
                    + '<span>' + tokens + ' tokens</span>'
                    + '<span>' + date + '</span>'
                    + '</div></div>';
            }).join('');

            // Click handlers
            container.querySelectorAll('.session-item').forEach(function (item) {
                item.addEventListener('click', function () {
                    var path = item.getAttribute('data-path');
                    if (!item.classList.contains('active')) {
                        switchSession(path);
                    }
                });
            });
        } catch (err) {
            console.error('Failed to load sessions:', err);
        }
    }

    function setupSidebar() {
        var sidebar = document.getElementById('sidebar');
        var overlay = document.getElementById('sidebar-overlay');
        var toggle = document.getElementById('sidebar-toggle');
        var closeBtn = document.getElementById('sidebar-close');
        var searchInput = document.getElementById('sidebar-search-input');

        function openSidebar() {
            sidebar.classList.add('open');
            overlay.classList.add('visible');
        }

        function closeSidebar() {
            sidebar.classList.remove('open');
            overlay.classList.remove('visible');
        }

        if (toggle) toggle.addEventListener('click', openSidebar);
        if (closeBtn) closeBtn.addEventListener('click', closeSidebar);
        if (overlay) overlay.addEventListener('click', closeSidebar);

        // Keyboard: S to open, Escape to close
        document.addEventListener('keydown', function (e) {
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
            if (e.key === 's' || e.key === 'S') {
                if (!e.ctrlKey && !e.metaKey) {
                    e.preventDefault();
                    openSidebar();
                }
            }
            if (e.key === 'Escape') {
                closeSidebar();
            }
        });

        // Search/filter
        if (searchInput) {
            searchInput.addEventListener('input', function () {
                var query = searchInput.value.toLowerCase();
                document.querySelectorAll('.session-item').forEach(function (item) {
                    var name = item.getAttribute('data-name') || '';
                    item.classList.toggle('hidden', query !== '' && name.indexOf(query) === -1);
                });
            });
        }
    }

    async function switchSession(path) {
        try {
            var res = await fetch('/api/switch', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({path: path})
            });
            var data = await res.json();
            if (data.success) {
                location.reload();
            } else {
                alert('Failed to switch: ' + (data.error || 'Unknown error'));
            }
        } catch (err) {
            alert('Failed to switch session: ' + err.message);
        }
    }

    document.addEventListener("DOMContentLoaded", init);
})();
