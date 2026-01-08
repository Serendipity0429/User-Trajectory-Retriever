/**
 * Session UI utilities
 * Handles session rendering, statistics UI, and pipeline badge generation
 */

window.BenchmarkSessionUI = window.BenchmarkSessionUI || {};

/**
 * Render a multi-turn session, including question, ground truths, and trials.
 * @param {object} session - The session object.
 * @param {Array} trials - Array of trial objects for the session.
 * @param {object} [options] - Optional settings.
 */
window.BenchmarkSessionUI.renderSession = function(session, trials, options = {}) {
    const {
        sessionTrials,
        sessionContainerId = 'session-container',
        noSessionSelectedId = 'no-session-selected',
        pipelineType = 'vanilla_llm'
    } = options;

    // Update external sessionTrials reference if provided
    if (sessionTrials) {
        sessionTrials.length = 0;
        sessionTrials.push(...trials);
    }

    document.getElementById('session-header').textContent = `Session #${session.id}`;
    document.getElementById('session-question').textContent = session.question;

    const gtContainer = document.getElementById('session-ground-truths');
    gtContainer.innerHTML = '';
    gtContainer.appendChild(BenchmarkUtils.BenchmarkRenderer.renderGroundTruthsList(session.ground_truths));

    const trialsContainer = document.getElementById('trials-container');
    trialsContainer.innerHTML = '';
    trials.forEach(trial => {
        trialsContainer.appendChild(BenchmarkUtils.BenchmarkRenderer.renderTrial(trial, session.is_completed, trials.length, session.max_retries, session.question, pipelineType));
    });

    document.getElementById(sessionContainerId).style.display = 'block';
    document.getElementById(noSessionSelectedId).style.display = 'none';
};

/**
 * Generate pipeline badge HTML matching the Django template tag.
 * @param {string} pipelineType - The pipeline type.
 * @returns {string} HTML string for the pipeline badge.
 */
window.BenchmarkSessionUI.generatePipelineBadge = function(pipelineType) {
    const config = BenchmarkPipelineConfig.get(pipelineType);

    return `
<span class="d-inline-flex align-items-center ${config.textClass} bg-white border border-${config.color} border-opacity-25 rounded px-2 py-0 ms-1 shadow-sm" style="font-size: 0.75em; height: 20px;">
    <i class="bi ${config.icon} me-1"></i>
    <span class="fw-medium text-uppercase" style="letter-spacing: 0.5px; font-size: 0.9em;">${config.label}</span>
</span>
`;
};

/**
 * Add a new session to the session list UI.
 * @param {string} sessionListId - The ID of the session list container.
 * @param {string} sessionId - The session ID.
 * @param {object} questionData - Data about the question.
 * @param {function} selectAllHandler - Function to handle select all checkbox change.
 * @param {string} groupId - The group ID (optional).
 * @param {string} groupName - The group name (optional).
 * @param {string} statusText - The status text to display.
 * @param {string} pipelineType - The pipeline type (optional).
 */
window.BenchmarkSessionUI.addNewSessionToList = function(sessionListId, sessionId, questionData, selectAllHandler, groupId = null, groupName = null, statusText = 'Now', pipelineType = null) {
    const sessionList = document.getElementById(sessionListId);
    if (!sessionList) return;

    // Check if session already exists
    const existingCheckbox = document.querySelector(`.session-checkbox[value="${sessionId}"]`);
    const existingDetails = document.querySelector(`.session-details[data-session-id="${sessionId}"]`);

    if (existingCheckbox || existingDetails) {
        const sessionDetails = existingDetails || document.querySelector(`.session-details[data-session-id="${sessionId}"]`);
        if (sessionDetails) {
            const timeEl = sessionDetails.querySelector('small.text-muted');
            if (timeEl) {
                timeEl.textContent = statusText;
            }
        }
        return;
    }

    // If this is the first session ever, remove "no sessions" and add select-all header
    if (document.querySelector('.no-sessions')) {
        const noSessions = document.querySelector('.no-sessions');
        if (noSessions) noSessions.remove();

        // Only create if it doesn't exist
        if (!document.getElementById('select-all-container')) {
            const selectAllContainer = document.createElement('div');
            selectAllContainer.className = 'list-group-item bg-light';
            selectAllContainer.id = 'select-all-container';
            selectAllContainer.innerHTML = `
                <input class="form-check-input" type="checkbox" id="select-all-checkbox">
                <label class="form-check-label ms-2" for="select-all-checkbox">Select All</label>`;
            sessionList.prepend(selectAllContainer);
            const cb = document.getElementById('select-all-checkbox');
            if (cb && selectAllHandler) cb.addEventListener('change', selectAllHandler);
        }
    }

    const newSessionItem = document.createElement('div');
    newSessionItem.className = 'list-group-item d-flex align-items-center session-item-container';

    let checkboxHtml = '';
    let detailsMargin = 'ms-3';

    if (!groupId) {
        checkboxHtml = `<input class="form-check-input session-checkbox" type="checkbox" value="${sessionId}" data-session-id="${sessionId}">`;
    } else {
        detailsMargin = '';
    }

    const pipelineBadgeHtml = pipelineType ? this.generatePipelineBadge(pipelineType) : '';

    newSessionItem.innerHTML = `
        ${checkboxHtml}
        <div class="${detailsMargin} flex-grow-1 session-details" data-session-id="${sessionId}" style="cursor: pointer;">
            <div class="d-flex w-100 justify-content-between">
                <h6 class="mb-1 small fw-bold">Session #${sessionId}</h6>
                <small class="text-muted" style="font-size: 0.7rem;">${statusText}</small>
            </div>
            <p class="mb-1 small text-muted text-truncate">${questionData.question || ''}</p>
            ${pipelineBadgeHtml}
        </div>`;

    if (groupId) {
        let groupContainer = document.getElementById(`session-group-${groupId}`);
        if (!groupContainer) {
            const groupEl = document.createElement('div');
            groupEl.className = 'list-group-item';
            groupEl.innerHTML = `
                <details open>
                    <summary class="fw-bold" style="cursor: pointer;">
                        <i class="bi bi-collection me-1"></i>
                        ${groupName}
                        <small class="text-muted" id="group-session-count-${groupId}">(1 sessions)</small>
                    </summary>
                    <div class="list-group list-group-flush mt-2" id="session-group-${groupId}">
                    </div>
                </details>
            `;
            const selectAllDiv = document.getElementById('select-all-container');
            if (selectAllDiv) {
                selectAllDiv.after(groupEl);
            } else {
                sessionList.prepend(groupEl);
            }
            groupContainer = document.getElementById(`session-group-${groupId}`);
        }
        newSessionItem.classList.add("ps-4");
        groupContainer.prepend(newSessionItem);

        // Update session count
        const countEl = document.getElementById(`group-session-count-${groupId}`);
        if (countEl) {
            const currentCount = groupContainer.children.length;
            countEl.textContent = `(${currentCount} sessions)`;
        }
    } else {
        const selectAllDiv = document.getElementById('select-all-container');
        if (selectAllDiv) {
            selectAllDiv.after(newSessionItem);
        } else {
            sessionList.appendChild(newSessionItem);
        }
    }
};

/**
 * Update statistics UI for multi-turn benchmarks.
 * Uses backend API for metrics calculation and renders all groups dynamically.
 * @param {Array} results - Array of result objects.
 * @param {string} groupName - Name of the group/run.
 * @param {function} loadSessionCallback - Callback to load a session.
 */
window.BenchmarkSessionUI.updateStatsUI = function(results, groupName, loadSessionCallback) {
    const statsBody = document.getElementById('stats-details-tbody');
    if (statsBody) {
        statsBody.innerHTML = '';
        results.forEach((res, idx) => {
            const tr = BenchmarkUtils.BenchmarkRenderer.renderMultiTurnResultRow(res, idx, loadSessionCallback);
            statsBody.appendChild(tr);
        });
    }

    const total = results.length;
    if (total === 0) {
        this._showMetricsPlaceholder('No results to display');
        return;
    }

    // Call the backend metrics API
    BenchmarkAPI.post(BenchmarkUrls.metrics.calculate, { results })
        .then(response => {
            if (response.status !== 'ok') {
                console.error('Metrics calculation failed:', response.message);
                this._showMetricsPlaceholder('Failed to calculate metrics');
                return;
            }
            this._renderAllMetricsFromAPI(response.metrics, response.groups, response.summary);
        })
        .catch(err => {
            console.error('Error fetching metrics:', err);
            this._showMetricsPlaceholder('Error loading metrics');
        });
};

/**
 * Show placeholder message in metrics container
 * @private
 */
window.BenchmarkSessionUI._showMetricsPlaceholder = function(message) {
    const container = document.getElementById('metrics-groups-container');
    if (container) {
        container.innerHTML = `
            <div class="text-center text-muted py-4">
                <i class="bi bi-info-circle me-2"></i>${message}
            </div>
        `;
    }
};

/**
 * Render all metrics organized by groups from API response
 * @private
 */
window.BenchmarkSessionUI._renderAllMetricsFromAPI = function(metrics, groups, summary) {
    const container = document.getElementById('metrics-groups-container');
    if (!container) return;

    // Clear container
    container.innerHTML = '';

    // Sort groups by priority
    const sortedGroups = (groups || []).slice().sort((a, b) => a.priority - b.priority);

    // Organize metrics by group
    const metricsByGroup = {};
    for (const [key, metric] of Object.entries(metrics)) {
        const group = metric.group;
        if (!metricsByGroup[group]) {
            metricsByGroup[group] = [];
        }
        metricsByGroup[group].push(metric);
    }

    // Sort metrics within each group by priority
    for (const group of Object.keys(metricsByGroup)) {
        metricsByGroup[group].sort((a, b) => a.priority - b.priority);
    }

    // Render each group
    for (const group of sortedGroups) {
        const groupMetrics = metricsByGroup[group.key];
        if (!groupMetrics || groupMetrics.length === 0) continue;

        // Create group container
        const groupDiv = document.createElement('div');
        groupDiv.className = 'mb-4';
        groupDiv.id = `metrics-group-${group.key}`;

        // Group header
        const header = document.createElement('h6');
        header.className = 'section-header';
        header.textContent = group.label;
        groupDiv.appendChild(header);

        // Metrics row
        const metricsRow = document.createElement('div');
        metricsRow.className = 'row g-4';

        // Render metrics for this group
        for (const metric of groupMetrics) {
            const card = this._createMetricCardElement(metric, group.key);
            metricsRow.appendChild(card);
        }

        groupDiv.appendChild(metricsRow);
        container.appendChild(groupDiv);
    }
};

/**
 * Create a metric card element based on group and metric type
 * @private
 */
window.BenchmarkSessionUI._createMetricCardElement = function(metric, groupKey) {
    // Special layout for outcome group (horizontal counts)
    if (groupKey === 'outcome' && metric.format_type === 'count') {
        return this._createOutcomeMetricCard(metric);
    }

    // Default card layout
    return BenchmarkUtils.createMetricCardWithColor(metric);
};

/**
 * Create outcome count metric card with appropriate styling
 * @private
 */
window.BenchmarkSessionUI._createOutcomeMetricCard = function(metric) {
    const col = document.createElement('div');
    col.className = 'col-lg-3 col-md-4';

    const color = metric.color || { border: '#6c757d', text: '#495057', bg: '#f8f9fa' };

    // Map metric keys to icons
    const icons = {
        'correct_count': 'bi-check-circle',
        'incorrect_count': 'bi-x-circle',
        'error_count': 'bi-exclamation-triangle'
    };
    const icon = icons[metric.key] || 'bi-circle';

    col.innerHTML = `
        <div class="metric-card" style="border-top: 4px solid ${color.border};">
            <div class="card-body text-center">
                <div class="fw-bold fs-3" style="color: ${color.text};">${metric.formatted}</div>
                <div class="small fw-medium" style="color: ${color.text};">
                    <i class="bi ${icon} me-1"></i>${metric.label}
                </div>
                <div class="small text-muted">${metric.description}</div>
            </div>
        </div>
    `;
    return col;
};

/**
 * Helper to set element text content
 * @private
 */
window.BenchmarkSessionUI._setElementText = function(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
};
