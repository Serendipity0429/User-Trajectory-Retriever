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

    // Pipeline badge configuration with icons
    const PIPELINE_BADGES = {
        'vanilla_llm': { text: 'LLM', class: 'pipeline-llm', icon: 'bi-chat-square-text' },
        'rag': { text: 'RAG', class: 'pipeline-rag', icon: 'bi-search' },
        'vanilla_agent': { text: 'Agent', class: 'pipeline-agent', icon: 'bi-robot' },
        'browser_agent': { text: 'Browser', class: 'pipeline-browser', icon: 'bi-globe' },
        'human': { text: 'Human', class: 'pipeline-human', icon: 'bi-person-fill' }
    };

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
     * Format token count for display
     */
    function formatTokens(tokens) {
        if (tokens >= 1000000) return (tokens / 1000000).toFixed(1) + 'M';
        if (tokens >= 1000) return Math.round(tokens / 1000) + 'K';
        return tokens || '-';
    }

    /**
     * Load leaderboard data from API
     */
    function loadLeaderboard() {
        const entriesContainer = document.getElementById('leaderboard-entries');
        const sortSelect = document.getElementById('leaderboard-sort');

        if (!entriesContainer) return;

        // Show loading state using template
        entriesContainer.innerHTML = '';
        const loadingTpl = isGlobalMode ? 'tpl-leaderboard-loading-table' : 'tpl-leaderboard-loading-card';
        const loadingEl = BenchmarkUtils.renderTemplate(loadingTpl, {});
        entriesContainer.appendChild(loadingEl);

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

        // Clear container
        entriesContainer.innerHTML = '';

        if (filteredData.length === 0) {
            const emptyTpl = isGlobalMode ? 'tpl-leaderboard-empty-table' : 'tpl-leaderboard-empty-card';
            const emptyEl = BenchmarkUtils.renderTemplate(emptyTpl, {});
            entriesContainer.appendChild(emptyEl);
            return;
        }

        if (isGlobalMode) {
            filteredData.forEach((run, index) => {
                const row = renderTableRow(run, index + 1);
                entriesContainer.appendChild(row);
            });
        } else {
            filteredData.forEach((run, index) => {
                const card = renderCompactCard(run, index + 1);
                entriesContainer.appendChild(card);
            });
        }
    }

    /**
     * Render a table row for global mode (home page)
     */
    function renderTableRow(run, rank) {
        const isHuman = run.is_human || run.pipeline_type === 'human';
        const rankClass = rank === 1 ? 'gold' : rank === 2 ? 'silver' : rank === 3 ? 'bronze' : 'default';
        
        // Accuracy colors
        let accuracyClass = 'accuracy-low';
        if (run.accuracy >= 70) accuracyClass = 'accuracy-high';
        else if (run.accuracy >= 40) accuracyClass = 'accuracy-medium';

        const badge = PIPELINE_BADGES[run.pipeline_type] || { text: run.pipeline_type, class: 'bg-secondary', icon: 'bi-question-circle' };
        const modelName = run.model || 'Unknown';
        const date = run.created_at ? new Date(run.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : '-';
        const isActive = activeRunId === run.run_id;

        const rowClasses = [];
        if (isActive) rowClasses.push('active');
        if (isHuman) rowClasses.push('table-light', 'human-baseline-row');

        const row = BenchmarkUtils.renderTemplate('tpl-leaderboard-table-row', {
            '.leaderboard-row': {
                attrs: {
                    'data-run-id': run.run_id,
                    'data-pipeline-type': run.pipeline_type
                },
                addClass: rowClasses.join(' ')
            },
            '.leaderboard-rank-badge': {
                text: rank,
                addClass: rankClass
            },
            '.run-name': {
                html: (isHuman ? '<i class="bi bi-person-fill me-1"></i>' : '') + BenchmarkHelpers.escapeHtml(run.name),
                attrs: { title: run.name }
            },
            '.pipeline-badge': {
                html: (badge.icon ? `<i class="bi ${badge.icon}"></i>` : '') + badge.text,
                addClass: badge.class
            },
            '.model-text': {
                text: modelName,
                attrs: { title: modelName }
            },
            '.session-count': { text: run.session_count },
            '.accuracy-text': {
                text: run.accuracy.toFixed(1) + '%',
                addClass: accuracyClass
            },
            '.avg-trials': { text: run.avg_trials ? run.avg_trials.toFixed(1) : '-' },
            '.tokens-cell': { text: formatTokens(run.total_tokens) },
            '.date-cell': { text: date }
        });

        // Add click handler
        row.addEventListener('click', () => {
            selectRun(run.run_id, run.pipeline_type);
        });

        return row;
    }

    /**
     * Render a compact card for sidebar (baseline pages)
     */
    function renderCompactCard(run, rank) {
        const isHuman = run.is_human || run.pipeline_type === 'human';
        const rankClass = rank === 1 ? 'gold' : rank === 2 ? 'silver' : rank === 3 ? 'bronze' : 'default';
        
        // Accuracy colors
        let accuracyClass = 'accuracy-low';
        if (run.accuracy >= 70) accuracyClass = 'accuracy-high';
        else if (run.accuracy >= 40) accuracyClass = 'accuracy-medium';

        const modelName = run.model || 'Unknown';
        const shortModel = modelName.length > 15 ? modelName.substring(0, 13) + '...' : modelName;
        const date = run.created_at ? new Date(run.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : '';
        const isActive = activeRunId === run.run_id;

        // Build details HTML
        const detailsHtml = `
            <span class="text-secondary" title="Model: ${BenchmarkHelpers.escapeHtml(modelName)}">${BenchmarkHelpers.escapeHtml(shortModel)}</span>
            <span class="text-secondary ms-2" title="Questions">• ${run.session_count}</span>
        `;

        const card = BenchmarkUtils.renderTemplate('tpl-leaderboard-compact-card', {
            '.leaderboard-entry': {
                attrs: {
                    'data-run-id': run.run_id,
                    'data-pipeline-type': run.pipeline_type
                },
                addClass: isActive ? 'active' : ''
            },
            '.leaderboard-rank': {
                text: rank,
                addClass: rankClass
            },
            '.run-name': {
                text: run.name,
                attrs: { title: run.name }
            },
            '.run-details': { html: detailsHtml },
            '.leaderboard-accuracy': {
                text: run.accuracy.toFixed(0) + '%',
                addClass: accuracyClass
            },
            '.run-date': { text: date }
        });

        // Add click handler
        card.addEventListener('click', () => {
            selectRun(run.run_id, run.pipeline_type);
        });

        return card;
    }

    /**
     * Select a run to view its details
     */
    function selectRun(runId, pipelineType) {
        // Human baselines are not clickable (no detailed view)
        if (pipelineType === 'human' || String(runId).startsWith('human_')) {
            return;
        }

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

        entriesContainer.innerHTML = '';
        const errorTpl = isGlobalMode ? 'tpl-leaderboard-error-table' : 'tpl-leaderboard-error-card';
        const errorEl = BenchmarkUtils.renderTemplate(errorTpl, {
            '.error-message': { text: message }
        });
        entriesContainer.appendChild(errorEl);
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