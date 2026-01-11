/**
 * Leaderboard Module
 * Handles fetching and displaying benchmark leaderboard data
 *
 * Two modes:
 * 1. Global mode (pipelineType = null): Table layout on home page, shows all pipelines
 * 2. Fixed mode (pipelineType set): Compact card layout in sidebar, filtered to one pipeline
 */

window.BenchmarkLeaderboard = (function() {
    let fixedPipelineType = null;   // Fixed filter for baseline pages (null = global mode)
    let filterPipelineType = null;  // User-selected filter in global mode
    let isGlobalMode = true;        // Whether we're in global mode (home page)
    let leaderboardData = [];
    let activeRunId = null;

    /**
     * Initialize the leaderboard
     * @param {string|null} pipelineType - If set, locks to this pipeline type (baseline pages)
     *                                     If null, shows global leaderboard with filter (home page)
     */
    function init(pipelineType) {
        fixedPipelineType = pipelineType;
        isGlobalMode = (pipelineType === null);
        filterPipelineType = null;
        setupEventListeners();
        loadLeaderboard();
    }

    /**
     * Setup event listeners for leaderboard controls
     */
    function setupEventListeners() {
        // Refresh button
        const refreshBtn = document.getElementById('refresh-leaderboard-btn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => loadLeaderboard());
        }

        // Sort dropdown
        const sortSelect = document.getElementById('leaderboard-sort');
        if (sortSelect) {
            sortSelect.addEventListener('change', () => loadLeaderboard());
        }

        // Pipeline filter dropdown (only in global mode)
        const pipelineFilter = document.getElementById('leaderboard-pipeline-filter');
        if (pipelineFilter) {
            pipelineFilter.addEventListener('change', (e) => {
                filterPipelineType = e.target.value || null;
                loadLeaderboard();
            });
        }

        // Complete only checkbox
        const completeOnlyCheckbox = document.getElementById('leaderboard-complete-only');
        if (completeOnlyCheckbox) {
            completeOnlyCheckbox.addEventListener('change', () => renderLeaderboard());
        }
    }

    /**
     * Load leaderboard data from API
     */
    function loadLeaderboard() {
        const entriesContainer = document.getElementById('leaderboard-entries');
        const sortSelect = document.getElementById('leaderboard-sort');

        if (!entriesContainer) return;

        // Show loading state
        if (isGlobalMode) {
            entriesContainer.innerHTML = `
                <tr>
                    <td colspan="9" class="text-center text-muted py-4">
                        <span class="spinner-border spinner-border-sm me-2"></span>Loading...
                    </td>
                </tr>
            `;
        } else {
            entriesContainer.innerHTML = `
                <div class="text-center text-muted py-3">
                    <span class="spinner-border spinner-border-sm me-2"></span>Loading...
                </div>
            `;
        }

        const params = {
            sort_by: sortSelect ? sortSelect.value : 'accuracy',
            order: 'desc'
        };

        // Determine pipeline type filter
        if (fixedPipelineType) {
            params.pipeline_type = fixedPipelineType;
        } else if (filterPipelineType) {
            params.pipeline_type = filterPipelineType;
        }

        const url = BenchmarkUrls.leaderboard.getFiltered(params);

        BenchmarkAPI.get(url)
            .then(data => {
                if (data.status === 'ok') {
                    leaderboardData = data.runs || [];
                    renderLeaderboard();
                } else {
                    showError(data.message || 'Failed to load leaderboard');
                }
            })
            .catch(err => {
                console.error('Leaderboard load error:', err);
                showError('Failed to load leaderboard');
            });
    }

    /**
     * Render leaderboard entries
     */
    function renderLeaderboard() {
        const entriesContainer = document.getElementById('leaderboard-entries');
        const completeOnlyCheckbox = document.getElementById('leaderboard-complete-only');

        if (!entriesContainer) return;

        let filteredData = leaderboardData;

        // Filter by complete only if checkbox is checked
        if (completeOnlyCheckbox && completeOnlyCheckbox.checked) {
            filteredData = leaderboardData.filter(run => run.is_complete);
        }

        if (filteredData.length === 0) {
            if (isGlobalMode) {
                entriesContainer.innerHTML = `
                    <tr>
                        <td colspan="9" class="text-center text-muted py-5">
                            <i class="bi bi-trophy" style="font-size: 2rem; opacity: 0.5;"></i>
                            <p class="mt-2 mb-0">No completed runs found</p>
                            <p class="text-muted small">Run a full pipeline to see results here</p>
                        </td>
                    </tr>
                `;
            } else {
                entriesContainer.innerHTML = `
                    <div class="text-center text-muted py-3">
                        <i class="bi bi-trophy" style="font-size: 1.25rem; opacity: 0.5;"></i>
                        <p class="mt-1 mb-0 small">No runs found</p>
                    </div>
                `;
            }
            return;
        }

        if (isGlobalMode) {
            entriesContainer.innerHTML = filteredData.map((run, index) => renderTableRow(run, index + 1)).join('');
            // Add click handlers for table rows
            entriesContainer.querySelectorAll('tr[data-run-id]').forEach(row => {
                row.addEventListener('click', () => {
                    selectRun(row.dataset.runId, row.dataset.pipelineType);
                });
            });
        } else {
            entriesContainer.innerHTML = filteredData.map((run, index) => renderCompactCard(run, index + 1)).join('');
            // Add click handlers for cards
            entriesContainer.querySelectorAll('.leaderboard-entry').forEach(entry => {
                entry.addEventListener('click', () => {
                    selectRun(entry.dataset.runId, entry.dataset.pipelineType);
                });
            });
        }
    }

    /**
     * Render a table row for global mode (home page)
     */
    function renderTableRow(run, rank) {
        const rankClass = rank === 1 ? 'gold' : rank === 2 ? 'silver' : rank === 3 ? 'bronze' : 'default';
        const accuracyClass = run.accuracy >= 70 ? 'accuracy-high' : run.accuracy >= 40 ? 'accuracy-medium' : 'accuracy-low';

        const pipelineBadges = {
            'vanilla_llm': { text: 'LLM', class: 'bg-primary' },
            'rag': { text: 'RAG', class: 'bg-success' },
            'vanilla_agent': { text: 'Agent', class: 'bg-info' },
            'browser_agent': { text: 'Browser', class: 'bg-warning text-dark' }
        };
        const badge = pipelineBadges[run.pipeline_type] || { text: run.pipeline_type, class: 'bg-secondary' };

        const modelName = run.model || 'Unknown';
        const date = run.created_at ? new Date(run.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : '-';

        const formatTokens = (tokens) => {
            if (tokens >= 1000000) return (tokens / 1000000).toFixed(1) + 'M';
            if (tokens >= 1000) return Math.round(tokens / 1000) + 'K';
            return tokens;
        };

        const isActive = activeRunId === run.run_id;

        return `
            <tr data-run-id="${run.run_id}" data-pipeline-type="${run.pipeline_type}" class="${isActive ? 'active' : ''}">
                <td class="text-center">
                    <span class="leaderboard-rank-badge ${rankClass}">${rank}</span>
                </td>
                <td>
                    <span class="fw-medium" title="${BenchmarkHelpers.escapeHtml(run.name)}">${BenchmarkHelpers.escapeHtml(run.name)}</span>
                </td>
                <td>
                    <span class="badge pipeline-badge ${badge.class}">${badge.text}</span>
                </td>
                <td>
                    <span class="model-text" title="${BenchmarkHelpers.escapeHtml(modelName)}">${BenchmarkHelpers.escapeHtml(modelName)}</span>
                </td>
                <td class="text-center">${run.session_count}</td>
                <td class="text-center ${accuracyClass}">${run.accuracy.toFixed(1)}%</td>
                <td class="text-center">${run.avg_trials.toFixed(1)}</td>
                <td class="text-end text-muted">${formatTokens(run.total_tokens)}</td>
                <td class="text-end text-muted small">${date}</td>
            </tr>
        `;
    }

    /**
     * Render a compact card for sidebar (baseline pages)
     */
    function renderCompactCard(run, rank) {
        const rankClass = rank === 1 ? 'gold' : rank === 2 ? 'silver' : rank === 3 ? 'bronze' : 'default';
        const accuracyClass = run.accuracy >= 70 ? 'high' : run.accuracy >= 40 ? 'medium' : 'low';

        const modelName = run.model || 'Unknown';
        const shortModel = modelName.length > 15 ? modelName.substring(0, 13) + '...' : modelName;
        const date = run.created_at ? new Date(run.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : '';

        const formatTokens = (tokens) => {
            if (tokens >= 1000000) return (tokens / 1000000).toFixed(1) + 'M';
            if (tokens >= 1000) return Math.round(tokens / 1000) + 'K';
            return tokens;
        };

        const isActive = activeRunId === run.run_id;

        return `
            <div class="leaderboard-entry${isActive ? ' active' : ''}" data-run-id="${run.run_id}" data-pipeline-type="${run.pipeline_type}">
                <div class="d-flex align-items-center gap-2">
                    <div class="leaderboard-rank ${rankClass}">${rank}</div>
                    <div class="flex-grow-1 min-width-0">
                        <div class="fw-medium small text-truncate" title="${BenchmarkHelpers.escapeHtml(run.name)}">${BenchmarkHelpers.escapeHtml(run.name)}</div>
                        <div class="d-flex align-items-center gap-2 text-muted" style="font-size: 0.7rem;">
                            <span title="${BenchmarkHelpers.escapeHtml(modelName)}">${BenchmarkHelpers.escapeHtml(shortModel)}</span>
                            <span>${run.session_count}Q</span>
                            <span>${run.avg_trials.toFixed(1)}t</span>
                            <span>${formatTokens(run.total_tokens)}</span>
                        </div>
                    </div>
                    <div class="text-end">
                        <div class="leaderboard-accuracy ${accuracyClass}">${run.accuracy.toFixed(0)}%</div>
                        <div style="font-size: 0.65rem; color: #999;">${date}</div>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Select a run to view its details
     */
    function selectRun(runId, pipelineType) {
        activeRunId = parseInt(runId);

        // Update active state in UI
        if (isGlobalMode) {
            document.querySelectorAll('#leaderboard-entries tr').forEach(row => {
                row.classList.toggle('active', parseInt(row.dataset.runId) === activeRunId);
            });
        } else {
            document.querySelectorAll('.leaderboard-entry').forEach(entry => {
                entry.classList.toggle('active', parseInt(entry.dataset.runId) === activeRunId);
            });
        }

        // In global mode (home page), redirect to the appropriate baseline page
        if (isGlobalMode) {
            const pipelineUrls = {
                'vanilla_llm': '/benchmark/vanilla_llm/',
                'rag': '/benchmark/rag/',
                'vanilla_agent': '/benchmark/vanilla_agent/',
                'browser_agent': '/benchmark/browser_agent/'
            };
            const baseUrl = pipelineUrls[pipelineType] || '/benchmark/vanilla_llm/';
            window.location.href = `${baseUrl}?run_id=${runId}`;
            return;
        }

        // In fixed mode (baseline pages), use MultiTurnPage to load the run
        if (window.BenchmarkUtils && window.BenchmarkUtils.MultiTurnPage && window.BenchmarkUtils.MultiTurnPage.loadRun) {
            window.BenchmarkUtils.MultiTurnPage.loadRun(runId, pipelineType);
        } else {
            const viewBtn = document.querySelector(`.view-group-results-btn[data-group-id="${runId}"]`);
            if (viewBtn) {
                viewBtn.click();
            }
        }
    }

    /**
     * Show error message
     */
    function showError(message) {
        const entriesContainer = document.getElementById('leaderboard-entries');
        if (!entriesContainer) return;

        if (isGlobalMode) {
            entriesContainer.innerHTML = `
                <tr>
                    <td colspan="9" class="text-center text-danger py-4">
                        <i class="bi bi-exclamation-circle me-2"></i>${BenchmarkHelpers.escapeHtml(message)}
                    </td>
                </tr>
            `;
        } else {
            entriesContainer.innerHTML = `
                <div class="text-center text-danger py-3 small">
                    <i class="bi bi-exclamation-circle me-1"></i>${BenchmarkHelpers.escapeHtml(message)}
                </div>
            `;
        }
    }

    /**
     * Get current leaderboard data
     */
    function getData() {
        return leaderboardData;
    }

    /**
     * Refresh leaderboard (public method)
     */
    function refresh() {
        loadLeaderboard();
    }

    return {
        init,
        refresh,
        getData,
        loadLeaderboard
    };
})();
