/**
 * Multi-turn Page Controller
 * Handles session management, pipeline execution, and UI interactions
 *
 * Dependencies:
 *   - core.js, renderer.js
 *   - config/pipeline-config.js (for pipeline configurations)
 *   - utils/settings.js, utils/session_ui.js, utils/pipeline_runner.js
 */

window.BenchmarkUtils.MultiTurnPage = (function() {
    // === State ===
    const activePolls = {};
    const trialState = {};
    const trialTraceCache = {};  // Cache for completed trial traces
    let activeGroupId = null;
    let activeSessionId = null;
    let sessionAbortController = null;
    let pipelineController = null;
    let currentPipelineResults = [];
    let currentRunPipelineType = null;
    let sessionRetryTimeout = null;
    let loadSessionDebounceTimer = null;  // Debounce timer for loadSession

    // === Polling Configuration ===
    const POLL_CONFIG = {
        // Interval bounds (ms)
        MIN_INTERVAL: 250,      // Burst mode when active
        BASE_INTERVAL: 500,     // Normal streaming
        IDLE_INTERVAL: 2000,    // When waiting for next step
        MAX_INTERVAL: 5000,     // Maximum backoff
        ERROR_INTERVAL: 10000,  // On network error

        // Timeout settings
        MAX_POLL_TIME: 3 * 60 * 1000,  // 3 minutes max polling time
        STALL_THRESHOLD: 60 * 1000,      // Show warning after 1 min of no changes

        // Backoff settings
        BACKOFF_MULTIPLIER: 1.5,  // Increase interval by 50% on no change
        BURST_RESET_COUNT: 2      // Reset to burst mode after 2 consecutive changes
    };

    // === Polling ===
    function stopPolling(trialId) {
        if (activePolls[trialId]) {
            clearTimeout(activePolls[trialId]);
            delete activePolls[trialId];
        }
        delete trialState[trialId];
    }

    function startPolling(trialId, pipelineType) {
        // SINGLETON PATTERN: If already polling this trial, don't start another
        if (activePolls[trialId]) {
            return;
        }
        const config = BenchmarkPipelineConfig.get(pipelineType);

        // Initialize polling state for this trial
        trialState[trialId] = {
            startTime: Date.now(),
            lastChangeTime: Date.now(),
            lastStepCount: 0,
            lastContentHash: '',
            consecutiveNoChange: 0,
            consecutiveChanges: 0,
            currentInterval: POLL_CONFIG.BASE_INTERVAL,
            stallWarningShown: false
        };

        const poll = () => {
            const state = trialState[trialId];
            if (!state) return;  // Polling was stopped

            const trialDiv = document.getElementById(`trial-${trialId}`);
            if (!trialDiv) {
                stopPolling(trialId);
                return;
            }

            const wrapper = trialDiv.querySelector('.trial-wrapper');
            if (!wrapper) {
                stopPolling(trialId);
                return;
            }

            // Check for max polling time exceeded
            const elapsedTime = Date.now() - state.startTime;
            if (elapsedTime > POLL_CONFIG.MAX_POLL_TIME) {
                stopPolling(trialId);
                // Show timeout warning
                if (!wrapper.querySelector('.trial-timeout-warning')) {
                    const timeoutWarning = document.createElement('div');
                    timeoutWarning.className = 'trial-timeout-warning alert alert-warning mt-3';
                    timeoutWarning.innerHTML = `
                        <strong>Polling Timeout</strong>
                        <p class="mb-0 small">Stopped polling after ${Math.round(POLL_CONFIG.MAX_POLL_TIME / 60000)} minutes.
                        The trial may still be processing. <a href="#" onclick="window.BenchmarkUtils.MultiTurnPage.startPolling(${trialId}, '${pipelineType}'); this.closest('.trial-timeout-warning').remove(); return false;">Resume polling</a></p>
                    `;
                    wrapper.appendChild(timeoutWarning);
                }
                return;
            }

            // Always fetch full trace (cursor=0) and do a smart diff/replace
            BenchmarkAPI.get(`/benchmark/api/sessions/get_trial_trace/${trialId}/?cursor=0`)
                .then(data => {
                    const allSteps = data.trace || [];
                    const trialInfo = data.trial;

                    // Get current bubbles (excluding verdict and indicators)
                    const existingBubbles = Array.from(wrapper.querySelectorAll('.message-bubble'))
                        .filter(b => !b.closest('.trial-verdict-container') && !b.querySelector('.trial-processing-indicator'));

                    const lastStep = allSteps.length > 0 ? allSteps[allSteps.length - 1] : null;
                    const isStreaming = !!(lastStep && lastStep.is_streaming);
                    const existingCount = existingBubbles.length;
                    const verdictContainer = wrapper.querySelector('.trial-verdict-container');
                    const hasNewSteps = allSteps.length > existingCount;

                    // Compute content hash for change detection (step count + last step content length)
                    const contentHash = `${allSteps.length}:${lastStep ? (lastStep.content || '').length : 0}`;
                    const hasContentChange = contentHash !== state.lastContentHash;
                    state.lastContentHash = contentHash;

                    // Update change tracking
                    if (hasContentChange || hasNewSteps) {
                        state.lastChangeTime = Date.now();
                        state.consecutiveNoChange = 0;
                        state.consecutiveChanges++;
                        state.stallWarningShown = false;
                        // Remove stall warning if it was shown
                        wrapper.querySelector('.trial-stall-warning')?.remove();
                    } else {
                        state.consecutiveNoChange++;
                        state.consecutiveChanges = 0;
                    }

                    // Calculate next polling interval dynamically
                    let nextInterval;
                    if (isStreaming && state.consecutiveChanges >= POLL_CONFIG.BURST_RESET_COUNT) {
                        // Burst mode: rapid polling when actively streaming
                        nextInterval = POLL_CONFIG.MIN_INTERVAL;
                    } else if (isStreaming) {
                        // Normal streaming
                        nextInterval = POLL_CONFIG.BASE_INTERVAL;
                    } else if (state.consecutiveNoChange > 0) {
                        // Exponential backoff when no changes
                        nextInterval = Math.min(
                            state.currentInterval * POLL_CONFIG.BACKOFF_MULTIPLIER,
                            POLL_CONFIG.MAX_INTERVAL
                        );
                    } else {
                        // Idle, waiting for next step
                        nextInterval = POLL_CONFIG.IDLE_INTERVAL;
                    }
                    state.currentInterval = nextInterval;

                    // Check for stall condition
                    const timeSinceChange = Date.now() - state.lastChangeTime;
                    if (timeSinceChange > POLL_CONFIG.STALL_THRESHOLD && !state.stallWarningShown) {
                        state.stallWarningShown = true;
                        // Show stall warning (but keep polling)
                        if (!wrapper.querySelector('.trial-stall-warning')) {
                            const stallWarning = document.createElement('div');
                            stallWarning.className = 'trial-stall-warning alert alert-info mt-2 py-2';
                            stallWarning.innerHTML = `<small><i class="bi bi-hourglass-split me-1"></i>Waiting for response... (${Math.round(timeSinceChange / 1000)}s)</small>`;
                            const indicator = wrapper.querySelector('.trial-processing-indicator')?.closest('.message-bubble');
                            if (indicator) indicator.insertAdjacentElement('beforebegin', stallWarning);
                            else wrapper.appendChild(stallWarning);
                        }
                    } else if (state.stallWarningShown && wrapper.querySelector('.trial-stall-warning')) {
                        // Update stall warning time
                        const stallEl = wrapper.querySelector('.trial-stall-warning small');
                        if (stallEl) stallEl.innerHTML = `<i class="bi bi-hourglass-split me-1"></i>Waiting for response... (${Math.round(timeSinceChange / 1000)}s)`;
                    }

                    // Only remove spinner when we have new steps to show (prevents flicker)
                    if (hasNewSteps) {
                        wrapper.querySelectorAll('.trial-processing-indicator').forEach(indicator => {
                            const parent = indicator.closest('.message-bubble');
                            if (parent) parent.remove();
                        });
                        // Append only NEW steps
                        for (let i = existingCount; i < allSteps.length; i++) {
                            const stepEl = BenchmarkUtils.BenchmarkRenderer.renderAgentStep(allSteps[i], i, trialId, trialInfo ? trialInfo.answer : null);
                            if (verdictContainer) verdictContainer.insertAdjacentElement('beforebegin', stepEl);
                            else wrapper.appendChild(stepEl);
                        }
                    }

                    // Update last step if streaming (content may have changed)
                    if (isStreaming && existingCount > 0 && allSteps.length === existingCount && hasContentChange) {
                        const lastBubble = existingBubbles[existingCount - 1];
                        const lastStepEl = BenchmarkUtils.BenchmarkRenderer.renderAgentStep(lastStep, existingCount - 1, trialId, trialInfo ? trialInfo.answer : null);
                        lastBubble.replaceWith(lastStepEl);
                    }

                    // Add processing indicator if still processing and not already present
                    if (trialInfo && trialInfo.status === 'processing' && !wrapper.querySelector('.trial-processing-indicator')) {
                        const indicatorEl = BenchmarkUtils.BenchmarkRenderer.createMessageBubble('assistant', `<div class="d-flex align-items-center trial-processing-indicator"><span class="spinner-border spinner-border-sm text-primary me-2"></span>${config.loadingText}</div>`, '', config.icon);
                        wrapper.appendChild(indicatorEl);
                    }

                    // Handle completion
                    if (trialInfo && (trialInfo.status === 'completed' || trialInfo.status === 'error')) {
                        stopPolling(trialId);

                        // Cache the completed trace for future use
                        if (allSteps.length > 0) {
                            trialTraceCache[trialId] = allSteps;
                        }

                        // Final cleanup: remove all indicators and warnings
                        wrapper.querySelectorAll('.trial-processing-indicator, .trial-stall-warning').forEach(el => {
                            const parent = el.closest('.message-bubble');
                            if (parent) parent.remove();
                            else el.remove();
                        });

                        // Add verdict if completed and not already present
                        if (trialInfo.status === 'completed' && !wrapper.querySelector('.trial-verdict-container')) {
                            const verdictContainer = BenchmarkUtils.BenchmarkRenderer.renderTrialVerdict(trialInfo);
                            if (verdictContainer) wrapper.appendChild(verdictContainer);
                        }
                        // Add error display if trial has error status
                        if (trialInfo.status === 'error' && !wrapper.querySelector('.trial-error-container')) {
                            const errorContainer = document.createElement('div');
                            errorContainer.className = 'trial-error-container alert alert-danger mt-3';
                            errorContainer.innerHTML = `
                                <strong>Trial Error</strong>
                                <p class="mb-0 small">${BenchmarkHelpers.escapeHtml(trialInfo.error || 'An error occurred during this trial.')}</p>
                            `;
                            wrapper.appendChild(errorContainer);
                        }
                        return;
                    }

                    // Schedule next poll with dynamic interval
                    if (activePolls[trialId]) {
                        activePolls[trialId] = setTimeout(poll, nextInterval);
                    }
                })
                .catch(err => {
                    console.error("Polling error:", err);
                    // Exponential backoff on errors, but cap at ERROR_INTERVAL
                    state.currentInterval = Math.min(
                        state.currentInterval * 2,
                        POLL_CONFIG.ERROR_INTERVAL
                    );
                    if (activePolls[trialId]) {
                        activePolls[trialId] = setTimeout(poll, state.currentInterval);
                    }
                });
        };

        // Mark as active and start first poll
        activePolls[trialId] = setTimeout(poll, POLL_CONFIG.MIN_INTERVAL);
    }

    // === Session Helpers ===
    function resetSessionUI() {
        const startBtn = document.getElementById('start-session-btn');
        const stopBtn = document.getElementById('stop-session-btn');
        if (startBtn) startBtn.style.display = 'block';
        if (stopBtn) stopBtn.style.display = 'none';
        BenchmarkSettings.toggleConfigurationInputs(false);
        sessionAbortController = null;
        if (sessionRetryTimeout) {
            clearTimeout(sessionRetryTimeout);
            sessionRetryTimeout = null;
        }
    }

    function loadSession(sessionId, initialTrialId = null, pipelineType = 'vanilla_llm') {
        // Debounce rapid successive calls to prevent redundant renders
        if (loadSessionDebounceTimer) {
            clearTimeout(loadSessionDebounceTimer);
        }

        loadSessionDebounceTimer = setTimeout(() => {
            loadSessionDebounceTimer = null;
            _loadSessionImpl(sessionId, initialTrialId, pipelineType);
        }, 50);  // 50ms debounce - fast enough to feel instant, but prevents burst calls
    }

    // Helper to ensure a trial's final state is rendered after completion
    // This catches any missed updates if polling was behind
    function _ensureTrialRendered(trialId, trialData) {
        const trialDiv = document.getElementById(`trial-${trialId}`);
        if (!trialDiv) return;

        const wrapper = trialDiv.querySelector('.trial-wrapper');
        if (!wrapper) return;

        // Remove any lingering processing indicators
        wrapper.querySelectorAll('.trial-processing-indicator').forEach(indicator => {
            const parent = indicator.closest('.message-bubble');
            if (parent) parent.remove();
        });

        // Add verdict if not present
        if (!wrapper.querySelector('.trial-verdict-container') && trialData) {
            const verdictContainer = BenchmarkUtils.BenchmarkRenderer.renderTrialVerdict(trialData);
            if (verdictContainer) wrapper.appendChild(verdictContainer);
        }
    }

    function _loadSessionImpl(sessionId, initialTrialId = null, pipelineType = 'vanilla_llm') {
        activeSessionId = sessionId;

        BenchmarkAPI.get(BenchmarkUrls.multiTurn.getSession(sessionId))
            .then(data => {
                const sessionPipelineType = data.session?.pipeline_type || pipelineType;
                BenchmarkSessionUI.renderSession(data.session, data.trials, { sessionTrials: [], pipelineType: sessionPipelineType });
                window.sessionTrials = data.trials;

                const whitelist = BenchmarkSettingsConfig.buildWhitelist(sessionPipelineType);
                BenchmarkUtils.BenchmarkRenderer.renderRunConfiguration(data.session.settings_snapshot, whitelist);

                document.getElementById('session-container').style.display = 'block';
                document.getElementById('no-session-selected').style.display = 'none';

                const delBtn = document.getElementById('delete-session-btn');
                if (delBtn) delBtn.style.display = data.session.group_id ? 'none' : 'inline-block';

                if (initialTrialId) {
                    executeTrial(initialTrialId, sessionId, sessionPipelineType);
                } else {
                    const lastTrial = data.trials[data.trials.length - 1];
                    if (lastTrial?.status === 'completed' && lastTrial.is_correct_llm === false && !data.session.is_completed) {
                        if (data.trials.length < data.session.max_retries && sessionAbortController && !sessionAbortController.signal.aborted) {
                            sessionRetryTimeout = setTimeout(() => {
                                if (sessionAbortController && !sessionAbortController.signal.aborted) {
                                    window.retryTrial(lastTrial.id);
                                }
                            }, 1500);
                        } else if (sessionAbortController) {
                            resetSessionUI();
                        }
                    } else if (data.session.is_completed && sessionAbortController) {
                        resetSessionUI();
                    }
                }
            });
    }

    function executeTrial(trialId, sessionId, pipelineType = 'rag') {
        const signal = sessionAbortController?.signal;

        // Load session to show processing trial - this triggers renderTrial which starts polling
        // NOTE: startPolling is called via renderTrial, no need to call it explicitly
        if (sessionId) loadSession(sessionId, null, pipelineType);

        BenchmarkAPI.get(BenchmarkUrls.multiTurn.runTrial(trialId), { signal })
            .then(data => {
                if (data.error) {
                    alert(`Error in trial #${trialId}: ${data.error}`);
                    stopPolling(trialId);
                    if (sessionAbortController) resetSessionUI();
                    return;
                }

                // Stop polling first
                stopPolling(trialId);

                // Ensure final state is rendered - do one final poll to catch any missed updates
                // This is a lightweight check since polling already rendered most of the trace
                _ensureTrialRendered(trialId, data);

                // If incorrect, trigger retry
                if (data.is_correct_llm === false) {
                    // Call retry_session to create new trial
                    BenchmarkAPI.post(BenchmarkUrls.multiTurn.retrySession(trialId), {
                        feedback: 'Incorrect',
                        is_correct: false
                    }, { signal })
                    .then(retryData => {
                        if (retryData.status === 'retrying' && retryData.new_trial_id) {
                            // Recursively execute the new trial
                            executeTrial(retryData.new_trial_id, sessionId, pipelineType);
                        } else if (retryData.status === 'max_retries_reached') {
                            if (sessionAbortController) resetSessionUI();
                        } else if (retryData.status === 'completed') {
                            if (sessionAbortController) resetSessionUI();
                        }
                    })
                    .catch(err => {
                        if (err.name !== 'AbortError') {
                            console.error('Error in retry:', err);
                        }
                        if (sessionAbortController) resetSessionUI();
                    });
                } else {
                    // Correct answer, session complete
                    if (sessionAbortController) resetSessionUI();
                }
            })
            .catch(err => {
                if (err.name !== 'AbortError') {
                    console.error('Network error in trial.', err);
                    // On error, reload session to show current state
                    if (sessionId) loadSession(sessionId, null, pipelineType);
                }
                if (sessionAbortController) resetSessionUI();
            });
    }

    function loadRun(groupId, pipelineType) {
        activeGroupId = groupId;
        const loadRunUrl = BenchmarkUrls.pipeline.loadRun(pipelineType, groupId);

        BenchmarkAPI.get(loadRunUrl).then(data => {
            if (data.error) { alert(data.error); return; }
            currentPipelineResults = data.results;

            const statsContainer = document.getElementById('statistics-container');
            if (statsContainer) statsContainer.style.display = 'block';

            BenchmarkSessionUI.updateStatsUI(data.results, data.group_name, (sid) => {
                document.getElementById('session-container').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                loadSession(sid, null, pipelineType);
            }, pipelineType);

            const whitelist = BenchmarkSettingsConfig.buildWhitelist(pipelineType);
            BenchmarkUtils.BenchmarkRenderer.renderRunConfiguration(data.settings, whitelist);
            if (statsContainer) statsContainer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        });
    }

    // === Pipeline Helpers ===
    function initiatePipelineRun(groupId, pipelineType) {
        currentRunPipelineType = pipelineType;
        const currentPipelineId = BenchmarkHelpers.generateUUID();
        const ui = {
            runBtn: document.getElementById('run-pipeline-btn'),
            stopBtn: document.getElementById('stop-pipeline-btn'),
            progressBar: document.getElementById('pipeline-progress-bar'),
            statusDiv: document.getElementById('pipeline-status'),
            resultsBody: null,
            spinner: null
        };

        document.getElementById('statistics-container').style.display = 'block';
        document.getElementById('stats-details-tbody').innerHTML = '';
        currentPipelineResults = [];
        document.getElementById('pipeline-progress').style.display = 'block';
        document.getElementById('results-header-text').textContent = groupId ? 'Resuming Pipeline Run...' : 'Live Pipeline Results';
        if (ui.statusDiv) ui.statusDiv.textContent = groupId ? 'Initializing resume...' : 'Initializing...';

        const currentLlmSettings = {
            llm_base_url: document.getElementById('llm_base_url').value,
            llm_api_key: document.getElementById('llm_api_key').value,
            llm_model: document.getElementById('llm_model').value,
            max_retries: document.getElementById('max_retries')?.value
        };
        BenchmarkUtils.BenchmarkRenderer.renderRunConfiguration({ llm_settings: currentLlmSettings });

        let preloadedCount = 0;
        let preloadPromise = Promise.resolve();

        if (groupId && groupId !== 'null' && groupId !== 'undefined') {
            ui.statusDiv.textContent = 'Fetching existing results...';
            preloadPromise = BenchmarkAPI.get(BenchmarkUrls.pipeline.loadRun(pipelineType, groupId))
                .then(data => {
                    if (data.results) {
                        currentPipelineResults = data.results;
                        preloadedCount = data.results.length;
                        BenchmarkSessionUI.updateStatsUI(currentPipelineResults, data.group_name || "Current Run", (sid) => {
                            document.getElementById('session-container').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                            loadSession(sid, null, pipelineType);
                        }, pipelineType);
                        ui.statusDiv.textContent = `Resuming... Loaded ${preloadedCount} existing results.`;
                    }
                })
                .catch(err => {
                    console.error("Error pre-loading run data:", err);
                    ui.statusDiv.textContent = "Error loading existing results. Starting pipeline...";
                });
        }

        preloadPromise.then(() => {
            const formData = new FormData();
            formData.append('csrfmiddlewaretoken', BenchmarkAPI.getCSRFToken());
            formData.append('dataset_id', document.getElementById('dataset-selector').value);
            formData.append('pipeline_id', currentPipelineId);
            formData.append('llm_base_url', currentLlmSettings.llm_base_url);
            formData.append('llm_api_key', currentLlmSettings.llm_api_key);
            formData.append('llm_model', currentLlmSettings.llm_model);
            if (currentLlmSettings.max_retries) formData.append('max_retries', currentLlmSettings.max_retries);
            if (groupId && groupId !== 'null' && groupId !== 'undefined') formData.append('group_id', groupId);

            // Allow page-specific form data additions
            if (window.buildPipelineFormData) window.buildPipelineFormData(formData);

            pipelineController = BenchmarkPipelineRunner.start({
                url: BenchmarkUrls.pipeline.start(pipelineType),
                formData: formData,
                ui: ui,
                totalItems: 0,
                initialProcessedCount: preloadedCount,
                callbacks: {
                    onMeta: (data) => {
                        if (data.type === 'info') ui.statusDiv.textContent = data.message;
                        if (data.type === 'session_created') {
                            BenchmarkSessionUI.addNewSessionToList('session-list', data.session_id, { question: data.question }, null, data.group_id, data.group_name, 'Processing...', pipelineType);
                            loadSession(data.session_id, null, pipelineType);
                            if (data.group_id) activeGroupId = data.group_id;
                        }
                        if (data.type === 'trial_started' || data.type === 'trial_completed') {
                            if (activeSessionId && String(activeSessionId) === String(data.session_id)) {
                                loadSession(data.session_id, null, pipelineType);
                            }
                        }
                        // Handle trial errors - stop polling and update UI immediately
                        if (data.type === 'trial_error') {
                            ui.statusDiv.textContent = `Trial error: ${data.error}`;
                            // Stop polling for this trial if we have the trial_id
                            if (data.trial_id) {
                                stopPolling(data.trial_id);
                            }
                            // Reload session to show error state
                            if (activeSessionId && String(activeSessionId) === String(data.session_id)) {
                                loadSession(data.session_id, null, pipelineType);
                            }
                        }
                    },
                    onData: (data) => {
                        if (data.error) {
                            ui.statusDiv.textContent = `Error: ${data.error}`;
                            if (data.session_id) {
                                BenchmarkSessionUI.addNewSessionToList('session-list', data.session_id, { question: data.question }, null, null, null, 'Error', pipelineType);
                                if (activeSessionId && String(activeSessionId) === String(data.session_id)) loadSession(data.session_id, null, pipelineType);
                            }
                            return;
                        }
                        const existingIdx = currentPipelineResults.findIndex(r => r.session_id === data.session_id);
                        if (existingIdx !== -1) currentPipelineResults[existingIdx] = data;
                        else currentPipelineResults.push(data);

                        BenchmarkSessionUI.updateStatsUI(currentPipelineResults, data.group_name || "Current Run", (sid) => {
                            document.getElementById('session-container').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                            loadSession(sid, null, pipelineType);
                        }, pipelineType);
                        BenchmarkSessionUI.addNewSessionToList('session-list', data.session_id, { question: data.question }, null, data.group_id, data.group_name, 'Finished', pipelineType);
                    }
                }
            });
        });
    }

    function stopPipeline() {
        if (pipelineController) pipelineController.abort();
        if (pipelineController?.pipelineId) {
            BenchmarkAPI.post(BenchmarkUrls.pipeline.stop(currentRunPipelineType), { pipeline_id: pipelineController.pipelineId }, { keepalive: true }).catch(console.error);
        }
    }

    // === Init Handlers ===
    function initPromptViewer() {
        document.addEventListener('click', function(e) {
            const btn = e.target.closest('.view-prompt-btn');
            if (!btn) return;

            const trialId = btn.dataset.trialId;
            if (!trialId) return;

            const originalHtml = btn.innerHTML;
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';

            BenchmarkAPI.get(BenchmarkUrls.multiTurn.getTrialPrompt(trialId))
                .then(data => {
                    if (data.status === 'ok') {
                        BenchmarkUtils.BenchmarkRenderer.renderPromptModal(JSON.stringify(data.messages, null, 2), 'modal-generic-content-container', 'benchmarkGenericModal', 'Full LLM Prompt');
                    } else {
                        alert(data.error || "Failed to load prompt.");
                    }
                })
                .catch(() => alert("Failed to load prompt details."))
                .finally(() => {
                    btn.disabled = false;
                    btn.innerHTML = originalHtml;
                });
        });
    }

    function initBatchDelete(pipelineType) {
        BenchmarkBatchSelection.setup(
            'session-list', 'select-all-checkbox', 'session-checkbox', 'delete-selected-btn',
            (selectedSessionIds, selectedGroupIds) => {
                if (selectedSessionIds.length === 0 && selectedGroupIds.length === 0) return;
                if (!confirm(`Delete ${selectedSessionIds.length} sessions and ${selectedGroupIds.length} groups?`)) return;

                const promises = [];
                if (selectedSessionIds.length > 0) {
                    promises.push(BenchmarkAPI.post(BenchmarkUrls.multiTurn.batchDeleteSessions, { session_ids: selectedSessionIds }));
                }
                selectedGroupIds.forEach(gid => {
                    promises.push(BenchmarkAPI.delete(BenchmarkUrls.multiTurn.deleteSessionGroup(gid)));
                });

                Promise.all(promises).then(() => window.location.reload()).catch(() => alert('Error during deletion.'));
            }, 'group-select-checkbox'
        );
    }

    function initSessionControls(pipelineType, questionsDataId) {
        const startBtn = document.getElementById('start-session-btn');
        const stopBtn = document.getElementById('stop-session-btn');

        if (startBtn) {
            startBtn.addEventListener('click', function() {
                const questionSelect = document.getElementById('question-select');
                if (!questionSelect.value) { alert('Select a question.'); return; }

                let qData = null;
                try {
                    const el = document.getElementById(questionsDataId);
                    if (el) qData = JSON.parse(el.textContent)[questionSelect.value];
                } catch (e) { console.error("Error parsing questions data", e); }

                if (!qData) { alert('Could not load question data.'); return; }

                startBtn.style.display = 'none';
                if (stopBtn) stopBtn.style.display = 'inline-block';
                BenchmarkSettings.toggleConfigurationInputs(true);

                sessionAbortController = new AbortController();

                BenchmarkAPI.post(BenchmarkUrls.multiTurn.createSession, {
                    question: qData.question,
                    ground_truths: qData.answer,
                    pipeline_type: pipelineType
                }, { signal: sessionAbortController.signal })
                    .then(data => {
                        if (data.error) {
                            alert(data.error);
                            resetSessionUI();
                        } else {
                            BenchmarkSessionUI.addNewSessionToList('session-list', data.session_id, qData, null, null, null, 'Now', pipelineType);
                            loadSession(data.session_id, data.trial_id, pipelineType);
                        }
                    })
                    .catch(err => {
                        if (err.name !== 'AbortError') {
                            alert('Error starting session.');
                            console.error(err);
                        }
                        resetSessionUI();
                    });
            });
        }

        if (stopBtn) {
            stopBtn.addEventListener('click', function() {
                if (sessionAbortController) sessionAbortController.abort();
                if (activeSessionId) {
                    BenchmarkAPI.post(BenchmarkUrls.multiTurn.stopSession, { session_id: activeSessionId })
                        .then(data => { if (data.status === 'ok') loadSession(activeSessionId, null, pipelineType); })
                        .catch(console.error);
                }
                resetSessionUI();
            });
        }
    }

    function initPipelineControls(pipelineType) {
        document.getElementById('run-pipeline-btn')?.addEventListener('click', () => initiatePipelineRun(null, pipelineType));
        document.getElementById('stop-pipeline-btn')?.addEventListener('click', stopPipeline);
        window.addEventListener('beforeunload', stopPipeline);
    }

    function initSessionListHandlers(pipelineType) {
        document.getElementById('session-list').addEventListener('click', function(e) {
            // Continue Group
            const continueBtn = e.target.closest('.continue-group-btn');
            if (continueBtn) {
                e.preventDefault();
                e.stopPropagation();
                if (confirm('Resume this pipeline run?')) {
                    initiatePipelineRun(continueBtn.dataset.groupId, continueBtn.dataset.pipelineType || pipelineType);
                }
                return;
            }

            // View Results
            const viewResultsBtn = e.target.closest('.view-group-results-btn');
            if (viewResultsBtn) {
                e.preventDefault();
                e.stopPropagation();
                loadRun(viewResultsBtn.dataset.groupId, viewResultsBtn.dataset.pipelineType || pipelineType);
                return;
            }

            // Rename Group
            const renameBtn = e.target.closest('.rename-group-btn');
            if (renameBtn) {
                e.preventDefault();
                e.stopPropagation();
                const groupId = renameBtn.dataset.groupId;
                const currentNameEl = document.querySelector(`.group-name-display[data-group-id="${groupId}"]`);
                const newName = prompt('Enter new name:', currentNameEl?.textContent || '');
                if (newName?.trim() && newName.trim() !== currentNameEl?.textContent) {
                    BenchmarkAPI.post(BenchmarkUrls.multiTurn.renameSessionGroup(groupId), { name: newName.trim() })
                        .then(data => { if (data.status === 'ok' && currentNameEl) currentNameEl.textContent = data.name; })
                        .catch(() => alert('Failed to rename.'));
                }
                return;
            }

            // Delete Group
            const deleteGrp = e.target.closest('.delete-group-btn');
            if (deleteGrp) {
                e.preventDefault();
                e.stopPropagation();
                if (confirm('Delete this pipeline run?')) {
                    BenchmarkAPI.delete(BenchmarkUrls.multiTurn.deleteSessionGroup(deleteGrp.dataset.groupId))
                        .then(data => { if (data.status === 'ok') window.location.reload(); });
                }
                return;
            }

            if (e.target.closest('input[type="checkbox"]')) return;

            // Session Click
            const target = e.target.closest('.session-details');
            if (target) {
                e.preventDefault();
                loadSession(target.dataset.sessionId, null, pipelineType);
            }
        });
    }

    function initRetryAndDelete(pipelineType) {
        window.retryTrial = function(trialId) {
            const trial = window.sessionTrials?.find(t => t.id === trialId);

            BenchmarkAPI.post(BenchmarkUrls.multiTurn.retrySession(trialId), {
                feedback: trial?.feedback || "",
                is_correct: false
            }, { signal: sessionAbortController?.signal })
                .then(data => {
                    if (data.error) {
                        alert(data.error);
                        if (sessionAbortController) resetSessionUI();
                    } else {
                        // NOTE: executeTrial will call loadSession, avoid double call
                        if (data.status === 'retrying') {
                            executeTrial(data.new_trial_id, activeSessionId, pipelineType);
                        } else {
                            // Only load session if not retrying (to show final state)
                            loadSession(activeSessionId, null, pipelineType);
                            if (data.status === 'max_retries_reached' || data.status === 'completed') {
                                if (sessionAbortController) resetSessionUI();
                            }
                        }
                    }
                })
                .catch(err => {
                    if (err.name !== 'AbortError') console.error(err);
                    if (sessionAbortController) resetSessionUI();
                });
        };

        document.getElementById('delete-session-btn')?.addEventListener('click', function() {
            if (activeSessionId && confirm('Delete session?')) {
                // Clear cached traces for trials in this session
                const trialsContainer = document.getElementById('trials-container');
                if (trialsContainer) {
                    trialsContainer.querySelectorAll('[id^="trial-"]').forEach(trialEl => {
                        const trialId = trialEl.id.replace('trial-', '');
                        if (trialId) delete trialTraceCache[trialId];
                    });
                }

                BenchmarkAPI.delete(BenchmarkUrls.multiTurn.deleteSession(activeSessionId))
                    .then(data => {
                        if (data.status === 'ok') {
                            document.querySelector(`#session-list [data-session-id='${activeSessionId}']`)?.remove();
                            document.getElementById('session-container').style.display = 'none';
                            document.getElementById('no-session-selected').style.display = 'block';
                            activeSessionId = null;
                        }
                    });
            }
        });
    }

    function initExports() {
        document.getElementById('export-session-json-btn')?.addEventListener('click', () => {
            if (activeSessionId) window.location.href = BenchmarkUrls.multiTurn.exportSession(activeSessionId) + '?format=json';
        });
        document.getElementById('export-session-csv-btn')?.addEventListener('click', () => {
            if (activeSessionId) window.location.href = BenchmarkUrls.multiTurn.exportSession(activeSessionId) + '?format=csv';
        });
        document.getElementById('export-results-json-btn')?.addEventListener('click', () => {
            if (activeGroupId) window.location.href = BenchmarkUrls.multiTurn.exportRun(activeGroupId);
            else alert("No run loaded to export.");
        });
    }

    function initImports() {
        const importBtn = document.getElementById('import-data-btn');
        const importFileInput = document.getElementById('import-file-input');

        if (!importBtn || !importFileInput) return;

        importBtn.addEventListener('click', () => {
            importFileInput.click();
        });

        importFileInput.addEventListener('change', async (e) => {
            const file = e.target.files[0];
            if (!file) return;

            // Reset input so same file can be selected again
            importFileInput.value = '';

            // Show loading state
            const originalHtml = importBtn.innerHTML;
            importBtn.disabled = true;
            importBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Importing...';

            try {
                const formData = new FormData();
                formData.append('file', file);
                formData.append('csrfmiddlewaretoken', BenchmarkAPI.getCSRFToken());

                const response = await fetch(BenchmarkUrls.multiTurn.importData, {
                    method: 'POST',
                    body: formData,
                    headers: {
                        'X-CSRFToken': BenchmarkAPI.getCSRFToken()
                    }
                });

                const data = await response.json();

                if (data.status === 'success') {
                    const importType = data.import_type === 'run' ? 'Pipeline Run' : 'Session';
                    const stats = data.stats || {};
                    let message = `${importType} imported successfully!`;
                    if (stats.sessions_imported) {
                        message += `\n- Sessions: ${stats.sessions_imported}`;
                    }
                    if (stats.trials_imported) {
                        message += `\n- Trials: ${stats.trials_imported}`;
                    }
                    alert(message);
                    // Reload the page to show imported data
                    window.location.reload();
                } else {
                    alert(`Import failed: ${data.message || 'Unknown error'}`);
                }
            } catch (err) {
                console.error('Import error:', err);
                alert(`Import failed: ${err.message || 'Network error'}`);
            } finally {
                importBtn.disabled = false;
                importBtn.innerHTML = originalHtml;
            }
        });
    }

    // === Public API ===
    return {
        init: function(config) {
            const { pipelineType, questionsDataId = 'questions-data', buildFormData } = config;

            currentRunPipelineType = pipelineType;
            if (buildFormData) window.buildPipelineFormData = buildFormData;

            BenchmarkSettings.setupConfigurationHandlers();
            BenchmarkSettings.setupConfigurationActionHandlers();

            initPromptViewer();
            initBatchDelete(pipelineType);
            initSessionControls(pipelineType, questionsDataId);
            initPipelineControls(pipelineType);
            initSessionListHandlers(pipelineType);
            initRetryAndDelete(pipelineType);
            initExports();
            initImports();

            // Initialize leaderboard (fixed to this pipeline type)
            if (window.BenchmarkLeaderboard) {
                BenchmarkLeaderboard.init(pipelineType);
            }

            // Check for run_id query parameter (from home page leaderboard click)
            const urlParams = new URLSearchParams(window.location.search);
            const runIdParam = urlParams.get('run_id');
            if (runIdParam) {
                // Auto-load the run after a short delay to ensure everything is initialized
                setTimeout(() => {
                    loadRun(runIdParam, pipelineType);
                    // Clean up the URL
                    window.history.replaceState({}, document.title, window.location.pathname);
                }, 100);
            }
        },

        // Expose loadRun for leaderboard integration
        loadRun: loadRun,

        startPolling: startPolling,

        // Get cached trace for a trial (returns null if not cached)
        getCachedTrace: function(trialId) {
            return trialTraceCache[trialId] || null;
        },

        // Set cached trace for a trial
        setCachedTrace: function(trialId, trace) {
            if (trace && trace.length > 0) {
                trialTraceCache[trialId] = trace;
            }
        },

        // Clear cache for a specific trial or all trials
        clearTraceCache: function(trialId) {
            if (trialId) {
                delete trialTraceCache[trialId];
            } else {
                Object.keys(trialTraceCache).forEach(k => delete trialTraceCache[k]);
            }
        }
    };
})();
