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
    const trialIds = new Set(trials.map(t => `trial-${t.id}`));
    // Remove elements not in current session (handles session switching)
    Array.from(trialsContainer.children).forEach(el => {
        const trialEl = el.id?.startsWith('trial-') ? el : el.querySelector('[id^="trial-"]');
        if (trialEl && !trialIds.has(trialEl.id)) el.remove();
    });

    trials.forEach((trial, idx) => {
        const existing = document.getElementById(`trial-${trial.id}`);
        const needsDivider = idx < trials.length - 1;
        const hasDivider = existing?.parentElement !== trialsContainer; // wrapped in container = has divider
        // Skip only if completed AND divider state unchanged
        if (existing && trial.status === 'completed' && needsDivider === hasDivider) return;
        // Remove existing (and its container if any)
        if (existing) {
            const toRemove = existing.parentElement === trialsContainer ? existing : existing.parentElement;
            toRemove.remove();
        }
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
 * Supports new sectioned layout with Pipeline Runs and Single Sessions sections.
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

    // Remove empty state if present
    const emptyState = sessionList.querySelector('.empty-state');
    if (emptyState) emptyState.remove();

    const pipelineBadgeHtml = pipelineType ? this.generatePipelineBadge(pipelineType) : '';

    if (groupId) {
        // Add to Pipeline Runs section
        let pipelineSection = sessionList.querySelector('.pipeline-runs-section');
        if (!pipelineSection) {
            pipelineSection = this._createPipelineRunsSection();
            sessionList.prepend(pipelineSection);
        }

        let groupContainer = document.getElementById(`session-group-${groupId}`);
        if (!groupContainer) {
            const pipelineRunsContainer = pipelineSection.querySelector('.pipeline-runs-container');
            const groupEl = this._createGroupElement(groupId, groupName, pipelineType);
            pipelineRunsContainer.appendChild(groupEl);
            groupContainer = document.getElementById(`session-group-${groupId}`);

            // Update pipeline runs badge count
            this._updateSectionBadge(pipelineSection, '.pipeline-runs-container > .group-item');
        }

        const sessionItem = this._createSessionItem(sessionId, questionData, statusText, pipelineBadgeHtml, false);
        sessionItem.classList.add('session-details');
        sessionItem.setAttribute('data-session-id', sessionId);
        groupContainer.prepend(sessionItem);

        // Update session count in group
        const countEl = document.getElementById(`group-session-count-${groupId}`);
        if (countEl) {
            const currentCount = groupContainer.children.length;
            countEl.textContent = currentCount;
        }
    } else {
        // Add to Single Sessions section
        let singleSection = sessionList.querySelector('.single-sessions-section');
        if (!singleSection) {
            singleSection = this._createSingleSessionsSection();
            // Insert after pipeline runs section if it exists, otherwise prepend
            const pipelineSection = sessionList.querySelector('.pipeline-runs-section');
            if (pipelineSection) {
                pipelineSection.after(singleSection);
            } else {
                sessionList.prepend(singleSection);
            }
        }

        const singleSessionsContainer = singleSection.querySelector('.single-sessions-container');
        const selectAllRow = singleSessionsContainer.querySelector('.select-all-row');
        const sessionItem = this._createSessionItem(sessionId, questionData, statusText, pipelineBadgeHtml, true);

        if (selectAllRow) {
            selectAllRow.after(sessionItem);
        } else {
            singleSessionsContainer.prepend(sessionItem);
        }

        // Update single sessions badge count
        this._updateSectionBadge(singleSection, '.single-sessions-container > .session-item');
    }
};

/**
 * Create Pipeline Runs section element using template
 * @private
 */
window.BenchmarkSessionUI._createPipelineRunsSection = function() {
    return BenchmarkUtils.renderTemplate('tpl-pipeline-runs-section', {});
};

/**
 * Create Single Sessions section element using template
 * @private
 */
window.BenchmarkSessionUI._createSingleSessionsSection = function() {
    return BenchmarkUtils.renderTemplate('tpl-single-sessions-section', {});
};

/**
 * Create a group element for pipeline runs using template
 * @private
 */
window.BenchmarkSessionUI._createGroupElement = function(groupId, groupName, pipelineType) {
    const groupEl = BenchmarkUtils.renderTemplate('tpl-pipeline-group-item', {
        '.group-select-checkbox': { attrs: { 'data-group-id': groupId } },
        '.group-name-display': { text: groupName, attrs: { 'data-group-id': groupId } },
        '.group-session-count': { attrs: { id: `group-session-count-${groupId}` } },
        '.session-list-inner': { attrs: { id: `session-group-${groupId}` } },
        '.view-group-results-btn': { attrs: { 'data-group-id': groupId, 'data-pipeline-type': pipelineType || null } },
        '.continue-group-btn': { attrs: { 'data-group-id': groupId, 'data-pipeline-type': pipelineType || null } },
        '.rename-group-btn': { attrs: { 'data-group-id': groupId } },
        '.delete-group-btn': { attrs: { 'data-group-id': groupId } }
    });
    return groupEl;
};

/**
 * Create a session item element using template
 * @private
 */
window.BenchmarkSessionUI._createSessionItem = function(sessionId, questionData, statusText, pipelineBadgeHtml, hasCheckbox) {
    const templateId = hasCheckbox ? 'tpl-session-item-checkbox' : 'tpl-session-item-plain';
    const item = BenchmarkUtils.renderTemplate(templateId, {
        '.session-id-label': { text: `Session #${sessionId}` },
        '.session-time': { text: statusText },
        '.session-question': { text: questionData.question || '' },
        '.pipeline-badge-container': { html: pipelineBadgeHtml }
    });

    if (hasCheckbox) {
        const checkbox = item.querySelector('.session-checkbox');
        if (checkbox) {
            checkbox.value = sessionId;
            checkbox.setAttribute('data-session-id', sessionId);
        }
        const details = item.querySelector('.session-details');
        if (details) {
            details.setAttribute('data-session-id', sessionId);
        }
    } else {
        item.setAttribute('data-session-id', sessionId);
    }

    return item;
};

/**
 * Update section badge count
 * @private
 */
window.BenchmarkSessionUI._updateSectionBadge = function(section, itemSelector) {
    const badge = section.querySelector('.section-count');
    if (badge) {
        const count = section.querySelectorAll(itemSelector).length;
        badge.textContent = count;
    }
};

/**
 * Update statistics UI for multi-turn benchmarks.
 * Uses backend API for metrics calculation and renders all groups dynamically.
 * @param {Array} results - Array of result objects.
 * @param {string} groupName - Name of the group/run.
 * @param {function} loadSessionCallback - Callback to load a session.
 * @param {string} pipelineType - Pipeline type for filtering applicable metrics.
 */
window.BenchmarkSessionUI.updateStatsUI = function(results, groupName, loadSessionCallback, pipelineType) {
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

    // Call the backend metrics API with pipeline_type
    BenchmarkAPI.post(BenchmarkUrls.metrics.calculate, { results, pipeline_type: pipelineType })
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
 * Show placeholder message in metrics container using template
 * @private
 */
window.BenchmarkSessionUI._showMetricsPlaceholder = function(message) {
    const container = document.getElementById('metrics-groups-container');
    if (container) {
        container.innerHTML = '';
        const placeholder = BenchmarkUtils.renderTemplate('tpl-metrics-placeholder', {
            '.placeholder-message': { text: message }
        });
        container.appendChild(placeholder);
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

    // Render each group as foldable details element
    for (const group of sortedGroups) {
        const groupMetrics = metricsByGroup[group.key];
        if (!groupMetrics || groupMetrics.length === 0) continue;

        // Create foldable group container
        const details = document.createElement('details');
        details.className = 'metrics-group-details';
        details.id = `metrics-group-${group.key}`;
        details.open = true; // Open by default

        // Group header (clickable summary)
        const summary = document.createElement('summary');
        summary.textContent = group.label;
        details.appendChild(summary);

        // Metrics row
        const metricsRow = document.createElement('div');
        metricsRow.className = 'row g-4';

        // Render metrics for this group
        for (const metric of groupMetrics) {
            const card = this._createMetricCardElement(metric, group.key);
            metricsRow.appendChild(card);
        }

        details.appendChild(metricsRow);
        container.appendChild(details);
    }
};

/**
 * Create a metric card element
 * @private
 */
window.BenchmarkSessionUI._createMetricCardElement = function(metric, groupKey) {
    return BenchmarkUtils.createMetricCardWithColor(metric);
};

/**
 * Helper to set element text content
 * @private
 */
window.BenchmarkSessionUI._setElementText = function(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
};
