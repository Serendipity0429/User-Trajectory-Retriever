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
            console.log(`[Polling] Already polling trial ${trialId}, skipping`);
            return;
        }

        console.log(`[Polling] Starting poll for trial ${trialId}, pipeline: ${pipelineType}`);
        const config = BenchmarkPipelineConfig.get(pipelineType);

        const poll = () => {
            const trialDiv = document.getElementById(`trial-${trialId}`);
            if (!trialDiv) {
                console.log(`[Polling] Trial div not found for ${trialId}, stopping`);
                stopPolling(trialId);
                return;
            }

            const wrapper = trialDiv.querySelector('.trial-wrapper');
            if (!wrapper) {
                console.log(`[Polling] Wrapper not found for trial ${trialId}, stopping`);
                stopPolling(trialId);
                return;
            }

            // Always fetch full trace (cursor=0) and do a smart diff/replace
            // This avoids sync issues between DOM state and cursor tracking
            console.log(`[Polling] Fetching trace for trial ${trialId}...`);
            BenchmarkAPI.get(`/benchmark/api/sessions/get_trial_trace/${trialId}/?cursor=0`)
                .then(data => {
                    const allSteps = data.trace || [];
                    const trialInfo = data.trial;
                    const totalSteps = data.total_steps || allSteps.length;

                    console.log(`[Polling] Trial ${trialId}: received ${allSteps.length} steps, status: ${trialInfo?.status}`);
                    // Debug: check if first step is system prompt
                    if (allSteps.length > 0) {
                        console.log('[Polling] First step:', { role: allSteps[0]?.role, step_type: allSteps[0]?.step_type, totalSteps: allSteps.length });
                    }

                    // Get current bubbles (excluding verdict and indicators)
                    const existingBubbles = Array.from(wrapper.querySelectorAll('.message-bubble'))
                        .filter(b => !b.closest('.trial-verdict-container') && !b.querySelector('.trial-processing-indicator'));

                    const lastStep = allSteps.length > 0 ? allSteps[allSteps.length - 1] : null;
                    const isStreaming = !!(lastStep && lastStep.is_streaming);
                    const existingCount = existingBubbles.length;
                    const verdictContainer = wrapper.querySelector('.trial-verdict-container');
                    const hasNewSteps = allSteps.length > existingCount;

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
                    if (isStreaming && existingCount > 0 && allSteps.length === existingCount) {
                        const lastBubble = existingBubbles[existingCount - 1];
                        const lastStepEl = BenchmarkUtils.BenchmarkRenderer.renderAgentStep(lastStep, existingCount - 1, trialId, trialInfo ? trialInfo.answer : null);
                        lastBubble.replaceWith(lastStepEl);
                    }

                    // Set backoff based on streaming state
                    const backoffDelay = isStreaming ? 500 : 2000;

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

                        // Final cleanup: remove all processing indicators
                        wrapper.querySelectorAll('.trial-processing-indicator').forEach(indicator => {
                            const parent = indicator.closest('.message-bubble');
                            if (parent) parent.remove();
                        });

                        // Add verdict if completed and not already present
                        if (trialInfo.status === 'completed' && !wrapper.querySelector('.trial-verdict-container')) {
                            const verdictContainer = BenchmarkUtils.BenchmarkRenderer.renderTrialVerdict(trialInfo);
                            if (verdictContainer) wrapper.appendChild(verdictContainer);
                        }
                        return;
                    }

                    // Schedule next poll
                    if (activePolls[trialId]) {
                        activePolls[trialId] = setTimeout(poll, backoffDelay);
                    }
                })
                .catch(err => {
                    console.error("Polling error:", err);
                    // Schedule retry with longer backoff
                    if (activePolls[trialId]) {
                        activePolls[trialId] = setTimeout(poll, 10000);
                    }
                });
        };

        // Mark as active and start first poll
        activePolls[trialId] = setTimeout(poll, 500);
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
        console.log(`[loadSession] Loading session ${sessionId}`);
        activeSessionId = sessionId;

        BenchmarkAPI.get(BenchmarkUrls.multiTurn.getSession(sessionId))
            .then(data => {
                console.log(`[loadSession] Received ${data.trials?.length || 0} trials:`, data.trials?.map(t => ({ id: t.id, status: t.status, trial_number: t.trial_number })));
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
                    if (lastTrial?.status === 'completed' && lastTrial.is_correct === false && !data.session.is_completed) {
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
                            console.log(`Retrying with new trial ${retryData.new_trial_id}`);
                            executeTrial(retryData.new_trial_id, sessionId, pipelineType);
                        } else if (retryData.status === 'max_retries_reached') {
                            console.log('Max retries reached');
                            if (sessionAbortController) resetSessionUI();
                        } else if (retryData.status === 'completed') {
                            console.log('Session completed');
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
                        console.log('[SSE] onMeta received:', data.type, data);
                        if (data.type === 'info') ui.statusDiv.textContent = data.message;
                        if (data.type === 'session_created') {
                            console.log('[SSE] session_created:', data.session_id);
                            BenchmarkSessionUI.addNewSessionToList('session-list', data.session_id, { question: data.question }, null, data.group_id, data.group_name, 'Processing...', pipelineType);
                            loadSession(data.session_id, null, pipelineType);
                            if (data.group_id) activeGroupId = data.group_id;
                        }
                        if (data.type === 'trial_started' || data.type === 'trial_completed') {
                            console.log(`[SSE] ${data.type}: trial=${data.trial_id}, session=${data.session_id}, activeSession=${activeSessionId}`);
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

    function initExports(csvPrefix) {
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
        document.getElementById('export-results-btn')?.addEventListener('click', () => {
            BenchmarkExport.exportToCSV(currentPipelineResults, csvPrefix,
                ["#", "Question", "Final Answer", "Ground Truths", "Result", "Trials"],
                (result, index) => [
                    index + 1, result.question, result.final_answer || 'N/A',
                    Array.isArray(result.ground_truths) ? result.ground_truths.join('; ') : result.ground_truths,
                    result.correct === true ? 'Correct' : (result.correct === false ? 'Incorrect' : 'Error'),
                    result.trials
                ]);
        });
    }

    // === Public API ===
    return {
        init: function(config) {
            const { pipelineType, csvPrefix = 'multiturn-results', questionsDataId = 'questions-data', buildFormData } = config;

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
            initExports(csvPrefix);
        },

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
