window.BenchmarkUtils.MultiTurnPage = (function() {
    const activePolls = {};
    const trialState = {};

    const PIPELINE_CONFIGS = {
        'vanilla_llm': {
            loadingText: 'Thinking...',
            icon: 'bi-robot'
        },
        'rag': {
            loadingText: 'Thinking...',
            icon: 'bi-globe'
        },
        'vanilla_agent': {
            loadingText: 'Thinking...',
            icon: 'bi-robot'
        },
        'browser_agent': {
            loadingText: 'Thinking...',
            icon: 'bi-browser-chrome'
        }
    };

    function startPolling(trialId, pipelineType) {
        if (activePolls[trialId]) return;

        const config = PIPELINE_CONFIGS[pipelineType] || PIPELINE_CONFIGS['vanilla_llm'];

        // Initialize state
        if (!trialState[trialId]) {
            trialState[trialId] = { renderedCount: 0, backoffDelay: 2000, lastStepWasStreaming: false };
        }

        const poll = () => {
            const trialDiv = document.getElementById(`trial-${trialId}`);
            if (!trialDiv) {
                delete activePolls[trialId];
                delete trialState[trialId];
                return;
            }

            let currentCount = trialState[trialId].renderedCount;
            // If the last step was streaming (partial), we need to re-fetch it to get updates
            if (trialState[trialId].lastStepWasStreaming) {
                currentCount = Math.max(0, currentCount - 1);
            }
            
            fetch(`/benchmark/api/sessions/get_trial_trace/${trialId}/?cursor=${currentCount}`)
                .then(res => res.json())
                .then(data => {
                    const newSteps = data.trace || [];
                    const trialInfo = data.trial; 

                    if (newSteps.length > 0) {
                        trialState[trialId].backoffDelay = 2000; // Reset backoff

                        const wrapper = trialDiv.querySelector('.trial-wrapper');
                        if (wrapper) {
                            // Safety: If starting fresh (cursor=0), clear existing bubbles to prevent duplication
                            if (currentCount === 0) {
                                const existing = wrapper.querySelectorAll('.message-bubble');
                                existing.forEach(el => el.remove());
                            }

                            // If we are replacing a streaming step, remove the last bubble
                            if (trialState[trialId].lastStepWasStreaming) {
                                const bubbles = wrapper.querySelectorAll('.message-bubble');
                                if (bubbles.length > 0) {
                                    bubbles[bubbles.length - 1].remove();
                                }
                                trialState[trialId].renderedCount--;
                            }

                            // Check for processing indicator - Remove ALL instances
                            const processingIndicators = wrapper.querySelectorAll('.trial-processing-indicator');
                            processingIndicators.forEach(indicator => {
                                const indicatorParent = indicator.closest('.message-bubble');
                                if (indicatorParent) indicatorParent.remove();
                            });

                            const verdictContainer = wrapper.querySelector('.trial-verdict-container');
                            
                            newSteps.forEach((step, idx) => {
                                const stepEl = BenchmarkUtils.BenchmarkRenderer.renderAgentStep(step, currentCount + idx, trialId, trialInfo ? trialInfo.answer : null);
                                // Insert new steps correctly (before verdict if it exists)
                                if (verdictContainer) {
                                    verdictContainer.insertAdjacentElement('beforebegin', stepEl);
                                } else {
                                    wrapper.appendChild(stepEl);
                                }
                            });
                            
                            // Re-append processing indicator if still processing
                            if (trialInfo && trialInfo.status === 'processing') {
                                const indicatorEl = BenchmarkUtils.BenchmarkRenderer.createMessageBubble('assistant', `<div class="d-flex align-items-center trial-processing-indicator"><span class="spinner-border spinner-border-sm text-primary me-2"></span>${config.loadingText}</div>`, '', config.icon);
                                
                                // Insert indicator before verdict if exists, else append
                                if (verdictContainer) {
                                    verdictContainer.insertAdjacentElement('beforebegin', indicatorEl);
                                } else {
                                    wrapper.appendChild(indicatorEl);
                                }
                            }
                        }
                        
                        trialState[trialId].renderedCount += newSteps.length;

                        const lastStep = newSteps[newSteps.length - 1];
                        if (lastStep && lastStep.is_streaming) {
                            trialState[trialId].lastStepWasStreaming = true;
                            trialState[trialId].backoffDelay = 500;
                        } else {
                            trialState[trialId].lastStepWasStreaming = false;
                        }
                    } else {
                        trialState[trialId].backoffDelay = Math.min(trialState[trialId].backoffDelay * 1.5, 10000);
                    }

                    if (trialInfo && (trialInfo.status === 'completed' || trialInfo.status === 'error')) {
                        clearTimeout(activePolls[trialId]);
                        delete activePolls[trialId];
                        delete trialState[trialId];

                        const wrapper = trialDiv.querySelector('.trial-wrapper');
                        if (wrapper) {
                             const processingIndicators = wrapper.querySelectorAll('.trial-processing-indicator');
                             processingIndicators.forEach(indicator => {
                                 const indicatorParent = indicator.closest('.message-bubble');
                                 if (indicatorParent) indicatorParent.remove();
                             });
                             
                             // Final check for verdict (if not already there)
                             if (trialInfo.status === 'completed' && !wrapper.querySelector('.trial-verdict-container')) {
                                const verdictContainer = BenchmarkUtils.BenchmarkRenderer.renderTrialVerdict(trialInfo);
                                if (verdictContainer) wrapper.appendChild(verdictContainer);
                             }
                        }
                        return;
                    }
                })
                .catch(err => {
                    console.error("Polling error:", err);
                    trialState[trialId].backoffDelay = 10000;
                })
                .finally(() => {
                    if (activePolls[trialId]) {
                         if (document.getElementById(`trial-${trialId}`)) {
                            activePolls[trialId] = setTimeout(poll, trialState[trialId].backoffDelay);
                        } else {
                            delete activePolls[trialId];
                            delete trialState[trialId];
                        }
                    }
                });
        };

        activePolls[trialId] = setTimeout(poll, 1000);
    }

    return {
        init: function(config) {
            const { 
                pipelineType, 
                csvPrefix = 'multiturn-results',
                questionsDataId = 'questions-data',
                buildFormData 
            } = config;
            
            const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
            if (!csrfToken) console.error("CSRF Token is missing or empty!");
            BenchmarkUtils.setupConfigurationHandlers();
            BenchmarkUtils.setupConfigurationActionHandlers(csrfToken, true, true);
            
            // Search Results Modal Listener removed - handled by inline onclick in renderer to prevent duplicates

            // --- Prompt Viewing Listener ---
            document.addEventListener('click', function(e) {
                if (e.target && e.target.closest('.view-prompt-btn')) {
                    const btn = e.target.closest('.view-prompt-btn');
                    const trialId = btn.dataset.trialId;
                    
                    if (!trialId) return;
                    
                    const originalHtml = btn.innerHTML;
                    btn.disabled = true;
                    btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';

                    fetch(BenchmarkUrls.multiTurn.getTrialPrompt(trialId))
                    .then(res => res.json())
                    .then(data => {
                        if (data.status === 'ok') {
                            const formattedPrompt = JSON.stringify(data.messages, null, 2);
                            BenchmarkUtils.BenchmarkRenderer.renderPromptModal(formattedPrompt, 'modal-generic-content-container', 'benchmarkGenericModal', 'Full LLM Prompt');
                        } else {
                            alert(data.error || "Failed to load prompt.");
                        }
                    })
                    .catch(err => {
                        console.error("Error fetching prompt:", err);
                        alert("Failed to load prompt details.");
                    })
                    .finally(() => {
                        btn.disabled = false;
                        btn.innerHTML = originalHtml;
                    });
                }
            });

            let activeSessionId = null;
            let currentPipelineResults = [];
            let pipelineController = null;
            let currentRunPipelineType = pipelineType;

            // Session Control Variables
            let sessionAbortController = null;
            const startSessionBtn = document.getElementById('start-session-btn');
            const stopSessionBtn = document.getElementById('stop-session-btn');
            let sessionRetryTimeout = null;

            function resetSessionUI() {
                if (startSessionBtn) startSessionBtn.style.display = 'block';
                if (stopSessionBtn) stopSessionBtn.style.display = 'none';
                BenchmarkUtils.toggleConfigurationInputs(false);
                sessionAbortController = null;
                if (sessionRetryTimeout) {
                    clearTimeout(sessionRetryTimeout);
                    sessionRetryTimeout = null;
                }
            }

            // --- Batch Delete ---
            BenchmarkUtils.setupBatchSelection(
                'session-list', 'select-all-checkbox', 'session-checkbox', 'delete-selected-btn',
                (selectedSessionIds, selectedGroupIds) => {
                    if (selectedSessionIds.length === 0 && selectedGroupIds.length === 0) return;
                    if (!confirm(`Delete ${selectedSessionIds.length} sessions and ${selectedGroupIds.length} groups?`)) return;
                    
                    const promises = [];
                    if (selectedSessionIds.length > 0) {
                        promises.push(fetch(BenchmarkUrls.multiTurn.batchDeleteSessions, {
                            method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                            body: JSON.stringify({ session_ids: selectedSessionIds })
                        }).then(res => res.json()));
                    }
                    selectedGroupIds.forEach(gid => {
                        promises.push(fetch(BenchmarkUrls.multiTurn.deleteSessionGroup(gid), {
                            method: 'DELETE', headers: { 'X-CSRFToken': csrfToken }
                        }).then(res => res.json()));
                    });

                    Promise.all(promises).then(() => window.location.reload())
                        .catch(err => alert('Error during deletion.'));
                }, 'group-select-checkbox'
            );

            // --- Helper: Load Session ---
            function loadSession(sessionId, initialTrialId = null) {
                activeSessionId = sessionId;
                
                fetch(BenchmarkUrls.multiTurn.getSession(sessionId))
                    .then(res => res.json())
                    .then(data => {
                        const sessionPipelineType = (data.session && data.session.pipeline_type) ? data.session.pipeline_type : pipelineType;
                        BenchmarkUtils.MultiTurnUtils.renderSession(data.session, data.trials, { sessionTrials: [], pipelineType: sessionPipelineType }); 
                        window.sessionTrials = data.trials; 
                        
                        const settingsWhitelist = ['llm_model', 'llm_base_url', 'max_retries', 'allow_reasoning', 'temperature', 'top_p', 'max_tokens'];
                         if (sessionPipelineType.includes('rag')) {
                            settingsWhitelist.push('search');
                        }
                        if (sessionPipelineType.includes('agent')) {
                            settingsWhitelist.push('agent');
                        }
                        BenchmarkUtils.BenchmarkRenderer.renderRunConfiguration(data.session.settings_snapshot, settingsWhitelist);
                        
                        document.getElementById('session-container').style.display = 'block';
                        document.getElementById('no-session-selected').style.display = 'none';
                        
                        const delBtn = document.getElementById('delete-session-btn');
                        if (data.session.group_id) delBtn.style.display = 'none';
                        else delBtn.style.display = 'inline-block';

                        if (initialTrialId) {
                            executeTrial(initialTrialId, sessionId);
                        } else {
                            const lastTrial = data.trials[data.trials.length - 1];
                            if (lastTrial && lastTrial.status === 'completed' && lastTrial.is_correct === false && !data.session.is_completed) {
                                if (data.trials.length < data.session.max_retries) {
                                    if (sessionAbortController && !sessionAbortController.signal.aborted) {
                                         sessionRetryTimeout = setTimeout(() => {
                                             if (sessionAbortController && !sessionAbortController.signal.aborted) {
                                                 window.retryTrial(lastTrial.id); 
                                             }
                                         }, 1500);
                                    }
                                } else {
                                    if (sessionAbortController) resetSessionUI();
                                }
                            } else if (data.session.is_completed) {
                                if (sessionAbortController) resetSessionUI();
                            }
                        }
                    });
            }

            // --- Helper: Execute Trial ---
            function executeTrial(trialId, sessionId) {
                 const signal = sessionAbortController ? sessionAbortController.signal : null;
                 
                 fetch(BenchmarkUrls.multiTurn.runTrial(trialId), { signal: signal })
                 .then(res => res.json()).then(data => {
                     if (data.error) {
                         alert(`Error in trial #${trialId}: ${data.error}`);
                         if (sessionAbortController) resetSessionUI();
                     }
                     if (sessionId) loadSession(sessionId);
                 }).catch((err) => {
                     if (err.name === 'AbortError') {
                         console.log("Trial execution aborted by user.");
                     } else {
                         console.error('Network error in trial.', err);
                         if (sessionId) loadSession(sessionId);
                     }
                     if (sessionAbortController) resetSessionUI();
                 });
            }
            
            // --- Helper: Load Group/Run ---
            function loadRun(groupId, overridePipelineType = null) {
                 const runPipelineType = overridePipelineType || pipelineType;
                 const loadRunUrl = BenchmarkUrls.pipeline.loadRun(runPipelineType, groupId);

                 fetch(loadRunUrl).then(res => res.json()).then(data => {
                     if (data.error) { alert(data.error); return; }
                     currentPipelineResults = data.results;
                     
                     const statsContainer = document.getElementById('statistics-container');
                     if (statsContainer) statsContainer.style.display = 'block';

                     BenchmarkUtils.MultiTurnUtils.updateStatsUI(data.results, data.group_name, (sid) => {
                         document.getElementById('session-container').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                         loadSession(sid);
                     });
                     
                     const settingsWhitelist = ['llm_model', 'llm_base_url', 'max_retries', 'allow_reasoning', 'temperature', 'top_p', 'max_tokens'];
                     if (runPipelineType.includes('rag')) settingsWhitelist.push('search');
                     if (runPipelineType.includes('agent')) settingsWhitelist.push('agent');
                     BenchmarkUtils.BenchmarkRenderer.renderRunConfiguration(data.settings, settingsWhitelist);
                     if (statsContainer) statsContainer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                 });
            }

            // --- Single Session Start ---
            if (startSessionBtn) {
                startSessionBtn.addEventListener('click', function() {
                    const questionSelect = document.getElementById('question-select');
                    if (!questionSelect.value) { alert('Select a question.'); return; }
                    
                    let qData = null;
                    try {
                         const questionsDataEl = document.getElementById(questionsDataId);
                         if (questionsDataEl) {
                             const questions = JSON.parse(questionsDataEl.textContent);
                             qData = questions[questionSelect.value];
                         }
                    } catch (e) { console.error("Error parsing questions data", e); }
                    
                    if (!qData) { alert('Could not load question data.'); return; }
                    
                    startSessionBtn.style.display = 'none';
                    if (stopSessionBtn) stopSessionBtn.style.display = 'inline-block';
                    BenchmarkUtils.toggleConfigurationInputs(true);
                    
                    sessionAbortController = new AbortController();
                    const signal = sessionAbortController.signal;
                    
                    fetch(BenchmarkUrls.multiTurn.createSession, {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrfToken},
                        body: JSON.stringify({
                            question: qData.question,
                            ground_truths: qData.answer,
                            pipeline_type: pipelineType
                        }),
                        signal: signal
                    }).then(res => res.json()).then(data => {
                        if (data.error) {
                            alert(data.error);
                            resetSessionUI();
                        } else {
                            BenchmarkUtils.MultiTurnUtils.addNewSessionToList('session-list', data.session_id, qData, null);
                            loadSession(data.session_id, data.trial_id);
                        }
                    }).catch(err => {
                        if (err.name !== 'AbortError') {
                            alert('Error starting session.');
                            console.error(err);
                        }
                        resetSessionUI();
                    });
                });
            }
            
            // --- Single Session Stop ---
            if (stopSessionBtn) {
                stopSessionBtn.addEventListener('click', function() {
                    if (sessionAbortController) {
                        sessionAbortController.abort();
                    }
                    if (activeSessionId) {
                         const currentSessionId = activeSessionId;
                         fetch(BenchmarkUrls.multiTurn.stopSession, {
                             method: 'POST',
                             headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                             body: JSON.stringify({ session_id: currentSessionId })
                         })
                         .then(res => res.json())
                         .then(data => {
                             if (data.status === 'ok') {
                                 loadSession(currentSessionId);
                             }
                         })
                         .catch(console.error);
                    }
                    resetSessionUI();
                });
            }

            // --- Pipeline Run Helper ---
            function initiatePipelineRun(groupId = null, overridePipelineType = null) {
                currentRunPipelineType = overridePipelineType || pipelineType;
                console.log(`initiatePipelineRun called with groupId: ${groupId} (type: ${typeof groupId})`);
                const currentPipelineId = BenchmarkUtils.generateUUID();
                const ui = {
                    runBtn: document.getElementById('run-pipeline-btn'), // Always reference main run button for state
                    stopBtn: document.getElementById('stop-pipeline-btn'),
                    progressBar: document.getElementById('pipeline-progress-bar'),
                    statusDiv: document.getElementById('pipeline-status'),
                    resultsBody: null, 
                    spinner: null
                };
                
                document.getElementById('statistics-container').style.display = 'block';
                
                // Clear table and results initially - we will repopulate if resuming
                document.getElementById('stats-details-tbody').innerHTML = '';
                currentPipelineResults = [];
                
                document.getElementById('pipeline-progress').style.display = 'block';
                document.getElementById('results-header-text').textContent = groupId ? 'Resuming Pipeline Run...' : 'Live Pipeline Results';
                if (ui.statusDiv) ui.statusDiv.textContent = groupId ? 'Initializing resume...' : 'Initializing...';

                // Ensure settings are synced
                const currentLlmSettings = {
                    llm_base_url: document.getElementById('llm_base_url').value,
                    llm_api_key: document.getElementById('llm_api_key').value,
                    llm_model: document.getElementById('llm_model').value,
                    max_retries: document.getElementById('max_retries') ? document.getElementById('max_retries').value : null,
                };
                BenchmarkUtils.BenchmarkRenderer.renderRunConfiguration({ llm_settings: currentLlmSettings });
                
                let preloadedCount = 0;
                let preloadPromise = Promise.resolve();

                if (groupId && groupId !== 'null' && groupId !== 'undefined') {
                    ui.statusDiv.textContent = 'Fetching existing results...';
                    const loadUrl = BenchmarkUrls.pipeline.loadRun(currentRunPipelineType, groupId);
                    
                    preloadPromise = fetch(loadUrl)
                        .then(res => res.json())
                        .then(data => {
                            if (data.results) {
                                currentPipelineResults = data.results;
                                preloadedCount = data.results.length;
                                
                                // Render existing results
                                BenchmarkUtils.MultiTurnUtils.updateStatsUI(currentPipelineResults, data.group_name || "Current Run", (sid) => {
                                     document.getElementById('session-container').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                                     loadSession(sid);
                                });
                                
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
                    formData.append('csrfmiddlewaretoken', csrfToken);
                    formData.append('dataset_id', document.getElementById('dataset-selector').value);
                    formData.append('pipeline_id', currentPipelineId);
                    formData.append('llm_base_url', currentLlmSettings.llm_base_url);
                    formData.append('llm_api_key', currentLlmSettings.llm_api_key);
                    formData.append('llm_model', currentLlmSettings.llm_model);
                    if (currentLlmSettings.max_retries) formData.append('max_retries', currentLlmSettings.max_retries);
                    
                    if (groupId && groupId !== 'null' && groupId !== 'undefined') {
                        formData.append('group_id', groupId);
                    }
                    
                    if (buildFormData) buildFormData(formData);
                    
                    const runUrl = BenchmarkUrls.pipeline.start(currentRunPipelineType);

                    pipelineController = BenchmarkUtils.PipelineRunner.start({
                        url: runUrl,
                        formData: formData,
                        ui: ui,
                        totalItems: 0, // Will be updated by stream
                        initialProcessedCount: preloadedCount, // Pass the count of preloaded items
                        callbacks: {
                            onMeta: (data) => {
                                 if (data.type === 'info') ui.statusDiv.textContent = data.message;
                                 if (data.type === 'session_created') {
                                     BenchmarkUtils.MultiTurnUtils.addNewSessionToList('session-list', data.session_id, { question: data.question }, null, data.group_id, data.group_name, 'Processing...');
                                     loadSession(data.session_id);
                                 }
                                 if (data.type === 'trial_started' || data.type === 'trial_completed') {
                                     if (activeSessionId && String(activeSessionId) === String(data.session_id)) loadSession(data.session_id);
                                 }
                            },
                                                    onData: (data) => {
                                                         if (data.error) { 
                                                             ui.statusDiv.textContent = `Error: ${data.error}`; 
                                                             if (data.session_id) {
                                                                 BenchmarkUtils.MultiTurnUtils.addNewSessionToList('session-list', data.session_id, { question: data.question }, null, null, null, 'Error');
                                                                 if (activeSessionId && String(activeSessionId) === String(data.session_id)) loadSession(data.session_id);
                                                             }
                                                             return; 
                                                         }
                                                         
                                                         const existingIdx = currentPipelineResults.findIndex(r => r.session_id === data.session_id);
                                                         if (existingIdx !== -1) {
                                                             currentPipelineResults[existingIdx] = data;
                                                         } else {
                                                             currentPipelineResults.push(data);
                                                         }
                            
                                                         BenchmarkUtils.MultiTurnUtils.updateStatsUI(currentPipelineResults, data.group_name || "Current Run", (sid) => {
                                                             document.getElementById('session-container').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                                                             loadSession(sid);
                                                         });
                                                         BenchmarkUtils.MultiTurnUtils.addNewSessionToList('session-list', data.session_id, { question: data.question }, null, data.group_id, data.group_name, 'Finished');
                                                    }                        }
                    });
                });
            }

            // --- Pipeline Run Button ---
            document.getElementById('run-pipeline-btn').addEventListener('click', function() {
                initiatePipelineRun(null, pipelineType);
            });

            // --- Stop Pipeline ---
            function stopPipeline() {
                if (pipelineController) pipelineController.abort();
                if (pipelineController && pipelineController.pipelineId) {
                    let strategyData = { pipeline_id: pipelineController.pipelineId };

                    const stopUrl = BenchmarkUrls.pipeline.stop(currentRunPipelineType || pipelineType);

                    fetch(stopUrl, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                        body: JSON.stringify(strategyData),
                        keepalive: true
                    }).catch(console.error);
                }
            }
            document.getElementById('stop-pipeline-btn').addEventListener('click', stopPipeline);
            window.addEventListener('beforeunload', stopPipeline);

            // --- List Click Handlers ---
            document.getElementById('session-list').addEventListener('click', function(e) {
                // Continue Group
                const continueBtn = e.target.closest('.continue-group-btn');
                if (continueBtn) {
                    e.preventDefault();
                    e.stopPropagation();
                    const groupId = continueBtn.dataset.groupId;
                    const groupPipelineType = continueBtn.dataset.pipelineType || pipelineType;
                    console.log(`Continue button clicked. Extracted groupId: ${groupId}`);
                    if (confirm('Resume this pipeline run?')) {
                        initiatePipelineRun(groupId, groupPipelineType);
                    }
                    return;
                }

                const deleteGrp = e.target.closest('.delete-group-btn');
                if (deleteGrp) {
                    e.preventDefault(); 
                    e.stopPropagation();
                    if (confirm('Delete group?')) {
                         fetch(BenchmarkUrls.multiTurn.deleteSessionGroup(deleteGrp.dataset.groupId), { method: 'DELETE', headers: { 'X-CSRFToken': csrfToken } })
                         .then(res => res.json()).then(data => {
                             if (data.status === 'ok') { deleteGrp.closest('.list-group-item').remove(); window.location.reload(); }
                         });
                    }
                    return;
                }

                if (e.target.closest('input[type="checkbox"]')) {
                    return; 
                }

                const target = e.target.closest('.session-details');
                if (target) { 
                    e.preventDefault();
                    loadSession(target.dataset.sessionId); 
                    return;
                }
                
                const groupSummary = e.target.closest('.group-summary');
                if (groupSummary) { 
                    if (groupSummary.dataset && groupSummary.dataset.groupId) {
                        try {
                            const groupPipelineType = groupSummary.dataset.pipelineType || pipelineType;
                            loadRun(groupSummary.dataset.groupId, groupPipelineType); 
                        } catch (err) {
                            console.error("loadRun error:", err);
                        }
                    }
                }
            });
            
            // --- Global Retry Trial Hook ---
            window.retryTrial = function(trialId) {
                const trial = window.sessionTrials ? window.sessionTrials.find(t => t.id === trialId) : null;
                const feedback = trial ? trial.feedback : "";
                
                const signal = sessionAbortController ? sessionAbortController.signal : null;

                fetch(BenchmarkUrls.multiTurn.retrySession(trialId), {
                    method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrfToken},
                    body: JSON.stringify({ feedback: feedback, is_correct: false }),
                    signal: signal
                }).then(res => res.json()).then(data => {
                    if (data.error) {
                        alert(data.error);
                        if (sessionAbortController) resetSessionUI();
                    } else {
                        loadSession(activeSessionId);
                        if (data.status === 'retrying') executeTrial(data.new_trial_id, activeSessionId);
                        if (data.status === 'max_retries_reached' || data.status === 'completed') {
                             if (sessionAbortController) resetSessionUI();
                        }
                    }
                }).catch(err => {
                    if (err.name !== 'AbortError') {
                        console.error(err);
                    }
                     if (sessionAbortController) resetSessionUI();
                });
            };
            
            // --- Single Session Delete ---
            document.getElementById('delete-session-btn').addEventListener('click', function() {
                 if (activeSessionId && confirm('Delete session?')) {
                     fetch(BenchmarkUrls.multiTurn.deleteSession(activeSessionId), { method: 'DELETE', headers: { 'X-CSRFToken': csrfToken } })
                     .then(res => res.json()).then(data => {
                         if (data.status === 'ok') {
                             document.querySelector(`#session-list [data-session-id='${activeSessionId}']`).remove();
                             document.getElementById('session-container').style.display = 'none';
                             document.getElementById('no-session-selected').style.display = 'block';
                             activeSessionId = null;
                         }
                     });
                 }
            });
            
            // --- Exports ---
            if (document.getElementById('export-session-json-btn')) {
                document.getElementById('export-session-json-btn').addEventListener('click', () => {
                    if (activeSessionId) window.location.href = BenchmarkUrls.multiTurn.exportSession(activeSessionId) + '?format=json';
                });
            }
            if (document.getElementById('export-session-csv-btn')) {
                document.getElementById('export-session-csv-btn').addEventListener('click', () => {
                    if (activeSessionId) window.location.href = BenchmarkUrls.multiTurn.exportSession(activeSessionId) + '?format=csv';
                });
            }
            document.getElementById('export-results-btn').addEventListener('click', () => {
                const headers = ["#", "Question", "Final Answer", "Ground Truths", "Result", "Trials"];
                const rowMapper = (result, index) => {
                    return [
                        index + 1, result.question, result.final_answer || 'N/A', 
                        Array.isArray(result.ground_truths) ? result.ground_truths.join('; ') : result.ground_truths,
                        result.correct === true ? 'Correct' : (result.correct === false ? 'Incorrect' : 'Error'),
                        result.trials
                    ];
                };
                BenchmarkUtils.exportToCSV(currentPipelineResults, csvPrefix, headers, rowMapper);
            });
        },
        
        startPolling: startPolling,
        PIPELINE_CONFIGS: PIPELINE_CONFIGS
    };
})();
