document.addEventListener('DOMContentLoaded', function() {
    const questionsData = JSON.parse(document.getElementById('questions-data').textContent);
    const questionSelector = document.getElementById('question-selector');
    const runSingleQuestionBtn = document.getElementById('run-single-question-btn');

    questionSelector.addEventListener('change', function() {
        const index = this.value;
        if (index !== "") {
            runSingleQuestionBtn.disabled = false;
        } else {
            runSingleQuestionBtn.disabled = true;
        }
    });

    let pipelineController;
    let currentRunResults = [];
    let failedItems = [];

    // --- Core UI Rendering Logic ---
    function renderResults(data, resultsBody, isRetry = false) {
        if (data.is_meta) {
            return {};
        }

        const rowId = `result-${Date.now()}-${Math.random()}`;
        let resultHtml;

        if (data.error) {
            resultHtml = `<tr class="table-warning" data-id="${rowId}"><td colspan="7">Error: ${data.error}</td></tr>`;
            if (!isRetry) {
                failedItems.push({ ...data, rowId });
            }
        } else {
            // Normalize keys (DB uses is_correct_*, Pipeline uses *_result)
            const ruleCorrect = data.hasOwnProperty('is_correct_rule') ? data.is_correct_rule : data.rule_result;
            const llmCorrect = data.hasOwnProperty('is_correct_llm') ? data.is_correct_llm : data.llm_result;
            
            const textColorClass = ruleCorrect ? 'text-success-dark' : 'text-danger-dark';

            const ruleBadge = ruleCorrect ? `<span class="badge bg-success">Correct</span>` : `<span class="badge bg-danger">Incorrect</span>`;
            const llmBadge = llmCorrect === null ? `<span class="badge bg-secondary">Error</span>` : (llmCorrect ? `<span class="badge bg-success">Correct</span>` : `<span class="badge bg-danger">Incorrect</span>`);
            const agreementIcon = (llmCorrect !== null && ruleCorrect === llmCorrect)
                ? `<i class="bi bi-check-circle-fill text-success fs-5"></i>`
                : `<i class="bi bi-x-circle-fill text-danger fs-5"></i>`;

            const groundTruthsArray = data.ground_truths || [];
            const remainingCount = groundTruthsArray.length - 3;
            let groundTruthsHtml = `<ul class="list-unstyled mb-0" data-expanded="false" data-remaining="${remainingCount}">`;
            groundTruthsArray.forEach((gt, index) => {
                const isHidden = index >= 3;
                groundTruthsHtml += `<li class="text-secondary small ground-truth-item" ${isHidden ? 'style="display:none;"' : ''}><i class="bi bi-dot me-1 text-muted"></i>${gt}</li>`;
            });
            if (groundTruthsArray.length > 3) {
                groundTruthsHtml += `<li class="show-more-item"><a href="#" class="toggle-answers-link small text-decoration-none">... Show ${remainingCount} more</a></li>`;
            }
            groundTruthsHtml += '</ul>';

            resultHtml = `<tr class="${ruleCorrect ? 'table-success-light' : 'table-danger-light'}" data-id="${rowId}">
                <td class="px-4 fw-bold text-muted small"></td>
                <td class="px-4"><div class="compact-cell fw-bold ${textColorClass}">${data.question}</div></td>
                <td class="px-4"><div class="compact-cell ${textColorClass}">${data.answer}</div></td>
                <td class="px-4">${groundTruthsHtml}</td>
                <td class="px-4 text-center align-middle">${ruleBadge}</td>
                <td class="px-4 text-center align-middle">${llmBadge}</td>
                <td class="px-4 text-center align-middle">${agreementIcon}</td>
            </tr>`;
        }

        if (isRetry && data.originalRowId) {
            const originalRow = resultsBody.querySelector(`[data-id="${data.originalRowId}"]`);
            if (originalRow) {
                originalRow.outerHTML = resultHtml; // Replace the original error row
            } else {
                 resultsBody.insertAdjacentHTML('afterbegin', resultHtml); // Fallback
            }
        } else {
            resultsBody.insertAdjacentHTML('afterbegin', resultHtml);
        }
        
        const finalRuleCorrect = data.hasOwnProperty('is_correct_rule') ? data.is_correct_rule : data.rule_result;
        const finalLlmCorrect = data.hasOwnProperty('is_correct_llm') ? data.is_correct_llm : data.llm_result;
        
        return { ruleCorrect: finalRuleCorrect, llmCorrect: finalLlmCorrect };
    }

    function renderRunConfiguration(settings) {
        const configCard = document.getElementById('run-config-card');
        const configDetails = document.getElementById('run-config-details');
        
        if (!configCard || !configDetails) return;

        if (!settings || Object.keys(settings).length === 0) {
            configCard.style.display = 'none';
            return;
        }

        configDetails.innerHTML = '';
        
        const addItem = (label, value, icon) => {
            const col = document.createElement('div');
            col.className = 'col-md-4 col-sm-6';
            col.innerHTML = `
                <div class="d-flex align-items-center bg-white p-2 rounded border">
                    <i class="bi ${icon} text-secondary me-2 fs-5"></i>
                    <div class="overflow-hidden">
                        <div class="text-muted text-uppercase" style="font-size: 0.65rem; letter-spacing: 0.5px;">${label}</div>
                        <div class="fw-medium text-truncate" title="${value}">${value}</div>
                    </div>
                </div>`;
            configDetails.appendChild(col);
        };

        
        // Check for nested first (if full snapshot passed)
        let llmSettings = settings.llm_settings || settings; 

        if (llmSettings.llm_model) addItem('LLM Model', llmSettings.llm_model, 'bi-cpu');
        if (llmSettings.max_retries) addItem('Max Retries', llmSettings.max_retries, 'bi-arrow-repeat');
        if (llmSettings.llm_base_url) addItem('Base URL', llmSettings.llm_base_url, 'bi-link-45deg');

        configCard.style.display = 'block';
    }

    function updateSummary(stats) {
        const ruleAccuracy = stats.total > 0 ? (stats.ruleCorrect / stats.total) * 100 : 0;
        const llmEvalCount = stats.total - stats.llmErrors;
        const llmAccuracy = llmEvalCount > 0 ? (stats.llmCorrect / llmEvalCount) * 100 : 0;
        const agreement = llmEvalCount > 0 ? (stats.agreements / llmEvalCount) * 100 : 0;

        document.getElementById('processed-count').textContent = stats.total;
        document.getElementById('agreement-rate').textContent = `${agreement.toFixed(2)}%`;
        document.getElementById('rule-correct-count').textContent = stats.ruleCorrect;
        document.getElementById('rule-incorrect-count').textContent = stats.total - stats.ruleCorrect;
        document.getElementById('rule-accuracy-rate').textContent = `${ruleAccuracy.toFixed(2)}%`;
        document.getElementById('llm-correct-count').textContent = stats.llmCorrect;
        document.getElementById('llm-incorrect-count').textContent = llmEvalCount - stats.llmCorrect;
        document.getElementById('llm-accuracy-rate').textContent = `${llmAccuracy.toFixed(2)}%`;
    }

    // --- Configuration Management ---
    function saveSettings() {
        const data = {
            llm_base_url: document.getElementById('llm_base_url').value,
            llm_api_key: document.getElementById('llm_api_key').value,
            llm_model: document.getElementById('llm_model').value,
        };
        const csrfToken = document.querySelector('input[name="csrfmiddlewaretoken"]').value;
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

    function testConnection() {
        const data = {
            llm_base_url: document.getElementById('llm_base_url').value,
            llm_api_key: document.getElementById('llm_api_key').value,
        };
        const csrfToken = document.querySelector('input[name="csrfmiddlewaretoken"]').value;
        BenchmarkUtils.testConnection(window.benchmarkUrls.testLlmConnection, csrfToken, data, 'test-connection-result', 'test-connection-btn');
    }

    // --- Event Listeners ---
    loadSavedRuns();

    // --- Save/Load/Delete Run Functions ---
    function loadSavedRuns() {
        BenchmarkUtils.loadSavedRuns(window.benchmarkUrls.listRuns, loadRun, deleteRun);
    }

    function loadRun(runId) {
        document.getElementById('pipeline-results-container').style.display = 'block';
        document.getElementById('progress-container').style.display = 'none';
        document.getElementById('save-run-btn').disabled = true;

        fetch(`/benchmark/api/vanilla_llm_adhoc/get_run/${runId}/`)
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    alert('Error loading run: ' + data.error);
                    return;
                }
                currentRunResults = data.results;
                
                document.getElementById('results-header-text').textContent = `Results for: ${data.name}`;
                
                if (data.settings) {
                    renderRunConfiguration(data.settings);
                }

                // Re-calculate stats from the results
                let stats = {
                    total: currentRunResults.length,
                    ruleCorrect: 0,
                    llmCorrect: 0,
                    llmErrors: 0,
                    agreements: 0
                };

                currentRunResults.forEach(result => {
                    const ruleCorrect = result.hasOwnProperty('is_correct_rule') ? result.is_correct_rule : result.rule_result;
                    const llmCorrect = result.hasOwnProperty('is_correct_llm') ? result.is_correct_llm : result.llm_result;

                    if (ruleCorrect) stats.ruleCorrect++;
                    if (llmCorrect) stats.llmCorrect++;
                    if (llmCorrect === null) stats.llmErrors++;
                    if (llmCorrect !== null && ruleCorrect === llmCorrect) {
                        stats.agreements++;
                    }
                });
                updateSummary(stats);

                // Render table
                const resultsBody = document.getElementById('pipeline-results-body');
                resultsBody.innerHTML = ''; // Clear existing results
                currentRunResults.forEach(result => {
                    renderResults(result, resultsBody);
                });

                document.getElementById('save-run-btn').disabled = true;
                document.getElementById('retry-btn').style.display = 'none';
                failedItems = [];
            })
            .catch(error => {
                console.error('Error loading run:', error);
                alert(`Failed to load run data.`);
            });
    }

    function deleteRun(runId) {
        const csrfToken = document.querySelector('input[name="csrfmiddlewaretoken"]').value;
        BenchmarkUtils.deleteRun(`/benchmark/api/vanilla_llm_adhoc/delete_run/${runId}/`, csrfToken);
    }    
    document.getElementById('save-run-btn').addEventListener('click', function() {
        const defaultName = `Run ${new Date().toISOString().slice(0, 19).replace('T', ' ')}`;
        const runName = prompt("Please enter a name for this run:", defaultName);
        
        if (runName && currentRunResults.length > 0) {
            const csrfToken = document.querySelector('input[name="csrfmiddlewaretoken"]').value;
            
            fetch(window.benchmarkUrls.vanillaLlmAdhoc, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({ name: runName, results: currentRunResults })
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'ok') {
                    alert('Run saved successfully!');
                    // Refresh to see the new run in the list
                    window.location.href = window.benchmarkUrls.vanillaLlmAdhoc;
                } else {
                    alert('Error saving run: ' + (data.error || 'Unknown error'));
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('An network error occurred while saving the run.');
            });
        }
    });

    async function processVanillaAdhocQuestion(questionData) {
        const csrfToken = document.querySelector('input[name="csrfmiddlewaretoken"]').value;
        const createSessionResponse = await fetch(window.benchmarkUrls.createSession, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify({
                question: questionData.question,
                ground_truths: questionData.ground_truths || questionData.answer, // Accommodate both keys
                pipeline_type: 'vanilla_llm_adhoc'
            })
        });
        const sessionData = await createSessionResponse.json();

        if (sessionData.error) {
            throw new Error(sessionData.error);
        }

        const trialId = sessionData.trial_id;

        const runTrialResponse = await fetch(`/benchmark/api/multi_turn/run_trial/${trialId}/`, {
            method: 'GET',
            headers: {
                'X-CSRFToken': csrfToken
            }
        });
        const trialData = await runTrialResponse.json();

        if (trialData.error) {
            throw new Error(trialData.error);
        }
        
        return {
            question: questionData.question,
            rule_result: trialData.is_correct, // Rule-based result for adhoc
            llm_result: trialData.is_correct,  // LLM-based result for adhoc
            answer: trialData.answer,
            ground_truths: questionData.ground_truths || questionData.answer,
        };
    }

    // --- Single Question Run Logic ---
    document.getElementById('run-single-question-btn').addEventListener('click', async function() {
        const resultsDiv = document.getElementById('single-run-results');
        const runBtn = this;

        resultsDiv.style.display = 'none'; // Hide previous results

        const apiKey = document.getElementById('llm_api_key').value;
        const modelName = document.getElementById('llm_model').value;

        if (!apiKey.trim() || !modelName.trim()) {
            alert('Please set your LLM API Key and Model Name in the LLM Configuration section.');
            return;
        }

        const selectedIndex = questionSelector.value;
        if (selectedIndex === "") {
            alert('Please select a question to run.');
            return;
        }
        const selectedQ = questionsData[selectedIndex];
        const question = selectedQ.question;
        const ground_truths = selectedQ.ground_truths || [];

        // Disable button and show spinner
        runBtn.disabled = true;
        const originalBtnHtml = runBtn.innerHTML;
        runBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Running...';

        const csrfToken = document.querySelector('input[name="csrfmiddlewaretoken"]').value;

        try {
            // 1. Create Session
            const createSessionResponse = await fetch(window.benchmarkUrls.createSession, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({
                    question: question,
                    ground_truths: ground_truths,
                    pipeline_type: 'vanilla_llm_adhoc' // Specify adhoc pipeline type
                })
            });
            const sessionData = await createSessionResponse.json();

            if (sessionData.error) {
                throw new Error(sessionData.error);
            }

            const sessionId = sessionData.session_id;
            const trialId = sessionData.trial_id;

            // 2. Run Trial
            const runTrialResponse = await fetch(`/benchmark/api/multi_turn/run_trial/${trialId}/`, {
                method: 'GET', // GET because it triggers server-side processing
                headers: {
                    'X-CSRFToken': csrfToken // Still send CSRF for verification
                }
            });
            const trialData = await runTrialResponse.json();

            if (trialData.error) {
                throw new Error(trialData.error);
            }

            // 3. Display Results
            resultsDiv.style.display = 'block';
            
            const singleResultAnswer = document.getElementById('single-result-answer');
            if (singleResultAnswer) {
                singleResultAnswer.textContent = trialData.answer || 'N/A';
            }

            const singleResultRuleCorrect = document.getElementById('single-result-rule-correct');
            if (singleResultRuleCorrect) {
                singleResultRuleCorrect.innerHTML = trialData.is_correct ? '<span class="badge bg-success">Correct</span>' : '<span class="badge bg-danger">Incorrect</span>';
            }
            
            const singleResultLlmCorrect = document.getElementById('single-result-llm-correct');
            if (singleResultLlmCorrect) {
                singleResultLlmCorrect.innerHTML = trialData.is_correct ? '<span class="badge bg-success">Correct</span>' : '<span class="badge bg-danger">Incorrect</span>';
            }

            const singleResultDetails = document.getElementById('single-result-details');
            if (singleResultDetails) {
                singleResultDetails.textContent = trialData.error ? `Error: ${trialData.error}` : 'Run completed.';
            }

        } catch (error) {
            resultsDiv.style.display = 'block';
            document.getElementById('single-result-answer').textContent = 'Error';
            document.getElementById('single-result-rule-correct').textContent = '-';
            document.getElementById('single-result-llm-correct').textContent = '-';
            document.getElementById('single-result-details').textContent = `Error: ${error.message}`;
            console.error('Error running single question:', error);
        } finally {
            runBtn.disabled = false;
            runBtn.innerHTML = originalBtnHtml;
        }
    });

    // --- Pipeline Execution ---
    let currentRunId = null;
    let currentPipelineId = null;

    function stopPipeline(pipelineId) {
        if (!pipelineId) return;

        const csrfToken = document.querySelector('input[name="csrfmiddlewaretoken"]').value;
        const url = window.benchmarkUrls.stopPipeline;
        
        const data = JSON.stringify({ pipeline_id: pipelineId });

        fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: data,
            keepalive: true
        }).catch(e => console.error("Stop request failed", e));
    }

    document.getElementById('stop-pipeline-btn').addEventListener('click', function() {
        if (pipelineController) {
            pipelineController.abort();
        }
        if (currentPipelineId) {
            stopPipeline(currentPipelineId);
            currentPipelineId = null;
        }
    });

    document.getElementById('retry-btn').addEventListener('click', function() {
        runRetryPipeline();
    });

    document.getElementById('run-pipeline-btn').addEventListener('click', runQAPipeline);

    function runQAPipeline() {
        const runBtn = document.getElementById('run-pipeline-btn');
        const stopBtn = document.getElementById('stop-pipeline-btn');
        const retryBtn = document.getElementById('retry-btn');
        const progressContainer = document.getElementById('progress-container');
        const progressBar = document.getElementById('progress-bar');
        const resultsBody = document.getElementById('pipeline-results-body');
        const resultsContainer = document.getElementById('pipeline-results-container');
        let totalQuestions = questionsData.length;

        // Reset UI
        runBtn.style.display = 'none';
        stopBtn.style.display = 'block';
        retryBtn.style.display = 'none';
        progressContainer.style.display = 'block';
        progressBar.style.width = '0%';
        progressBar.textContent = '0%';
        resultsContainer.style.display = 'block';
        resultsBody.innerHTML = '';
        currentRunResults = [];
        failedItems = [];
        document.getElementById('save-run-btn').disabled = true;
        document.getElementById('results-header-text').textContent = "QA Pipeline Results";
        document.getElementById('running-spinner').style.display = 'inline-block';

        // Controller to stop the fetch
        pipelineController = new AbortController();
        const signal = pipelineController.signal;

        currentPipelineId = BenchmarkUtils.generateUUID();

        let stats = { total: 0, ruleCorrect: 0, llmCorrect: 0, llmErrors: 0, agreements: 0 };
        updateSummary(stats);

        const initialLlmSettings = {
            llm_base_url: document.getElementById('llm_base_url').value,
            llm_api_key: document.getElementById('llm_api_key').value,
            llm_model: document.getElementById('llm_model').value,
        };

        // Render the configuration immediately upon pipeline start
        renderRunConfiguration(initialLlmSettings);

        const formData = new FormData();
        const datasetId = document.getElementById('dataset-selector').value;
        formData.append('csrfmiddlewaretoken', document.querySelector('input[name="csrfmiddlewaretoken"]').value);
        formData.append('dataset_id', datasetId);
        formData.append('llm_base_url', initialLlmSettings.llm_base_url);
        formData.append('llm_api_key', initialLlmSettings.llm_api_key);
        formData.append('llm_model', initialLlmSettings.llm_model);
        formData.append('pipeline_id', currentPipelineId);

        
        let processedCount = 0;

        // If a dataset is selected, we need to get the question count for the progress bar
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
                if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let buffer = '';

                function push() {
                    reader.read().then(({ done, value }) => {
                        if (done) {
                            runBtn.style.display = 'block';
                            stopBtn.style.display = 'none';
                            document.getElementById('running-spinner').style.display = 'none';
                            if (failedItems.length > 0) {
                                retryBtn.style.display = 'block';
                                retryBtn.disabled = false;
                                retryBtn.innerHTML = `Retry ${failedItems.length} Failed`;
                            }
                            document.getElementById('save-run-btn').disabled = false;
                            currentPipelineId = null;
                            return;
                        }

                        buffer += decoder.decode(value, { stream: true });
                        const lines = buffer.split('\n');
                        buffer = lines.pop(); // Keep the last, possibly incomplete, line in the buffer

                        lines.forEach(line => {
                            if (pipelineController.signal.aborted) {
                                reader.cancel();
                                return;
                            }
                            if (line.trim() === '') return;

                            try {
                                let data = JSON.parse(line);
                                if (typeof data === 'string') {
                                    data = JSON.parse(data);
                                }
                                console.log("Processing data:", data); // DEBUG
                                
                                if (data.is_meta) {
                                    console.log("Skipping meta object"); // DEBUG
                                    return;
                                }
                                
                                currentRunResults.push(data);
                                
                                const resultSummary = renderResults(data, resultsBody, false);
                                
                                processedCount++;
                                const progress = totalQuestions > 0 ? (processedCount / totalQuestions) * 100 : 0;
                                progressBar.style.width = `${progress}%`;
                                progressBar.textContent = `${Math.round(progress)}%`;

                                stats.total++;
                                if (resultSummary.ruleCorrect) stats.ruleCorrect++;
                                if (resultSummary.llmCorrect) stats.llmCorrect++;
                                if (resultSummary.llmCorrect === null) stats.llmErrors++;
                                if (resultSummary.llmCorrect !== null && resultSummary.ruleCorrect === resultSummary.llmCorrect) {
                                    stats.agreements++;
                                }
                                updateSummary(stats);

                            } catch (e) {
                                console.error("Error processing streamed JSON:", e, line);
                            }
                        });
                        push();
                    }).catch(error => {
                        if (error.name === 'AbortError') {
                            console.log('Pipeline stopped by user.');
                        } else {
                            console.error('Error during stream processing:', error);
                        }
                        runBtn.style.display = 'block';
                        stopBtn.style.display = 'none';
                        document.getElementById('running-spinner').style.display = 'none';
                        currentPipelineId = null;
                    });
                }
                push();
            })
            .catch(error => {
                if (error.name === 'AbortError') {
                     console.log('Fetch aborted by user.');
                } else {
                    console.error('Error starting the pipeline:', error);
                    alert('Failed to start the pipeline.');
                }
                runBtn.style.display = 'block';
                stopBtn.style.display = 'none';
                document.getElementById('running-spinner').style.display = 'none';
                currentPipelineId = null;
            });
    }

    function runRetryPipeline() {
        const btn = document.getElementById('retry-btn');
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Retrying...';

        const resultsBody = document.getElementById('pipeline-results-body');
        const questionsToRetry = failedItems.map(item => ({ question: item.question, ground_truths: item.ground_truths, originalRowId: item.rowId }));
        
        const formData = new FormData();
        formData.append('csrfmiddlewaretoken', document.querySelector('input[name="csrfmiddlewaretoken"]').value);
        formData.append('questions', JSON.stringify(questionsToRetry.map(q => ({question: q.question, ground_truths: q.ground_truths}))));
        formData.append('llm_base_url', document.getElementById('llm_base_url').value);
        formData.append('llm_api_key', document.getElementById('llm_api_key').value);
        formData.append('llm_model', document.getElementById('llm_model').value);

        fetch(window.benchmarkUrls.vanillaLlmAdhoc, { method: 'POST', body: formData })
            .then(response => {
                if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let retryIndex = 0;

                function push() {
                    reader.read().then(({ done, value }) => {
                        if (done) {
                            btn.style.display = 'none'; // Hide after successful retry
                            failedItems = []; // Clear the list
                            return;
                        }

                        const chunk = decoder.decode(value, { stream: true });
                        const jsonObjects = chunk.split('\n').filter(s => s.trim());
                        
                        jsonObjects.forEach(jsonStr => {
                            try {
                                let data = JSON.parse(jsonStr);
                                if (typeof data === 'string') {
                                    data = JSON.parse(data);
                                }

                                if (data.is_meta) {
                                    return; // Skip meta objects
                                }
                                
                                const originalItem = questionsToRetry[retryIndex++];
                                data.originalRowId = originalItem.originalRowId;

                                // Replace the old result in currentRunResults
                                const resultIndex = currentRunResults.findIndex(r => r.rowId === data.originalRowId);
                                if (resultIndex !== -1) {
                                    currentRunResults[resultIndex] = data;
                                }

                                renderResults(data, resultsBody, true); // true for isRetry

                            } catch (e) {
                                console.error("Failed to parse JSON chunk on retry:", e, jsonStr);
                            }
                        });
                        push();
                    }).catch(error => console.error('Error during retry stream:', error));
                }
                push();
            })
            .catch(error => {
                console.error('Error starting the retry pipeline:', error);
                alert('Failed to start the retry pipeline.');
                btn.disabled = false;
                btn.innerHTML = 'Retry Failed';
            });
    }

    document.getElementById('stop-pipeline-btn').addEventListener('click', function() {
        if (pipelineController) {
            pipelineController.abort();
        }
        if (currentPipelineId) {
            stopPipeline(currentPipelineId);
            currentPipelineId = null;
        }
    });

    // Config buttons
    document.getElementById('save-settings-btn').addEventListener('click', saveSettings);
    document.getElementById('restore-defaults-btn').addEventListener('click', restoreDefaults);
    document.getElementById('test-connection-btn').addEventListener('click', testConnection);

    // Autosave for LLM Settings
    const autosaveSettings = BenchmarkUtils.debounce(saveSettings, 1000);
    ['llm_base_url', 'llm_model', 'llm_api_key'].forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener('input', autosaveSettings);
        }
    });

    // Delegated event listener for toggling ground truths
    document.getElementById('pipeline-results-body').addEventListener('click', function(e) {
        if (e.target && e.target.classList.contains('toggle-answers-link')) {
            e.preventDefault();
            const link = e.target;
            const listItem = link.parentNode;
            const list = listItem.parentNode;
            const isExpanded = list.dataset.expanded === 'true';
            const remainingCount = parseInt(list.dataset.remaining, 10);
            const items = list.querySelectorAll('.ground-truth-item');

            list.dataset.expanded = !isExpanded;
            link.textContent = isExpanded ? `... Show ${remainingCount} more` : '... Show less';

            items.forEach((item, index) => {
                if (index >= 3) { // Only toggle items beyond the initial 3
                    item.style.display = isExpanded ? 'none' : 'list-item';
                }
            });
        }
    });
});
