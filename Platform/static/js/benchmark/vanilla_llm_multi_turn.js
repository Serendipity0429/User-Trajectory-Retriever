document.addEventListener('DOMContentLoaded', function() {
    BenchmarkUtils.setupConfigurationHandlers();
    const questions = JSON.parse(document.getElementById('questions-data').textContent);
    let activeSessionId = null;
    let sessionTrials = [];
    let pipelineController = { aborted: false };
    let currentPipelineResults = [];

    // --- Configuration Management ---
    const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
    BenchmarkUtils.setupConfigurationActionHandlers(window.benchmarkUrls, csrfToken, false, false);

    const startBtn = document.getElementById('start-session-btn');
    const questionSelect = document.getElementById('question-select');
        const sessionList = document.getElementById('session-list');
        const sessionContainer = document.getElementById('session-container');
        const noSessionSelected = document.getElementById('no-session-selected');
    
            // --- Batch Delete ---
            BenchmarkUtils.setupBatchSelection(
                'session-list',
                'select-all-checkbox',
                'session-checkbox',
                'delete-selected-btn',
                (selectedSessionIds, selectedGroupIds) => {
                    if (selectedSessionIds.length === 0 && selectedGroupIds.length === 0) return;
        
                    let confirm_msg = "Are you sure you want to delete the selected items?\n";
                    if (selectedGroupIds.length > 0) {
                        confirm_msg += `\n- ${selectedGroupIds.length} group(s) and all their sessions`;
                    }
                    if (selectedSessionIds.length > 0) {
                        confirm_msg += `\n- ${selectedSessionIds.length} individual session(s)`;
                    }
        
                    if (!confirm(confirm_msg)) return;
        
                    const deletePromises = [];
        
                    if (selectedSessionIds.length > 0) {
                        const promise = fetch('/benchmark/api/multi_turn/batch_delete_sessions/', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').getAttribute('content') },
                            body: JSON.stringify({ session_ids: selectedSessionIds })
                        }).then(res => res.json());
                        deletePromises.push(promise);
                    }
        
                    selectedGroupIds.forEach(groupId => {
                        const promise = fetch(`/benchmark/api/multi_turn/delete_session_group/${groupId}/`, {
                            method: 'DELETE',
                            headers: { 'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').getAttribute('content') }
                        }).then(res => res.json());
                        deletePromises.push(promise);
                    });
        
                    Promise.all(deletePromises)
                        .then(results => {
                            let hasError = false;
                            results.forEach(result => {
                                if (result.status !== 'ok') {
                                    hasError = true;
                                    console.error('Deletion failed for an item:', result);
                                }
                            });
        
                            if (hasError) {
                                alert('Some items could not be deleted. Please check the console and refresh the page.');
                            } else {
                                window.location.reload();
                            }
                        })
                        .catch(err => {
                            console.error('An error occurred during deletion:', err);
                            alert('An error occurred during deletion. Please check the console and refresh the page.');
                        });
                },
                'group-select-checkbox' // itemGroupIdClass
            );    
        // --- Session Management ---
        startBtn.addEventListener('click', function() {
            const selectedIndex = questionSelect.value;
            if (selectedIndex === "") {
                alert('Please select a question.');
                return;
            }
            console.log("Selected Index:", selectedIndex);
            const questionData = questions[selectedIndex];
            console.log("Question Data:", questionData);
            
            startBtn.disabled = true;
            startBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Starting...';
    
            fetch(window.benchmarkUrls.createSession, {
                method: 'POST',
                headers: {'Content-Type': 'application/json', 'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').getAttribute('content')},
                body: JSON.stringify({
                    question: questionData.question,
                    ground_truths: questionData.answer,
                    pipeline_type: 'vanilla_llm_multi_turn'
                })
            })
            .then(res => res.json())
            .then(data => {
                            if(data.error) {
                                alert('Error starting session: ' + data.error);
                                return;
                            }
                            BenchmarkUtils.MultiTurnUtils.addNewSessionToList('session-list', data.session_id, questionData, null);
                            loadSession(data.session_id, data.trial_id);            })
            .catch(err => {
                console.error("Error creating session:", err);
                alert("An error occurred while trying to start a new session. Please check the console for details.");
            })
            .finally(() => {
                startBtn.disabled = false;
                startBtn.innerHTML = 'Start';
            });
        });
    
        sessionList.addEventListener('click', function(e) {
            const target = e.target.closest('.session-details');
            if (target) {
                e.preventDefault();
                const sessionId = target.dataset.sessionId;
                loadSession(sessionId);
            }

            const groupSummary = e.target.closest('.group-summary');
            if (groupSummary) {
                e.preventDefault();
                const groupId = groupSummary.dataset.groupId;
                loadRun(groupId);
            }

            const deleteBtn = e.target.closest('.delete-group-btn');
            if (deleteBtn) {
                e.preventDefault();
                const groupId = deleteBtn.dataset.groupId;
                if (confirm(`Are you sure you want to delete this entire group and all its sessions?`)) {
            const promise = fetch(`/benchmark/api/multi_turn/delete_session_group/${groupId}/`, {
                        method: 'DELETE',
                        headers: { 'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').getAttribute('content') }
                    })
                    .then(res => res.json())
                    .then(data => {
                        if (data.status === 'ok') {
                            // remove the group from the list
                            deleteBtn.closest('.list-group-item').remove();
                            window.location.reload();
                        } else {
                            alert('Error deleting session group: ' + (data.message || 'Unknown error'));
                        }
                    });
                }
            }
        });
    function loadSession(sessionId, initialTrialId = null) {
        activeSessionId = sessionId;
        fetch(`/benchmark/api/multi_turn/get_session/${sessionId}/`)
            .then(res => res.json())
            .then(data => {
                sessionTrials = data.trials; // Keep sessionTrials updated locally for other functions
                BenchmarkUtils.MultiTurnUtils.renderSession(data.session, data.trials, { sessionTrials: sessionTrials });
                BenchmarkUtils.renderRunConfiguration(data.session.settings_snapshot, ['llm_model', 'llm_base_url', 'max_retries']);
                sessionContainer.style.display = 'block';
                noSessionSelected.style.display = 'none';

                const deleteBtn = document.getElementById('delete-session-btn');
                if (data.session.group_id) {
                    deleteBtn.style.display = 'none';
                } else {
                    deleteBtn.style.display = 'inline-block';
                }

                if (initialTrialId) {
                    executeTrial(initialTrialId, sessionId);
                } else {
                    const lastTrial = data.trials[data.trials.length - 1];
                    const session = data.session;
                    if (lastTrial && lastTrial.status === 'completed' && lastTrial.is_correct === false && !session.is_completed) {
                        if (data.trials.length < session.max_retries) {
                            // Automatically retry after a short delay to allow user to see the feedback
                            setTimeout(() => {
                                window.retryTrial(lastTrial.id);
                            }, 1500);
                        }
                    }
                }
            });
    }

    function executeTrial(trialId, sessionId) {
        fetch(`/benchmark/api/multi_turn/run_trial/${trialId}/`)
            .then(res => res.json())
            .then(data => {
                if(data.error) {
                    alert(`Error in trial #${trialId}: ${data.error}`);
                }
                // Reload the session to get the updated trial data
                if (sessionId) {
                    loadSession(sessionId);
                }
            })
            .catch(err => {
                alert(`A network error occurred while running trial #${trialId}.`);
                if (sessionId) {
                    loadSession(sessionId);
                }
            });
    }



    // --- Search Results Modal ---
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

    // --- Actions ---
    window.retryTrial = function(trialId) {
        const trial = sessionTrials.find(t => t.id === trialId);
        const feedback = trial ? trial.feedback : "";

        fetch(`/benchmark/api/multi_turn/retry_session/${trialId}/`, {
            method: 'POST',
            headers:{'Content-Type': 'application/json', 'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').getAttribute('content')},
            body: JSON.stringify({ feedback: feedback, is_correct: false })
        })
        .then(res => res.json())
        .then(data => {
            if (data.error) {
                alert('Error: ' + data.error);
                return;
            }

            // Reload session to show the new trial in 'processing' state
            loadSession(activeSessionId);

            if (data.status === 'retrying') {
                executeTrial(data.new_trial_id, activeSessionId);
            }
        });
    }

    document.getElementById('delete-session-btn').addEventListener('click', function() {
        if (!activeSessionId || !confirm('Are you sure you want to delete this session?')) return;

        fetch(`/benchmark/api/multi_turn/delete_session/${activeSessionId}/`, {
            method: 'DELETE',
            headers:{'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').getAttribute('content')}
        })
        .then(res => res.json())
        .then(data => {
            if (data.status === 'ok') {
                document.querySelector(`#session-list [data-session-id='${activeSessionId}']`).remove();
                sessionContainer.style.display = 'none';
                noSessionSelected.style.display = 'block';
                activeSessionId = null;
            } else {
                alert('Error deleting session: ' + data.message);
            }
        });
    });

    document.getElementById('export-session-btn').addEventListener('click', function() {
        if (!activeSessionId) return;
        window.location.href = `/benchmark/api/multi_turn/export_session/${activeSessionId}/`;
    });


    // --- Load Run ---
    function loadRun(groupId) {
        if (!groupId) {
            return;
        }

        // Optional: Add some visual feedback
        const summaryElement = document.querySelector(`.group-summary[data-group-id='${groupId}']`);
        const originalColor = summaryElement.style.color;
        summaryElement.style.color = 'blue';


        fetch(`/benchmark/api/multi_turn/load_run/${groupId}/`)
            .then(res => res.json())
            .then(data => {
                if (data.error) {
                    alert('Error loading run: ' + data.error);
                    return;
                }
                currentPipelineResults = data.results;
                BenchmarkUtils.MultiTurnUtils.updateStatsUI(data.results, data.group_name, (sessionId) => {
                    const sessionContainer = document.getElementById('session-container');
                    sessionContainer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                    loadSession(sessionId);
                });
                BenchmarkUtils.renderRunConfiguration(data.settings, ['llm_model', 'llm_base_url', 'max_retries']);
                const statsContainer = document.getElementById('statistics-container');
                statsContainer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            })
            .catch(err => {
                console.error("Error loading run:", err);
                alert("An error occurred while trying to load the run. Please check the console for details.");
            })
            .finally(() => {
                // Restore original color
                summaryElement.style.color = originalColor;
            });
    }




    // --- QA Pipeline ---
    document.getElementById('run-pipeline-btn').addEventListener('click', runQAPipeline);
    
    function runQAPipeline() {
        const runBtn = document.getElementById('run-pipeline-btn');
        const stopBtn = document.getElementById('stop-pipeline-btn');
        const statusDiv = document.getElementById('pipeline-status');
        const progressBar = document.getElementById('pipeline-progress-bar');
        const resultsHeader = document.getElementById("results-header-text");

        runBtn.style.display = 'none';
        stopBtn.style.display = 'block';
        stopBtn.disabled = false;
        
        // Reset stats
        document.getElementById('statistics-container').style.display = 'block';
        document.getElementById('stats-details-tbody').innerHTML = '';
        document.getElementById('stats-accuracy').textContent = '0.00%';
        document.getElementById('stats-correct-count').textContent = '0';
        document.getElementById('stats-incorrect-count').textContent = '0';
        document.getElementById('stats-error-count').textContent = '0';
        document.getElementById('stats-avg-trials-all').textContent = '0.00';
        document.getElementById('stats-avg-trials-success').textContent = '0.00';
        document.getElementById('stats-first-try-success').textContent = '0.00%';
        document.getElementById('stats-give-up-rate').textContent = '0.00%';
        resultsHeader.textContent = 'Live Pipeline Results';

        document.getElementById('pipeline-progress').style.display = 'block';
        progressBar.style.width = '0%';
        progressBar.textContent = '0%';
        statusDiv.textContent = 'Initializing pipeline...';
        BenchmarkUtils.toggleConfigurationInputs(true);

        currentPipelineResults = [];
        let completedCount = 0;
        let totalQuestions = questions.length; // Default

        // Controller to stop the fetch
        pipelineController = new AbortController();
        const signal = pipelineController.signal;
        
        // Generate a temporary ID for tracking stop requests if needed
        pipelineController.id = BenchmarkUtils.generateUUID();

        const currentLlmSettings = {
            llm_base_url: document.getElementById('llm_base_url').value,
            llm_api_key: document.getElementById('llm_api_key').value,
            llm_model: document.getElementById('llm_model').value,
            max_retries: document.getElementById('max_retries') ? document.getElementById('max_retries').value : null,
        };

        BenchmarkUtils.renderRunConfiguration({ llm_settings: currentLlmSettings });

        const datasetId = document.getElementById('dataset-selector').value;
        const formData = new FormData();
        formData.append('csrfmiddlewaretoken', document.querySelector('meta[name="csrf-token"]').getAttribute('content'));
        formData.append('dataset_id', datasetId);
        formData.append('llm_base_url', currentLlmSettings.llm_base_url);
        formData.append('llm_api_key', currentLlmSettings.llm_api_key);
        formData.append('llm_model', currentLlmSettings.llm_model);
        if (currentLlmSettings.max_retries) formData.append('max_retries', currentLlmSettings.max_retries);
        formData.append('pipeline_id', pipelineController.id);

        // Fetch total questions if dataset is selected
        if (datasetId) {
             fetch(`/benchmark/api/datasets/${datasetId}/questions/`)
                .then(res => res.json())
                .then(data => {
                    if (!data.error) {
                        totalQuestions = data.questions.length;
                    }
                });
        }

        fetch(window.benchmarkUrls.runPipeline, { method: 'POST', body: formData, signal: signal })
        .then(response => {
            BenchmarkUtils.processStreamedResponse(
                response,
                (data) => {
                    if (data.error) {
                        console.error("Pipeline Error:", data.error);
                        statusDiv.textContent = `Error: ${data.error}`;
                        return;
                    }

                    if (data.is_meta) {
                         if (data.type === 'info') statusDiv.textContent = data.message;
                         if (data.type === 'session_created') {
                             BenchmarkUtils.MultiTurnUtils.addNewSessionToList('session-list', data.session_id, { question: data.question }, null, data.group_id, data.group_name, 'Processing...');
                             loadSession(data.session_id);
                         }
                         if (data.type === 'trial_started' || data.type === 'trial_completed') {
                             if (activeSessionId && String(activeSessionId) === String(data.session_id)) {
                                 loadSession(data.session_id);
                             }
                         }
                         return;
                    }

                    // data corresponds to one completed session result from BaseMultiTurnPipeline
                    currentPipelineResults.push(data);
                    completedCount++;

                    // Update Progress
                    const progress = totalQuestions > 0 ? Math.round((completedCount / totalQuestions) * 100) : 0;
                    progressBar.style.width = `${progress}%`;
                    progressBar.textContent = `${progress}%`;
                    statusDiv.textContent = `Processed ${completedCount} questions...`;

                    // Update Stats
                    BenchmarkUtils.MultiTurnUtils.updateStatsUI(currentPipelineResults, data.group_name || "Current Run", (sessionId) => {
                        const sessionContainer = document.getElementById('session-container');
                        sessionContainer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                        loadSession(sessionId);
                    });

                    // Add to Session List
                    BenchmarkUtils.MultiTurnUtils.addNewSessionToList('session-list', data.session_id, { question: data.question }, null, data.group_id, data.group_name, 'Finished');
                },
                () => { // onComplete
                    BenchmarkUtils.toggleConfigurationInputs(false);
                    runBtn.style.display = 'block';
                    stopBtn.style.display = 'none';
                    statusDiv.textContent = `Pipeline finished. Processed ${completedCount} questions.`;
                    pipelineController.id = null;
                },
                (error) => { // onError
                    if (error.name === 'AbortError') {
                        statusDiv.textContent = "Pipeline stopped by user.";
                    } else {
                        console.error('Error during stream processing:', error);
                        statusDiv.textContent = `Error: ${error.message}`;
                    }
                    BenchmarkUtils.toggleConfigurationInputs(false);
                    runBtn.style.display = 'block';
                    stopBtn.style.display = 'none';
                    pipelineController.id = null;
                },
                signal
            );
        })
        .catch(error => {
            if (error.name === 'AbortError') {
                console.log('Fetch aborted by user.');
                statusDiv.textContent = "Pipeline stopped by user.";
            } else {
                console.error('Error starting the pipeline:', error);
                alert('Failed to start the pipeline.');
                statusDiv.textContent = "Failed to start pipeline.";
            }
            BenchmarkUtils.toggleConfigurationInputs(false);
            runBtn.style.display = 'block';
            stopBtn.style.display = 'none';
            pipelineController.id = null;
        });
    }

    function stopPipeline() {
        if (pipelineController) {
            pipelineController.abort();
        }
        if (pipelineController.id) {
            const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
            fetch(window.benchmarkUrls.stopVanillaLlmMultiTurnPipeline, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({ pipeline_id: pipelineController.id }),
                keepalive: true
            }).catch(e => console.error("Stop request failed", e));
        }
    }

    document.getElementById('stop-pipeline-btn').addEventListener('click', stopPipeline);
    window.addEventListener('beforeunload', stopPipeline);

    function exportResultsAsCSV() {
        const headers = ["#", "Question", "Final Answer", "Ground Truths", "Result", "Trials"];
        const rowMapper = (result, index) => {
            const finalAnswer = result.final_answer || 'N/A';
            const groundTruths = Array.isArray(result.ground_truths) ? result.ground_truths.join('; ') : result.ground_truths;
            
            let resultText = 'Error';
            if (result.correct === true) resultText = 'Correct';
            else if (result.correct === false) resultText = 'Incorrect';

            return [
                index + 1,
                result.question,
                finalAnswer,
                groundTruths,
                resultText,
                result.trials
            ];
        };
        BenchmarkUtils.exportToCSV(currentPipelineResults, 'pipeline-results', headers, rowMapper);
    }

    document.getElementById('export-results-btn').addEventListener('click', exportResultsAsCSV);
});
