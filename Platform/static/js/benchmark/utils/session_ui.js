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
    if (total === 0) return;

    const correct = results.filter(r => r.correct === true).length;
    const incorrect = results.filter(r => r.correct === false).length;
    const error = results.filter(r => r.correct !== true && r.correct !== false).length;
    const accuracy = (correct / total) * 100;

    // Basic Stats
    this._setElementText('stats-accuracy', `${accuracy.toFixed(2)}%`);
    this._setElementText('stats-correct-count', correct);
    this._setElementText('stats-incorrect-count', incorrect);
    this._setElementText('stats-error-count', error);

    // Rule-based Accuracy & Coherence
    const correctRule = results.filter(r => r.is_correct_rule === true).length;
    const ruleAccuracy = (correctRule / total) * 100;
    this._setElementText('stats-rule-accuracy', `${ruleAccuracy.toFixed(2)}%`);

    const avgCoherence = results.reduce((sum, r) => sum + (r.coherence || 0), 0) / total;
    this._setElementText('stats-coherence', `${(avgCoherence * 100).toFixed(2)}%`);

    // Average trials
    const totalTrials = results.reduce((sum, r) => sum + (r.trials || 0), 0);
    const avgTrials = totalTrials / total;
    this._setElementText('stats-avg-trials-all', avgTrials.toFixed(2));

    const successResults = results.filter(r => r.correct === true);
    const successTrials = successResults.reduce((sum, r) => sum + (r.trials || 0), 0);
    const avgSuccessTrials = successResults.length > 0 ? successTrials / successResults.length : 0;
    this._setElementText('stats-avg-trials-success', avgSuccessTrials.toFixed(2));

    // First try success
    const firstTrySuccess = results.filter(r => r.initial_correct === true).length;
    const firstTryRate = (firstTrySuccess / total) * 100;
    this._setElementText('stats-first-try-success', `${firstTryRate.toFixed(2)}%`);

    // Correction Gain
    const correctionGain = accuracy - firstTryRate;
    this._setElementText('stats-correction-gain', `+${correctionGain.toFixed(2)}%`);

    // Give up rate
    const giveUp = results.filter(r => r.correct === false).length;
    const giveUpRate = (giveUp / total) * 100;
    this._setElementText('stats-give-up-rate', `${giveUpRate.toFixed(2)}%`);

    // Self-Correction Rate
    const initialFailures = results.filter(r => r.initial_correct === false);
    const selfCorrected = initialFailures.filter(r => r.correct === true);
    const selfRecoveryRate = initialFailures.length > 0 ? (selfCorrected.length / initialFailures.length) * 100 : 0;
    const scEl = document.getElementById('stats-self-correction-rate');
    if (scEl) {
        scEl.textContent = `${selfRecoveryRate.toFixed(2)}%`;
        scEl.title = `${selfCorrected.length} corrected out of ${initialFailures.length} initial failures`;
    }

    // Error Rate
    const errorRate = (error / total) * 100;
    this._setElementText('stats-error-rate', `${errorRate.toFixed(2)}%`);

    // Behavioral Analysis Metrics
    this._renderBehavioralMetrics(results, firstTryRate, selfRecoveryRate, correctionGain);

    // Baseline-Specific Metrics
    this._renderSpecificMetrics(results);
};

/**
 * Helper to set element text content
 * @private
 */
window.BenchmarkSessionUI._setElementText = function(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
};

/**
 * Render behavioral analysis metrics
 * @private
 */
window.BenchmarkSessionUI._renderBehavioralMetrics = function(results, firstTryRate, selfRecoveryRate, correctionGain) {
    const behavioralRow = document.getElementById('behavioral-metrics-row');
    if (!behavioralRow) return;

    behavioralRow.innerHTML = '';

    // One-Shot Success
    behavioralRow.appendChild(BenchmarkUtils.createMetricCard({
        value: `${firstTryRate.toFixed(2)}%`,
        label: 'One-Shot Success',
        description: 'Solved on Turn 1',
        color: 'success'
    }));

    // Recovery Rate
    behavioralRow.appendChild(BenchmarkUtils.createMetricCard({
        value: `${selfRecoveryRate.toFixed(2)}%`,
        label: 'Recovery Rate',
        description: 'Failures Fixed Later',
        color: 'primary'
    }));

    // Stubbornness Index
    const stubbornSessions = results.filter(r => r.stubborn_score !== undefined && r.stubborn_score !== null && r.stubborn_score > 0);
    if (stubbornSessions.length > 0) {
        const totalStub = stubbornSessions.reduce((sum, r) => sum + Number(r.stubborn_score), 0);
        const avgStub = totalStub / stubbornSessions.length;

        behavioralRow.appendChild(BenchmarkUtils.createMetricCard({
            value: `${(avgStub * 100).toFixed(2)}%`,
            label: 'Stubbornness Index',
            description: 'Repetition on Failure',
            color: 'secondary'
        }));
    }

    // Correction Gain
    behavioralRow.appendChild(BenchmarkUtils.createMetricCard({
        value: `+${correctionGain.toFixed(2)}%`,
        label: 'Correction Gain',
        description: 'Multi-turn Lift',
        color: 'purple'
    }));
};

/**
 * Render baseline-specific metrics
 * @private
 */
window.BenchmarkSessionUI._renderSpecificMetrics = function(results) {
    const specificContainer = document.getElementById('specific-metrics-container');
    const specificRow = document.getElementById('specific-metrics-row');
    if (!specificContainer || !specificRow) return;

    specificRow.innerHTML = '';
    let hasSpecific = false;

    // Avg Search Count
    const searchCountSessions = results.filter(r => r.search_count !== undefined);
    if (searchCountSessions.length > 0) {
        const totalSearch = searchCountSessions.reduce((sum, r) => sum + Number(r.search_count), 0);
        const avgSearch = totalSearch / searchCountSessions.length;

        specificRow.appendChild(BenchmarkUtils.createMetricCard({
            value: avgSearch.toFixed(2),
            label: 'Search Queries',
            description: 'Avg. Queries per Session',
            color: 'info'
        }));
        hasSpecific = true;
    }

    // Avg Query Shift
    const shiftSessions = results.filter(r => r.query_shift !== undefined && r.query_shift !== null);
    if (shiftSessions.length > 0) {
        const totalShift = shiftSessions.reduce((sum, r) => sum + Number(r.query_shift), 0);
        const avgShift = totalShift / shiftSessions.length;

        specificRow.appendChild(BenchmarkUtils.createMetricCard({
            value: avgShift.toFixed(3),
            label: 'Query Diversity',
            description: 'Avg. Query Shift Distance',
            color: 'warning'
        }));
        hasSpecific = true;

        this._setElementText('stats-avg-query-shift', avgShift.toFixed(3));
    }

    specificContainer.style.display = hasSpecific ? 'block' : 'none';
};
