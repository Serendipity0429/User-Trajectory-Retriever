document.addEventListener('DOMContentLoaded', function() {
    BenchmarkUtils.setupConfigurationHandlers();
    const questionsData = JSON.parse(document.getElementById('questions-data') ? document.getElementById('questions-data').textContent : '[]');
    // Removed questionSelector and runSingleQuestionBtn as they are no longer used

    let pipelineController;
    let currentRunResults = [];
    let failedItems = [];

    
    // --- Event Listeners ---
    loadSavedRuns();

    // --- Save/Load/Delete Run Functions ---
    function loadSavedRuns() {
        BenchmarkUtils.loadSavedRuns(
            window.benchmarkUrls.listRuns, 
            loadRun, 
            deleteRun,
            'saved-runs-list', 
            'no-runs-message', 
            true, // enableSelection
            toggleDeleteButton // onSelectionChange
        );
         // Reset select all checkbox and hide container initially (will be shown if runs exist)
         const selectAllContainer = document.getElementById('select-all-container');
         const selectAllCheckbox = document.getElementById('select-all-checkbox');
         if (selectAllCheckbox) selectAllCheckbox.checked = false;
    }

    // Observer to show/hide "Select All" based on list content
    const savedRunsList = document.getElementById('saved-runs-list');
    const selectAllContainer = document.getElementById('select-all-checkbox') ? document.getElementById('select-all-container') : null;
    
    if (savedRunsList && selectAllContainer) {
        const observer = new MutationObserver((mutations) => {
            if (savedRunsList.children.length > 0) {
                selectAllContainer.style.display = 'block';
            } else {
                selectAllContainer.style.display = 'none';
            }
            toggleDeleteButton(); // Re-evaluate button state
        });
        observer.observe(savedRunsList, { childList: true });
    }

    // --- Batch Delete Logic ---
    BenchmarkUtils.setupBatchSelection(
        'saved-runs-list',
        'select-all-checkbox',
        'run-checkbox',
        'delete-selected-btn',
        (selectedRunIds) => {
            if (!confirm(`Are you sure you want to delete ${selectedRunIds.length} run(s)?`)) return;

            fetch(window.benchmarkUrls.batchDeleteRuns, {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json', 
                    'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').getAttribute('content') 
                },
                body: JSON.stringify({ run_ids: selectedRunIds })
            })
            .then(res => res.json())
            .then(data => {
                if (data.status === 'ok') {
                    loadSavedRuns();
                } else {
                    alert('Error deleting runs: ' + data.message);
                }
            })
            .catch(err => {
                console.error('Error:', err);
                alert('An error occurred during deletion.');
            });
        }
    );

    function loadRun(runId) {
        document.getElementById('pipeline-results-container').style.display = 'block';
        document.getElementById('progress-container').style.display = 'none';

                    fetch(`/benchmark/api/vanilla_llm_adhoc/get_run/${runId}/`)
                        .then(response => response.json())
                        .then(data => {
                            if (data.error) {
                                alert('Error loading run: ' + data.error);
                                return;
                            }
                            currentRunResults = data.results;
                            
                            document.getElementById('results-header-text').textContent = `Results for: ${data.name}`;
                            
                BenchmarkUtils.renderRunConfiguration(data.settings, ['llm_model', 'llm_base_url']);        
                            // Replace manual stats calculation and rendering with displayRunResults
                            const runData = {
                                name: data.name,
                                results: data.results
                            };
                            BenchmarkUtils.displayRunResults(runData, BenchmarkUtils.updateAdhocStatsUI, 'vanilla_adhoc');
        
                            document.getElementById('retry-btn').style.display = 'none';
                            failedItems = [];
                        })            .catch(error => {
                console.error('Error loading run:', error);
                alert(`Failed to load run data.`);
            });
    }

    function deleteRun(runId) {
        const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
        BenchmarkUtils.deleteRun(`/benchmark/api/vanilla_llm_adhoc/delete_run/${runId}/`, csrfToken);
    }    
    // Removed save-run-btn event listener as run saving is automatic in streaming pipeline

    // Removed processVanillaAdhocQuestion and single question run logic

    // --- Pipeline Execution ---
    let currentRunId = null;
    let currentPipelineId = null;

    function handleStopPipeline() {
        if (pipelineController) {
            pipelineController.abort();
        }
        if (currentPipelineId) {
            stopPipeline(currentPipelineId);
            currentPipelineId = null;
        }
    }

    document.getElementById('stop-pipeline-btn').addEventListener('click', handleStopPipeline);
    window.addEventListener('beforeunload', handleStopPipeline);

    function stopPipeline(pipelineId) {
        if (!pipelineId) return;

        const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
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
        document.getElementById('results-header-text').textContent = "QA Pipeline Results";
        document.getElementById('running-spinner').style.display = 'inline-block';
        BenchmarkUtils.toggleConfigurationInputs(true);

        // Controller to stop the fetch
        pipelineController = new AbortController();
        const signal = pipelineController.signal;

        currentPipelineId = BenchmarkUtils.generateUUID();

        let stats = { total: 0, ruleCorrect: 0, llmCorrect: 0, llmErrors: 0, agreements: 0 };
        BenchmarkUtils.updateAdhocStatsUI(stats);

        const initialLlmSettings = {
            llm_base_url: document.getElementById('llm_base_url').value,
            llm_api_key: document.getElementById('llm_api_key').value,
            llm_model: document.getElementById('llm_model').value,
        };

        // Render the configuration immediately upon pipeline start
        BenchmarkUtils.renderRunConfiguration(initialLlmSettings);

        const formData = new FormData();
        const datasetId = document.getElementById('dataset-selector').value;
        formData.append('csrfmiddlewaretoken', document.querySelector('meta[name="csrf-token"]').getAttribute('content'));
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
            BenchmarkUtils.processStreamedResponse(
                response,
                (data) => {
                    if (data.error) {
                         console.error("Pipeline Error:", data.error);
                         // Append error to results body as a row
                         const errorRow = document.createElement('tr');
                         errorRow.innerHTML = `<td colspan="5" class="text-danger">Error: ${data.error}</td>`;
                         resultsBody.appendChild(errorRow);
                         return;
                    }

                    if (data.is_meta) return;

                    currentRunResults.push(data);
                    
                    processedCount++;
                    const resultSummary = BenchmarkUtils.BenchmarkRenderer.renderResultRow(data, resultsBody, processedCount, 'vanilla_adhoc', false);
                    
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
                    BenchmarkUtils.updateAdhocStatsUI(stats);
                },
                () => { // onComplete
                    BenchmarkUtils.toggleConfigurationInputs(false);
                    runBtn.style.display = 'block';
                    stopBtn.style.display = 'none';
                    document.getElementById('running-spinner').style.display = 'none';
                    if (failedItems.length > 0) {
                        retryBtn.style.display = 'block';
                        retryBtn.disabled = false;
                        retryBtn.innerHTML = `Retry ${failedItems.length} Failed`;
                    }
                    currentPipelineId = null;
                },
                (error) => { // onError
                    if (error.name === 'AbortError') {
                        console.log('Pipeline stopped by user.');
                    } else {
                        console.error('Error during stream processing:', error);
                    }
                    BenchmarkUtils.toggleConfigurationInputs(false);
                    runBtn.style.display = 'block';
                    stopBtn.style.display = 'none';
                    document.getElementById('running-spinner').style.display = 'none';
                    currentPipelineId = null;
                },
                signal // abortSignal
            );
        })
        .catch(error => {
            if (error.name === 'AbortError') {
                    console.log('Fetch aborted by user.');
            } else {
                console.error('Error starting the pipeline:', error);
                alert('Failed to start the pipeline.');
            }
            BenchmarkUtils.toggleConfigurationInputs(false);
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
        formData.append('csrfmiddlewaretoken', document.querySelector('meta[name="csrf-token"]').getAttribute('content'));
        formData.append('questions', JSON.stringify(questionsToRetry.map(q => ({question: q.question, ground_truths: q.ground_truths}))));
        formData.append('llm_base_url', document.getElementById('llm_base_url').value);
        formData.append('llm_api_key', document.getElementById('llm_api_key').value);
        formData.append('llm_model', document.getElementById('llm_model').value);

        let retryIndex = 0;

        fetch(window.benchmarkUrls.vanillaLlmAdhoc, { method: 'POST', body: formData })
        .then(response => {
            BenchmarkUtils.processStreamedResponse(
                response,
                (data) => {
                    if (data.is_meta) return;

                    const originalItem = questionsToRetry[retryIndex++];
                    data.originalRowId = originalItem.originalRowId;

                    // Replace the old result in currentRunResults
                    const resultIndex = currentRunResults.findIndex(r => r.rowId === data.originalRowId);
                    if (resultIndex !== -1) {
                        currentRunResults[resultIndex] = data;
                    }

                    BenchmarkUtils.BenchmarkRenderer.renderResultRow(data, resultsBody, null, 'vanilla_adhoc', true); // true for isRetry
                },
                () => {
                    btn.style.display = 'none'; // Hide after successful retry
                    failedItems = []; // Clear the list
                },
                (error) => console.error('Error during retry stream:', error)
            );
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

    // --- Configuration Management ---
    const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
    BenchmarkUtils.setupConfigurationActionHandlers(window.benchmarkUrls, csrfToken, false, false);

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

    function exportResultsAsCSV() {
        const headers = ["#", "Question", "Model Answer", "Ground Truths", "Rule-based Correct", "LLM Judge Correct", "Agreement"];
        const rowMapper = (result, index) => {
            const ruleCorrect = result.hasOwnProperty('is_correct_rule') ? result.is_correct_rule : result.rule_result;
            const llmCorrect = result.hasOwnProperty('is_correct_llm') ? result.is_correct_llm : result.llm_result;
            const agreement = (llmCorrect !== null && ruleCorrect === llmCorrect);
            const groundTruths = result.ground_truths || result.answer || [];

            return [
                index + 1,
                result.question || '',
                result.answer || '',
                Array.isArray(groundTruths) ? groundTruths.join('; ') : groundTruths,
                ruleCorrect ? 'Correct' : 'Incorrect',
                llmCorrect === null ? 'Error' : (llmCorrect ? 'Correct' : 'Incorrect'),
                agreement ? 'Yes' : 'No'
            ];
        };
        BenchmarkUtils.exportToCSV(currentRunResults, 'vanilla-adhoc', headers, rowMapper);
    }

    document.getElementById('export-results-btn').addEventListener('click', exportResultsAsCSV);
});