document.addEventListener('DOMContentLoaded', function() {
    const questions = JSON.parse(document.getElementById('questions-data').textContent);
    let activeSessionId = null;
    let sessionTrials = [];
    let pipelineController = { aborted: false };
    let currentPipelineResults = [];

    const startBtn = document.getElementById('start-session-btn');
    const questionSelect = document.getElementById('question-select');
        const sessionList = document.getElementById('session-list');
        const sessionContainer = document.getElementById('session-container');
        const noSessionSelected = document.getElementById('no-session-selected');
    
        // --- Batch Delete ---
        const deleteSelectedBtn = document.getElementById('delete-selected-btn');
    
        function getSelectAllCheckbox() { return document.getElementById('select-all-checkbox'); }
        function getSessionCheckboxes() { return document.querySelectorAll('.session-checkbox'); }
        function getGroupCheckboxes() { return document.querySelectorAll('.group-select-checkbox'); }
    
        function toggleDeleteButton() {
            const anySessionChecked = Array.from(getSessionCheckboxes()).some(cb => cb.checked);
            const anyGroupChecked = Array.from(getGroupCheckboxes()).some(cb => cb.checked);
            const anyChecked = anySessionChecked || anyGroupChecked;
            deleteSelectedBtn.style.display = anyChecked ? 'inline-block' : 'none';
    
            const selectAllCheckbox = getSelectAllCheckbox();
            if (selectAllCheckbox) {
                const allSessionCheckboxes = Array.from(getSessionCheckboxes());
                const allGroupCheckboxes = Array.from(getGroupCheckboxes());
                const allCheckboxes = allSessionCheckboxes.concat(allGroupCheckboxes);
                const allChecked = allCheckboxes.length > 0 && allCheckboxes.every(cb => cb.checked);
                selectAllCheckbox.checked = anyChecked && allChecked;
            }
        }
    
        function selectAllHandler(e) {
            const isChecked = e.target.checked;
            getGroupCheckboxes().forEach(checkbox => checkbox.checked = isChecked);
            getSessionCheckboxes().forEach(checkbox => checkbox.checked = isChecked);
            toggleDeleteButton();
        }

        if (getSelectAllCheckbox()) {
            getSelectAllCheckbox().addEventListener('change', selectAllHandler);
        }
        
        sessionList.addEventListener('change', function(e) {
            if (e.target.classList.contains('session-checkbox')) {
                toggleDeleteButton();
            }
            if (e.target.classList.contains('group-select-checkbox')) {
                toggleDeleteButton();
            }
        });
    
        deleteSelectedBtn.addEventListener('click', function() {
            const selectedSessionIds = Array.from(getSessionCheckboxes())
                .filter(cb => cb.checked)
                .map(cb => cb.dataset.sessionId);
            
            const selectedGroupIds = Array.from(getGroupCheckboxes())
                .filter(cb => cb.checked)
                .map(cb => cb.dataset.groupId);

            const session_count = selectedSessionIds.length;
            const group_count = selectedGroupIds.length;

            if (session_count === 0 && group_count === 0) {
                return;
            }

            let confirm_msg = "Are you sure you want to delete the selected items!\n";
            if (group_count > 0) {
                confirm_msg += "\n- " + group_count + " group(s) and all their sessions";
            }
            if (session_count > 0) {
                confirm_msg += "\n- " + session_count + " individual session(s)";
            }

            if (!confirm(confirm_msg)) {
                return;
            }
    
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
                        // Easiest way to reflect all changes is to just reload.
                        window.location.reload();
                    }
                })
                .catch(err => {
                    console.error('An error occurred during deletion:', err);
                    alert('An error occurred during deletion. Please check the console and refresh the page.');
                });
        });
    
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
                addNewSessionToList(data.session_id, questionData);
                loadSession(data.session_id, data.trial_id);
            })
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
                renderSession(data.session, data.trials);
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

    // --- Rendering ---
    function renderSession(session, trials) {
        sessionTrials = trials;
        document.getElementById('session-header').textContent = `Session #${session.id}`;
        document.getElementById('session-question').textContent = session.question;

        const gtContainer = document.getElementById('session-ground-truths');
        gtContainer.innerHTML = '';

        const GROUNDTRUTH_DISPLAY_LIMIT = 3; 

        if (session.ground_truths.length > GROUNDTRUTH_DISPLAY_LIMIT) {
            const initialGroundTruths = session.ground_truths.slice(0, GROUNDTRUTH_DISPLAY_LIMIT);
            initialGroundTruths.forEach(gt => {
                const el = document.createElement('span');
                el.className = 'badge bg-secondary me-1';
                el.textContent = gt;
                gtContainer.appendChild(el);
            });

            const showMoreBtn = document.createElement('button');
            showMoreBtn.className = 'btn btn-link btn-sm p-0';
            showMoreBtn.textContent = `Show ${session.ground_truths.length - GROUNDTRUTH_DISPLAY_LIMIT} more`;
            showMoreBtn.setAttribute('type', 'button');
            gtContainer.appendChild(showMoreBtn);

            const fullGroundTruthsDiv = document.createElement('div');
            fullGroundTruthsDiv.style.display = 'none'; // Initially hidden
            session.ground_truths.slice(GROUNDTRUTH_DISPLAY_LIMIT).forEach(gt => {
                const el = document.createElement('span');
                el.className = 'badge bg-secondary me-1';
                el.textContent = gt;
                fullGroundTruthsDiv.appendChild(el);
            });
            gtContainer.appendChild(fullGroundTruthsDiv);

            const showLessBtn = document.createElement('button');
            showLessBtn.className = 'btn btn-link btn-sm p-0 ms-2';
            showLessBtn.textContent = `Show less`;
            showLessBtn.setAttribute('type', 'button');
            showLessBtn.style.display = 'none'; // Initially hidden
            gtContainer.appendChild(showLessBtn);


            showMoreBtn.addEventListener('click', () => {
                fullGroundTruthsDiv.style.display = 'block';
                showMoreBtn.style.display = 'none';
                showLessBtn.style.display = 'inline';
            });

            showLessBtn.addEventListener('click', () => {
                fullGroundTruthsDiv.style.display = 'none';
                showMoreBtn.style.display = 'inline';
                showLessBtn.style.display = 'none';
            });

        } else {
            session.ground_truths.forEach(gt => {
                const el = document.createElement('span');
                el.className = 'badge bg-secondary me-1';
                el.textContent = gt;
                gtContainer.appendChild(el);
            });
        }

        const trialsContainer = document.getElementById('trials-container');
        trialsContainer.innerHTML = '';
        trials.forEach(trial => {
            trialsContainer.appendChild(BenchmarkUtils.BenchmarkRenderer.renderTrial(trial, session.is_completed, trials.length, session.max_retries));
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
            headers: {'Content-Type': 'application/json', 'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').getAttribute('content')},
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
            headers: {'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').getAttribute('content')}
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

    function testConnection() {
        const data = {
            llm_base_url: document.getElementById('llm_base_url').value,
            llm_api_key: document.getElementById('llm_api_key').value,
        };
        const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
        BenchmarkUtils.testConnection(window.benchmarkUrls.testLlmConnection, csrfToken, data, 'test-connection-result', 'test-connection-btn');
    }

    function saveSettings() {
        const data = {
            llm_base_url: document.getElementById('llm_base_url').value,
            llm_api_key: document.getElementById('llm_api_key').value,
            llm_model: document.getElementById('llm_model').value,
            max_retries: document.getElementById('max_retries').value
        };
        const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
        BenchmarkUtils.saveSettings(window.benchmarkUrls.saveLlmSettings, csrfToken, data, 'save-settings-btn');
    }

    function restoreDefaults() {
        BenchmarkUtils.restoreDefaults(window.benchmarkUrls.getLlmEnvVars, function(data) {
            document.getElementById('llm_base_url').value = data.llm_base_url;
            document.getElementById('llm_api_key').value = data.llm_api_key;
            document.getElementById('llm_model').value = data.llm_model;
            saveSettings();
        });
    }

    document.getElementById('save-settings-btn').addEventListener('click', saveSettings);
    document.getElementById('test-connection-btn').addEventListener('click', testConnection);
    document.getElementById('restore-defaults-btn').addEventListener('click', restoreDefaults);


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
                displayStats(data.results, data.group_name);
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
    document.getElementById('stop-pipeline-btn').addEventListener('click', () => {
        if (pipelineController) {
            pipelineController.aborted = true;
        }
    });

    function addNewSessionToList(sessionId, questionData, groupId = null, groupName = null) {
        // If this is the first session ever, remove "no sessions" and add select-all header
        if (document.querySelector('.no-sessions')) {
            document.querySelector('.no-sessions').remove();
            const selectAllContainer = document.createElement('div');
            selectAllContainer.className = 'list-group-item bg-light';
            selectAllContainer.id = 'select-all-container';
            selectAllContainer.innerHTML = `
                <input class="form-check-input" type="checkbox" id="select-all-checkbox">
                <label class="form-check-label ms-2" for="select-all-checkbox">Select All</label>`;
            sessionList.prepend(selectAllContainer);
            getSelectAllCheckbox().addEventListener('change', selectAllHandler);
        }

        const newSessionItem = document.createElement('div');
        newSessionItem.className = 'list-group-item d-flex align-items-center session-item-container';
        newSessionItem.innerHTML = `
            <input class="form-check-input session-checkbox" type="checkbox" value="${sessionId}" data-session-id="${sessionId}">
            <div class="ms-3 flex-grow-1 session-details" data-session-id="${sessionId}" style="cursor: pointer;">
                <div class="d-flex w-100 justify-content-between">
                    <h6 class="mb-1">Session #${sessionId}</h6>
                    <small class="text-muted">Now</small>
                </div>
                <p class="mb-1 small text-muted">${questionData.question.substring(0, 100)}...</p>
            </div>`;
        
        if (groupId) {
            let groupContainer = document.getElementById(`session-group-${groupId}`);
            if (!groupContainer) {
                // Create the group container if it doesn't exist
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
                selectAllDiv.after(groupEl);
                groupContainer = document.getElementById(`session-group-${groupId}`);
            }
            newSessionItem.classList.add("ps-4");
            groupContainer.prepend(newSessionItem);
            
            // Update session count
            const countEl = document.getElementById(`group-session-count-${groupId}`);
            const currentCount = groupContainer.children.length;
            countEl.textContent = `(${currentCount} sessions)`;

        } else {
            const selectAllDiv = document.getElementById('select-all-container');
            selectAllDiv.after(newSessionItem);
        }
    }

    async function runSessionLifecycle(sessionId, initialTrialId) {
        let currentTrialId = initialTrialId;
        
        while (true) {
            if (pipelineController.aborted) throw new Error("Pipeline aborted");

            // 1. Run Trial
            try {
                const res = await fetch(`/benchmark/api/multi_turn/run_trial/${currentTrialId}/`);
                const trialData = await res.json();
                if (trialData.error) throw new Error(trialData.error);
            } catch (e) {
                console.error(`Trial ${currentTrialId} failed:`, e);
                return { 
                    question: "Error", 
                    correct: "error", 
                    trials: 0, 
                    session_id: sessionId, 
                    final_answer: e.message, 
                    ground_truths: [] 
                };
            }

            // 2. Refresh Session State
            const sessionRes = await fetch(`/benchmark/api/multi_turn/get_session/${sessionId}/`);
            const sessionData = await sessionRes.json();
            const session = sessionData.session;
            const trials = sessionData.trials;
            const lastTrial = trials[trials.length - 1];

            // Update UI if this is the active session
            if (activeSessionId == sessionId) {
                 renderSession(session, trials);
            }

            // 3. Check for completion
            if (session.is_completed) {
                return {
                    question: session.question,
                    correct: lastTrial ? lastTrial.is_correct : false,
                    trials: trials.length,
                    session_id: sessionId,
                    final_answer: lastTrial ? lastTrial.answer : "No trials",
                    ground_truths: session.ground_truths,
                    max_retries: session.max_retries
                };
            }

            // 4. Check for Retry
            if (lastTrial && lastTrial.status === 'completed' && lastTrial.is_correct === false) {
                 if (trials.length < session.max_retries) {
                     // Retry
                     try {
                        const retryRes = await fetch(`/benchmark/api/multi_turn/retry_session/${lastTrial.id}/`, {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json', 'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').getAttribute('content')},
                            body: JSON.stringify({ feedback: lastTrial.feedback, is_correct: false })
                        });
                        const retryData = await retryRes.json();
                        if (retryData.error) throw new Error(retryData.error);
                        
                        if (retryData.status === 'retrying') {
                            currentTrialId = retryData.new_trial_id;
                            // Update UI to show processing
                            if (activeSessionId == sessionId) {
                                fetch(`/benchmark/api/multi_turn/get_session/${sessionId}/`)
                                    .then(r=>r.json()).then(d=>renderSession(d.session, d.trials));
                            }
                            continue; 
                        } else {
                            break; 
                        }
                     } catch (e) {
                         console.error(`Retry failed for trial ${lastTrial.id}:`, e);
                         return { 
                            question: session.question, 
                            correct: "error", 
                            trials: trials.length, 
                            session_id: sessionId, 
                            final_answer: e.message, 
                            ground_truths: session.ground_truths 
                        };
                     }
                 } else {
                     // Max retries reached, return final result
                     return {
                        question: session.question,
                        correct: lastTrial ? lastTrial.is_correct : false,
                        trials: trials.length,
                        session_id: sessionId,
                        final_answer: lastTrial ? lastTrial.answer : "N/A",
                        ground_truths: session.ground_truths,
                        max_retries: session.max_retries
                    };
                 }
            } else {
                 return { 
                    question: session.question, 
                    correct: "error", 
                    trials: trials.length, 
                    session_id: sessionId, 
                    final_answer: "Unexpected state", 
                    ground_truths: session.ground_truths 
                };
            }
        }
        
        // Fallback
        return {
            question: "Unknown",
            correct: false,
            trials: 0,
            session_id: sessionId,
            final_answer: "N/A",
            ground_truths: [],
            max_retries: 0
        };
    }

    async function processQuestion(questionData, groupId = null) {
        const createResponse = await fetch(window.benchmarkUrls.createSession, {
            method: 'POST',
            headers: {'Content-Type': 'application/json', 'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').getAttribute('content')},
            body: JSON.stringify({
                question: questionData.question,
                ground_truths: questionData.answer,
                group_id: groupId
            })
        });
        const createData = await createResponse.json();
        if (createData.error) {
            throw new Error(createData.error);
        }
        const { session_id, trial_id } = createData;

        // Optionally load into view if nothing selected, but don't auto-run via loadSession
        loadSession(session_id);

        return await runSessionLifecycle(session_id, trial_id);
    }
    
    function displayStats(results, groupName) {
        currentPipelineResults = results;
        const totalQuestions = results.length;
        if (totalQuestions === 0) return;

        document.getElementById("results-header-text").textContent = `Results for ${groupName}`;

        const correctCount = results.filter(r => r.correct === true).length;
        const incorrectCount = results.filter(r => r.correct === false).length;
        const errorCount = results.filter(r => r.correct === 'error').length;
        
        const totalTrials = results.reduce((sum, r) => sum + (r.trials || 0), 0);
        const successfulTrials = results.filter(r => r.correct === true).reduce((sum, r) => sum + r.trials, 0);
        
        const firstTryCorrectCount = results.filter(r => r.correct === true && r.trials === 1).length;
        const giveUpCount = results.filter(r => r.correct === false && r.trials >= r.max_retries).length;

        const answeredQuestions = correctCount + incorrectCount;
        const accuracy = answeredQuestions > 0 ? (correctCount / answeredQuestions) * 100 : 0;
        
        const avgTrialsAll = totalQuestions > 0 ? totalTrials / totalQuestions : 0;
        const avgTrialsSuccess = correctCount > 0 ? successfulTrials / correctCount : 0;
        
        const firstTrySuccessRate = totalQuestions > 0 ? (firstTryCorrectCount / totalQuestions) * 100 : 0;
        const giveUpRate = totalQuestions > 0 ? (giveUpCount / totalQuestions) * 100 : 0;

        document.getElementById('stats-accuracy').textContent = `${accuracy.toFixed(2)}%`;
        document.getElementById('stats-correct-count').textContent = correctCount;
        document.getElementById('stats-incorrect-count').textContent = incorrectCount;
        document.getElementById('stats-error-count').textContent = errorCount;
        document.getElementById('stats-avg-trials-all').textContent = avgTrialsAll.toFixed(2);
        document.getElementById('stats-avg-trials-success').textContent = avgTrialsSuccess.toFixed(2);
        document.getElementById('stats-first-try-success').textContent = `${firstTrySuccessRate.toFixed(2)}%`;
        document.getElementById('stats-give-up-rate').textContent = `${giveUpRate.toFixed(2)}%`;

        const tbody = document.getElementById('stats-details-tbody');
        tbody.innerHTML = '';
        results.forEach((result, index) => {
            const row = BenchmarkUtils.BenchmarkRenderer.renderMultiTurnResultRow(result, index, (sessionId) => {
                const sessionContainer = document.getElementById('session-container');
                sessionContainer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                loadSession(sessionId);
            });
            tbody.appendChild(row);
        });

        document.getElementById('statistics-container').style.display = 'block';
    }

    async function runQAPipeline() {
        const runBtn = document.getElementById('run-pipeline-btn');
        const stopBtn = document.getElementById('stop-pipeline-btn');
        
        runBtn.style.display = 'none';
        stopBtn.style.display = 'block';
        pipelineController.aborted = false;

        // Capture current LLM settings
        const currentLlmSettings = {
            llm_base_url: document.getElementById('llm_base_url').value,
            llm_api_key: document.getElementById('llm_api_key').value,
            llm_model: document.getElementById('llm_model').value,
            max_retries: document.getElementById('max_retries') ? document.getElementById('max_retries').value : null, // max_retries might not always be present
        };

        const initialSnapshot = {
            llm_settings: currentLlmSettings,
        };
        
        // Render the configuration immediately upon pipeline start
        BenchmarkUtils.renderRunConfiguration(initialSnapshot);

        // Reset stats
        const statsContainer = document.getElementById('statistics-container');
        statsContainer.style.display = 'block';
        document.getElementById('stats-details-tbody').innerHTML = '';
        document.getElementById('stats-accuracy').textContent = '0.00%';
        document.getElementById('stats-correct-count').textContent = '0';
        document.getElementById('stats-incorrect-count').textContent = '0';
        document.getElementById('stats-error-count').textContent = '0';
        document.getElementById('stats-avg-trials-all').textContent = '0.00';
        document.getElementById('stats-avg-trials-success').textContent = '0.00';
        document.getElementById('stats-first-try-success').textContent = '0.00%';
        document.getElementById('stats-give-up-rate').textContent = '0.00%';
        document.getElementById('results-header-text').textContent = 'Live Pipeline Results';

        document.getElementById('pipeline-progress').style.display = 'block';
        const progressBar = document.getElementById('pipeline-progress-bar');
        const statusDiv = document.getElementById('pipeline-status');

        const datasetId = document.getElementById('dataset-selector').value;
        let questionsToRun = questions; // Default questions

        if (datasetId) {
            try {
                const response = await fetch(`/benchmark/api/datasets/${datasetId}/questions/`);
                const data = await response.json();
                if (data.error) {
                    throw new Error(data.error);
                }
                questionsToRun = data.questions;
            } catch (error) {
                console.error("Error fetching dataset questions:", error);
                statusDiv.textContent = "Error loading questions for the selected dataset.";
                stopBtn.style.display = 'none';
                runBtn.style.display = 'block';
                return;
            }
        }
        
        let groupData;
        try {
            const groupResponse = await fetch(window.benchmarkUrls.createSessionGroup, {
                method: 'POST',
                headers: {'Content-Type': 'application/json', 'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').getAttribute('content')},
                body: JSON.stringify({ name: `Pipeline Run - ${new Date().toLocaleString()}` })
            });
            groupData = await groupResponse.json();
            if (groupData.error) throw new Error(groupData.error);
        } catch (error) {
            console.error("Error creating session group:", error);
            statusDiv.textContent = "Error starting pipeline run.";
            stopBtn.style.display = 'none';
            runBtn.style.display = 'block';
            return;
        }

        const results = [];
        let completedCount = 0;
        const totalQuestions = questionsToRun.length;

        for (const questionData of questionsToRun) {
            if (pipelineController.aborted) {
                statusDiv.textContent = "Pipeline stopped by user.";
                break;
            }

            statusDiv.textContent = `Processing question ${completedCount + 1} of ${totalQuestions}...`;

            try {
                const result = await processQuestion(questionData, groupData.group_id);
                results.push(result);
                // Add to session list - using the group info from the result
                addNewSessionToList(result.session_id, questionData, groupData.group_id, groupData.group_name);
            } catch (error) {
                console.error("Error processing question:", error);
                results.push({
                    question: questionData.question,
                    correct: 'error',
                    trials: 0,
                    session_id: null,
                    final_answer: "Error processing",
                    ground_truths: questionData.answer || []
                });
            }
            
            completedCount++;
            displayStats(results, groupData.group_name || "Current Run");

            const progress = Math.round((completedCount / totalQuestions) * 100);
            progressBar.style.width = `${progress}%`;
            progressBar.textContent = `${progress}%`;
        }

        stopBtn.style.display = 'none';
        runBtn.style.display = 'block';
        statusDiv.textContent = `Pipeline finished. Processed ${completedCount} of ${totalQuestions} questions.`;
    }

    function exportResultsAsCSV() {
        if (currentPipelineResults.length === 0) {
            alert("No pipeline results to export.");
            return;
        }

        const headers = ["#", "Question", "Final Answer", "Ground Truths", "Result", "Trials"];
        const csvRows = [headers.join(',')];

        currentPipelineResults.forEach((result, index) => {
            const row = [
                index + 1,
                `"${result.question.replace(/"/g, '""')}"`, 
                `"${(result.final_answer || 'N/A').replace(/"/g, '""')}"`, 
                `"${result.ground_truths.join('; ').replace(/"/g, '""')}"`, 
                result.correct === true ? 'Correct' : (result.correct === false ? 'Incorrect' : 'Error'),
                result.trials
            ];
            csvRows.push(row.join(','));
        });

        const csvString = csvRows.join('\n');
        const blob = new Blob([csvString], { type: 'text/csv;charset=utf-8;' });

        const link = document.createElement("a");
        if (link.download !== undefined) {
            const url = URL.createObjectURL(blob);
            const groupNameText = document.getElementById("results-header-text").textContent;
            const groupName = groupNameText.includes('Results for') ? groupNameText.replace('Results for ', '') : 'pipeline_run';
            const filename = `pipeline-results-${groupName.replace(/[ ':]/g, '_')}.csv`;
            link.setAttribute("href", url);
            link.setAttribute("download", filename);
            link.style.visibility = 'hidden';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }
    }

    document.getElementById('export-results-btn').addEventListener('click', exportResultsAsCSV);
});