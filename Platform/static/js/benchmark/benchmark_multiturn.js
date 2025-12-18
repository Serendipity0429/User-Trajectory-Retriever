window.BenchmarkUtils.MultiTurnPage = {
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
            
            // --- Search Results Modal Listener ---
            if (config.pipelineType.includes('rag')) {
                document.addEventListener('click', function(e) {
                    if (e.target && e.target.closest('.view-search-results-btn')) {
                        const btn = e.target.closest('.view-search-results-btn');
                        try {
                            const results = JSON.parse(decodeURIComponent(btn.dataset.results));
                            const container = document.getElementById('modal-search-results-container');
                            BenchmarkUtils.BenchmarkRenderer.renderModalSearchResults(results, container);
                            const modal = new bootstrap.Modal(document.getElementById('searchResultsListModal'));
                            modal.show();
                        } catch (err) {
                            console.error("Error opening results modal:", err);
                            alert("Failed to load results details.");
                        }
                    }
                });
            }

            let activeSessionId = null;
            let currentPipelineResults = [];
            let pipelineController = null;

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
                // If we are currently running a session and loading a DIFFERENT session, do not abort unless logic dictates.
                // But typically loadSession is called to refresh current session.
                
                fetch(BenchmarkUrls.multiTurn.getSession(sessionId))
                    .then(res => res.json())
                    .then(data => {
                        BenchmarkUtils.MultiTurnUtils.renderSession(data.session, data.trials, { sessionTrials: [] }); 
                        window.sessionTrials = data.trials; 
                        
                        const settingsWhitelist = ['llm_model', 'llm_base_url', 'max_retries', 'allow_reasoning'];
                         if (pipelineType.includes('rag')) {
                            settingsWhitelist.push('rag_settings', 'search_settings');
                        }
                        if (pipelineType.includes('agent')) {
                            settingsWhitelist.push('agent_config');
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
                            // Only check for retry if we are NOT starting a new trial explicitly
                            const lastTrial = data.trials[data.trials.length - 1];
                            if (lastTrial && lastTrial.status === 'completed' && lastTrial.is_correct === false && !data.session.is_completed) {
                                if (data.trials.length < data.session.max_retries) {
                                    // Check if we should auto-retry (if session is running)
                                    if (sessionAbortController && !sessionAbortController.signal.aborted) {
                                         sessionRetryTimeout = setTimeout(() => {
                                             if (sessionAbortController && !sessionAbortController.signal.aborted) {
                                                 window.retryTrial(lastTrial.id); 
                                             }
                                         }, 1500);
                                    }
                                } else {
                                    // Max retries reached, session done
                                    if (sessionAbortController) resetSessionUI();
                                }
                            } else if (data.session.is_completed) {
                                // Session completed
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
            function loadRun(groupId) {
                 let loadRunUrl = BenchmarkUrls.vanillaLlmMultiTurn.loadRun(groupId);
                 if (pipelineType === 'browser_agent') loadRunUrl = BenchmarkUrls.browserAgent.loadRun(groupId);
                 else if (pipelineType === 'vanilla_agent') loadRunUrl = BenchmarkUrls.vanillaAgent.loadRun(groupId);
                 else if (pipelineType.includes('rag')) loadRunUrl = BenchmarkUrls.ragMultiTurn.loadRun(groupId);

                 fetch(loadRunUrl).then(res => res.json()).then(data => {
                     if (data.error) { alert(data.error); return; }
                     currentPipelineResults = data.results;
                     
                     // Show stats container first so updateStatsUI can find elements if they depend on visibility
                     const statsContainer = document.getElementById('statistics-container');
                     if (statsContainer) statsContainer.style.display = 'block';

                     BenchmarkUtils.MultiTurnUtils.updateStatsUI(data.results, data.group_name, (sid) => {
                         document.getElementById('session-container').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                         loadSession(sid);
                     });
                     
                     const settingsWhitelist = ['llm_model', 'llm_base_url', 'max_retries', 'allow_reasoning'];
                     if (pipelineType.includes('rag')) settingsWhitelist.push('rag_settings', 'search_settings');
                     if (pipelineType.includes('agent')) settingsWhitelist.push('agent_config');
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
                    
                    // UI Lock
                    startSessionBtn.style.display = 'none';
                    if (stopSessionBtn) stopSessionBtn.style.display = 'inline-block'; // Or block
                    BenchmarkUtils.toggleConfigurationInputs(true);
                    
                    sessionAbortController = new AbortController();
                    const signal = sessionAbortController.signal;
                    
                    let singleSessionPipelineType = pipelineType;
                    // Only allow RAG mode override if we are on a RAG multi-turn page
                    if (document.getElementById('rag_mode_select') && pipelineType.startsWith('rag_multi_turn')) {
                        singleSessionPipelineType = document.getElementById('rag_mode_select').value;
                    }

                    fetch(BenchmarkUrls.multiTurn.createSession, {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrfToken},
                        body: JSON.stringify({
                            question: qData.question,
                            ground_truths: qData.answer,
                            pipeline_type: singleSessionPipelineType
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
                         const currentSessionId = activeSessionId; // Capture ID
                         fetch(BenchmarkUrls.multiTurn.stopSession, {
                             method: 'POST',
                             headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                             body: JSON.stringify({ session_id: currentSessionId })
                         })
                         .then(res => res.json())
                         .then(data => {
                             if (data.status === 'ok') {
                                 // Reload session to update UI (remove spinner, show error)
                                 loadSession(currentSessionId);
                             }
                         })
                         .catch(console.error);
                    }
                    resetSessionUI();
                });
            }

            // --- Pipeline Run ---
            document.getElementById('run-pipeline-btn').addEventListener('click', function() {
                const currentPipelineId = BenchmarkUtils.generateUUID();
                const ui = {
                    runBtn: this,
                    stopBtn: document.getElementById('stop-pipeline-btn'),
                    progressBar: document.getElementById('pipeline-progress-bar'),
                    statusDiv: document.getElementById('pipeline-status'),
                    resultsBody: null, 
                    spinner: null
                };
                
                document.getElementById('statistics-container').style.display = 'block';
                document.getElementById('stats-details-tbody').innerHTML = '';
                document.getElementById('pipeline-progress').style.display = 'block';
                document.getElementById('results-header-text').textContent = 'Live Pipeline Results';

                const currentLlmSettings = {
                    llm_base_url: document.getElementById('llm_base_url').value,
                    llm_api_key: document.getElementById('llm_api_key').value,
                    llm_model: document.getElementById('llm_model').value,
                    max_retries: document.getElementById('max_retries') ? document.getElementById('max_retries').value : null,
                };
                BenchmarkUtils.BenchmarkRenderer.renderRunConfiguration({ llm_settings: currentLlmSettings });
                
                currentPipelineResults = [];
                
                const formData = new FormData();
                formData.append('csrfmiddlewaretoken', csrfToken);
                formData.append('dataset_id', document.getElementById('dataset-selector').value);
                formData.append('pipeline_id', currentPipelineId);
                formData.append('llm_base_url', currentLlmSettings.llm_base_url);
                formData.append('llm_api_key', currentLlmSettings.llm_api_key);
                formData.append('llm_model', currentLlmSettings.llm_model);
                if (currentLlmSettings.max_retries) formData.append('max_retries', currentLlmSettings.max_retries);
                
                if (buildFormData) buildFormData(formData);
                
                let runUrl = BenchmarkUrls.vanillaLlmMultiTurn.runPipeline;
                if (pipelineType === 'browser_agent') runUrl = BenchmarkUrls.browserAgent.runPipeline;
                else if (pipelineType === 'vanilla_agent') runUrl = BenchmarkUrls.vanillaAgent.runPipeline;
                else if (pipelineType.includes('rag')) runUrl = BenchmarkUrls.ragMultiTurn.runPipeline;

                pipelineController = BenchmarkUtils.PipelineRunner.start({
                    url: runUrl,
                    formData: formData,
                    ui: ui,
                    totalItems: 0, // Dynamic total items
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
                             if (data.error) { ui.statusDiv.textContent = `Error: ${data.error}`; return; }
                             currentPipelineResults.push(data);
                             BenchmarkUtils.MultiTurnUtils.updateStatsUI(currentPipelineResults, data.group_name || "Current Run", (sid) => {
                                 document.getElementById('session-container').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                                 loadSession(sid);
                             });
                             BenchmarkUtils.MultiTurnUtils.addNewSessionToList('session-list', data.session_id, { question: data.question }, null, data.group_id, data.group_name, 'Finished');
                        }
                    }
                });
            });

            // --- Stop Pipeline ---
            function stopPipeline() {
                if (pipelineController) pipelineController.abort();
                if (pipelineController && pipelineController.pipelineId) {
                    let strategyData = { pipeline_id: pipelineController.pipelineId };

                     let stopUrl = BenchmarkUrls.vanillaLlmMultiTurn.stopPipeline;
                     if (pipelineType === 'browser_agent') stopUrl = BenchmarkUrls.browserAgent.stopPipeline;
                     else if (pipelineType === 'vanilla_agent') stopUrl = BenchmarkUrls.vanillaAgent.stopPipeline;
                     else if (pipelineType.includes('rag')) stopUrl = BenchmarkUrls.ragMultiTurn.stopPipeline;

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
                // Handle Delete Group Button
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

                // Handle Checkboxes
                if (e.target.closest('input[type="checkbox"]')) {
                    return; 
                }

                // Handle Session Click
                const target = e.target.closest('.session-details');
                if (target) { 
                    e.preventDefault();
                    loadSession(target.dataset.sessionId); 
                    return;
                }
                
                // Handle Group Summary Click
                const groupSummary = e.target.closest('.group-summary');
                if (groupSummary) { 
                    // Do NOT preventDefault() to allow <details> toggle behavior
                    if (groupSummary.dataset && groupSummary.dataset.groupId) {
                        try {
                            loadRun(groupSummary.dataset.groupId); 
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
        }
    };
