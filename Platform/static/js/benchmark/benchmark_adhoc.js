window.BenchmarkUtils.AdhocPage = {
        init: function(config) {
            const { pipelineType, csvPrefix = 'adhoc-results', buildFormData } = config;
            
            const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
            if (!csrfToken) console.error("CSRF Token is missing or empty!");
            BenchmarkUtils.setupConfigurationHandlers();
            BenchmarkUtils.setupConfigurationActionHandlers(csrfToken, true, true);
            
            // --- Web Search Test Logic (for RAG) ---
            if (pipelineType === 'rag_adhoc') {
                const webSearchBtn = document.getElementById('test-web-search-btn');
                if (webSearchBtn) {
                    webSearchBtn.addEventListener('click', function() {
                        const query = document.getElementById('web-search-query').value.trim();
                        if (!query) { alert('Please enter a search query.'); return; }

                        const btn = this;
                        const originalHtml = btn.innerHTML;
                        const resultsContainer = document.getElementById('web-search-results');
                        const resultsList = document.getElementById('web-search-results-list');

                        btn.disabled = true;
                        btn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Searching...';
                        resultsContainer.style.display = 'none';
                        resultsList.innerHTML = '';

                        fetch(BenchmarkUrls.webSearch, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                            body: JSON.stringify({ query: query })
                        })
                        .then(response => response.json())
                        .then(data => {
                            resultsContainer.style.display = 'block';
                            if (data.error) {
                                BenchmarkUtils.BenchmarkRenderer.renderSearchError(resultsList, `Error: ${data.error}`);
                            } else if (data.results && data.results.length > 0) {
                                BenchmarkUtils.BenchmarkRenderer.renderSearchResults(data.results, resultsList);
                            } else {
                                BenchmarkUtils.BenchmarkRenderer.renderNoSearchResults(resultsList);
                            }
                        })
                        .catch(error => {
                            console.error('Error:', error);
                            resultsContainer.style.display = 'block';
                            BenchmarkUtils.BenchmarkRenderer.renderSearchError(resultsList, `An error occurred: ${error.message}`);
                        })
                        .finally(() => {
                            btn.disabled = false;
                            btn.innerHTML = originalHtml;
                        });
                    });
                }
            }

            // --- Default Retry Logic (for Vanilla Adhoc) ---
            const defaultRetryStrategy = function(failedItems, resultsBody, currentRunResults) {
                 const btn = document.getElementById('retry-btn');
                 btn.disabled = true;
                 btn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Retrying...';
                 
                 const questionsToRetry = failedItems.map(item => ({ question: item.question, ground_truths: item.ground_truths, originalRowId: item.rowId }));
                 const formData = new FormData();
                 formData.append('csrfmiddlewaretoken', csrfToken);
                 formData.append('questions', JSON.stringify(questionsToRetry.map(q => ({question: q.question, ground_truths: q.ground_truths}))));
                 formData.append('llm_base_url', document.getElementById('llm_base_url').value);
                 formData.append('llm_api_key', document.getElementById('llm_api_key').value);
                 formData.append('llm_model', document.getElementById('llm_model').value);
                 
                 let retryIndex = 0;
                 fetch(BenchmarkUrls.vanillaLlmAdhoc.runPipeline, { method: 'POST', body: formData })
                 .then(response => {
                    BenchmarkUtils.processStreamedResponse(
                        response,
                        (data) => {
                            if (data.is_meta) return;
                            const originalItem = questionsToRetry[retryIndex++]; 
                            if (originalItem) {
                                data.originalRowId = originalItem.originalRowId;
                                const resultIndex = currentRunResults.findIndex(r => r.rowId === data.originalRowId);
                                if (resultIndex !== -1) currentRunResults[resultIndex] = data;
                                BenchmarkUtils.BenchmarkRenderer.renderResultRow(data, resultsBody, null, 'vanilla_adhoc', true);
                            }
                        },
                        () => { 
                            btn.style.display = 'none'; 
                            failedItems.length = 0; 
                        },
                        (error) => console.error(error)
                    );
                 })
                 .catch(error => {
                     console.error(error);
                     alert('Failed to start retry pipeline.');
                     btn.disabled = false;
                     btn.innerHTML = 'Retry Failed';
                 });
            };

            // questionsData removed - we now rely on backend streaming
            
            let pipelineController = null;
            let currentRunResults = [];
            let currentSettings = {};
            let failedItems = [];

            // UI Elements
            const runBtn = document.getElementById('run-pipeline-btn');
            const stopBtn = document.getElementById('stop-pipeline-btn');
            const retryBtn = document.getElementById('retry-btn');
            const resultsBody = document.getElementById('pipeline-results-body');
            const resultsHeader = document.getElementById('results-header-text');

            // --- Load Runs ---
            function loadSavedRuns() {
                const listRunsUrl = (pipelineType === 'vanilla_adhoc') ? BenchmarkUrls.vanillaLlmAdhoc.listRuns : BenchmarkUrls.ragAdhoc.listRuns;
                const deleteRunFunc = (runId) => (pipelineType === 'vanilla_adhoc') ? BenchmarkUrls.vanillaLlmAdhoc.deleteRun(runId) : BenchmarkUrls.ragAdhoc.deleteRun(runId);

                BenchmarkUtils.loadSavedRuns(
                    listRunsUrl,
                    loadRun,
                    (runId) => BenchmarkUtils.deleteRun(deleteRunFunc(runId), csrfToken),
                    'saved-runs-list',
                    'no-runs-message',
                    true
                );
                const selectAllCheckbox = document.getElementById('select-all-checkbox');
                if (selectAllCheckbox) selectAllCheckbox.checked = false;
            }

            // --- Load Single Run ---
            function loadRun(runId) {
                document.getElementById('pipeline-results-container').style.display = 'block';
                document.getElementById('progress-container').style.display = 'none';
                
                const url = (pipelineType === 'vanilla_adhoc') ? BenchmarkUrls.vanillaLlmAdhoc.getRun(runId) : BenchmarkUrls.ragAdhoc.getRun(runId);

                fetch(url)
                    .then(response => response.json())
                    .then(data => {
                        if (data.error) {
                            alert('Error loading run: ' + data.error);
                            return;
                        }
                        currentRunResults = data.results;
                        currentSettings = data.settings;
                        resultsHeader.textContent = `Results for: ${data.name}`;
                        
                        const settingsWhitelist = ['llm_model', 'llm_base_url', 'max_retries', 'allow_reasoning'];
                        if (pipelineType === 'rag_adhoc') {
                            settingsWhitelist.push('rag_settings', 'search_settings');
                        }
                        BenchmarkUtils.BenchmarkRenderer.renderRunConfiguration(data.settings, settingsWhitelist);
                        
                        const runData = { name: data.name, results: data.results };
                        BenchmarkUtils.displayRunResults(runData, BenchmarkUtils.updateAdhocStatsUI, pipelineType);
                        
                        if (retryBtn) retryBtn.style.display = 'none';
                        failedItems = [];
                    })
                    .catch(error => {
                        console.error('Error loading run:', error);
                        alert(`Failed to load run data.`);
                    });
            }

            // --- Batch Delete ---
            BenchmarkUtils.setupBatchSelection(
                'saved-runs-list', 'select-all-checkbox', 'run-checkbox', 'delete-selected-btn',
                (selectedRunIds) => {
                    if (!confirm(`Are you sure you want to delete ${selectedRunIds.length} run(s)?`)) return;
                    fetch((pipelineType === 'vanilla_adhoc' ? BenchmarkUrls.vanillaLlmAdhoc.batchDeleteRuns : BenchmarkUrls.ragAdhoc.batchDeleteRuns), {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                        body: JSON.stringify({ run_ids: selectedRunIds })
                    })
                    .then(res => res.json())
                    .then(data => {
                        if (data.status === 'ok') loadSavedRuns();
                        else alert('Error deleting runs: ' + data.message);
                    })
                    .catch(err => alert('An error occurred during deletion.'));
                }
            );

            // --- Stop Pipeline ---
            function handleStopPipeline() {
                if (pipelineController) {
                    pipelineController.abort();
                }
                if (pipelineController && pipelineController.pipelineId) {
                    BenchmarkUtils.stopPipeline((pipelineType === 'vanilla_adhoc' ? BenchmarkUrls.vanillaLlmAdhoc.stopPipeline : BenchmarkUrls.ragAdhoc.stopPipeline), csrfToken, pipelineController.pipelineId);
                }
            }
            if (stopBtn) stopBtn.addEventListener('click', handleStopPipeline);
            window.addEventListener('beforeunload', handleStopPipeline);

            // --- Run Pipeline ---
            function runQAPipeline() {
                const currentPipelineId = BenchmarkUtils.generateUUID();
                let stats = { total: 0, ruleCorrect: 0, llmCorrect: 0, llmErrors: 0, agreements: 0, totalDocsUsed: 0 };
                
                // Collect Settings Snapshot for UI
                const currentLlmSettings = {
                    llm_base_url: document.getElementById('llm_base_url').value,
                    llm_api_key: document.getElementById('llm_api_key').value,
                    llm_model: document.getElementById('llm_model').value,
                };
                const snapshot = { llm_settings: currentLlmSettings };
                if (pipelineType === 'rag_adhoc') {
                    snapshot.rag_settings = { prompt_template: document.getElementById('rag_prompt_template').value };
                    const searchProviderEl = document.getElementById('search_provider');
                    const fullContentEl = document.getElementById('serper_fetch_full_content');
                    snapshot.search_settings = {
                        search_provider: searchProviderEl ? searchProviderEl.value : null,
                        serper_fetch_full_content: fullContentEl ? fullContentEl.checked : null,
                    };
                }
                currentSettings = snapshot;
                BenchmarkUtils.BenchmarkRenderer.renderRunConfiguration(snapshot);

                // Prepare Form Data
                const formData = new FormData();
                formData.append('csrfmiddlewaretoken', csrfToken);
                formData.append('dataset_id', document.getElementById('dataset-selector').value);
                formData.append('pipeline_id', currentPipelineId);
                
                // Add common LLM fields
                formData.append('llm_base_url', currentLlmSettings.llm_base_url);
                formData.append('llm_api_key', currentLlmSettings.llm_api_key);
                formData.append('llm_model', currentLlmSettings.llm_model);

                // Add custom fields via callback
                if (buildFormData) buildFormData(formData);

                currentRunResults = [];
                failedItems = [];
                resultsHeader.textContent = "Pipeline Results";
                BenchmarkUtils.updateAdhocStatsUI(stats);

                let totalQuestions = 0; // Will be updated via stream meta
                
                // Ensure status div exists for Adhoc (keep existing logic)
                let statusDiv = document.getElementById('pipeline-status');
                if (!statusDiv) {
                    statusDiv = document.createElement('div');
                    statusDiv.id = 'pipeline-status';
                    statusDiv.className = 'mt-2 text-muted small';
                    statusDiv.style.display = 'none';
                    // Insert after progress container
                    const progressContainer = document.getElementById('progress-container');
                    if (progressContainer) {
                        progressContainer.parentNode.insertBefore(statusDiv, progressContainer.nextSibling);
                    }
                }
                statusDiv.style.display = 'block';
                statusDiv.innerText = 'Initializing...';

                const uiElements = {
                    runBtn: runBtn,
                    stopBtn: stopBtn,
                    retryBtn: retryBtn,
                    progressContainer: document.getElementById('progress-container'),
                    progressBar: document.getElementById('progress-bar'),
                    resultsContainer: document.getElementById('pipeline-results-container'),
                    resultsBody: resultsBody,
                    statusDiv: statusDiv, 
                    spinner: document.getElementById('running-spinner')
                };

                // Helper to update processing row
                let currentProcessingRow = null;
                const updateRunningRow = (questionItem) => {
                    // Remove existing
                    if (currentProcessingRow) {
                        currentProcessingRow.remove();
                        currentProcessingRow = null;
                    }
                    // Remove any other stray processing rows
                    const strays = resultsBody.querySelectorAll('.processing-row');
                    strays.forEach(row => row.remove());

                    if (questionItem) {
                        const colSpan = (pipelineType === 'rag_adhoc') ? 8 : 7;
                        currentProcessingRow = BenchmarkUtils.BenchmarkRenderer.renderProcessingRow(questionItem, resultsBody, colSpan);
                    }
                };

                pipelineController = BenchmarkUtils.PipelineRunner.start({
                    url: (pipelineType === 'vanilla_adhoc' ? BenchmarkUrls.vanillaLlmAdhoc.runPipeline : BenchmarkUrls.ragAdhoc.runPipeline),
                    formData: formData,
                    ui: uiElements,
                    totalItems: 0, // Will update based on meta
                    itemsData: null, // No longer used
                    callbacks: {
                        onMeta: (data) => {
                            if (data.type === 'total_count') {
                                totalQuestions = data.count;
                                // We can manually update totalItems in PipelineRunner context if needed, 
                                // but simpler to just handle progress bar update here if PipelineRunner doesn't support dynamic total.
                                // Actually PipelineRunner uses `totalItems` passed in `options`. 
                                // We can update the UI directly since PipelineRunner is simple.
                            } else if (data.type === 'processing_start') {
                                const questionItem = data.question;
                                updateRunningRow(questionItem);
                                
                                // Update status text
                                if (uiElements.statusDiv) {
                                    const qText = questionItem.question || 'Unknown';
                                    const processedCount = currentRunResults.length; // Approximate
                                    let text = `Processing ${processedCount + 1} / ${totalQuestions || '?'} items...`;
                                    uiElements.statusDiv.innerText = text;
                                }
                            }
                        },
                        onData: (data, processedCount) => {
                            // Remove processing row before adding result
                            if (currentProcessingRow) {
                                currentProcessingRow.remove();
                                currentProcessingRow = null;
                            }
                            // Clean up any strays just in case
                            resultsBody.querySelectorAll('.processing-row').forEach(r => r.remove());

                            currentRunResults.push(data);
                            const resultSummary = BenchmarkUtils.BenchmarkRenderer.renderResultRow(data, resultsBody, processedCount, pipelineType, false);
                            
                            if (resultSummary.rowId) {
                                data.rowId = resultSummary.rowId;
                            }

                            if (data.error && resultSummary.rowId) {
                                failedItems.push({ ...data, rowId: resultSummary.rowId });
                            }

                            stats.total++;
                            if (resultSummary.ruleCorrect) stats.ruleCorrect++;
                            if (resultSummary.llmCorrect) stats.llmCorrect++;
                            if (resultSummary.llmCorrect === null) stats.llmErrors++;
                            if (resultSummary.llmCorrect !== null && resultSummary.ruleCorrect === resultSummary.llmCorrect) {
                                stats.agreements++;
                            }
                            stats.totalDocsUsed += (data.num_docs_used || 0);
                            BenchmarkUtils.updateAdhocStatsUI(stats);
                            
                            // Update Progress Bar manually if totalQuestions is known
                            if (uiElements.progressBar && totalQuestions > 0) {
                                const progress = Math.round((stats.total / totalQuestions) * 100);
                                uiElements.progressBar.style.width = `${progress}%`;
                                uiElements.progressBar.textContent = `${progress}%`;
                            }
                        },
                        onComplete: (processedCount) => {
                             if (currentProcessingRow) currentProcessingRow.remove();
                             if (failedItems.length > 0 && retryBtn) {
                                retryBtn.style.display = 'block';
                                retryBtn.disabled = false;
                                retryBtn.innerHTML = `Retry ${failedItems.length} Failed`;
                            }
                        },
                        onError: (error) => {
                             if (currentProcessingRow) currentProcessingRow.remove();
                        }
                    }
                });

                // Show first item processing (Called AFTER start to avoid being cleared)
                // Use a small timeout to ensure it runs after the sync UI clear in start()
                setTimeout(() => {
                    if (totalQuestions > 0) {
                        updateRunningRow(0);
                    }
                }, 50);
            }
            if (runBtn) runBtn.addEventListener('click', runQAPipeline);

            // --- Retry Logic (Placeholder or Basic) ---
            if (retryBtn) {
                retryBtn.addEventListener('click', function() {
                    if (config.onRetry) {
                        config.onRetry(failedItems, resultsBody, currentRunResults);
                    } else if (pipelineType === 'vanilla_adhoc') {
                        defaultRetryStrategy(failedItems, resultsBody, currentRunResults);
                    } else {
                        alert("Retry logic is currently specialized per page. Please implement if needed.");
                    }
                });
            }

            // --- CSV Export ---
            const exportCsvBtn = document.getElementById('export-results-csv-btn');
            if (exportCsvBtn) {
                exportCsvBtn.addEventListener('click', function() {
                    const headers = ["#", "Question", "Model Answer", "Ground Truths", "Num Docs Used", "Rule-based Correct", "LLM Judge Correct", "Agreement"];
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
                            result.num_docs_used || 0,
                            ruleCorrect ? 'Correct' : 'Incorrect',
                            llmCorrect === null ? 'Error' : (llmCorrect ? 'Correct' : 'Incorrect'),
                            agreement ? 'Yes' : 'No'
                        ];
                    };
                    BenchmarkUtils.exportToCSV(currentRunResults, csvPrefix, headers, rowMapper);
                });
            }

            // --- JSON Export ---
            const exportJsonBtn = document.getElementById('export-results-json-btn');
            if (exportJsonBtn) {
                exportJsonBtn.addEventListener('click', function() {
                    const exportData = {
                        settings: currentSettings,
                        results: currentRunResults
                    };
                    BenchmarkUtils.exportToJSON(exportData, csvPrefix); // Reusing csvPrefix as generic prefix
                });
            }

            // --- Initial Load ---
            loadSavedRuns();
            
            // --- Toggles ---
            document.getElementById('pipeline-results-body').addEventListener('click', function(e) {
                if (e.target && e.target.classList.contains('toggle-answers-link')) {
                    e.preventDefault();
                    const link = e.target;
                    const listItem = link.parentNode;
                    const list = listItem.parentNode;
                    const isExpanded = list.dataset.expanded === 'true';
                    const items = list.querySelectorAll('.ground-truth-item');
                    list.dataset.expanded = !isExpanded;
                    link.textContent = isExpanded ? `... Show ${list.dataset.remaining} more` : '... Show less';
                    items.forEach((item, index) => {
                        if (index >= 3) item.style.display = isExpanded ? 'none' : 'list-item';
                    });
                }
                
                // View Search Results Modal Trigger
                if (e.target && e.target.closest('.view-all-results-btn')) {
                    e.preventDefault();
                    const btn = e.target.closest('.view-all-results-btn');
                    try {
                        const results = JSON.parse(decodeURIComponent(btn.dataset.results));
                        const container = document.getElementById('modal-generic-content-container');
                        BenchmarkUtils.BenchmarkRenderer.renderModalSearchResults(results, container);
                        const modal = new bootstrap.Modal(document.getElementById('benchmarkGenericModal'));
                        modal.show();
                    } catch (err) { console.error(err); }
                }

                // View Reasoning Modal Trigger
                if (e.target && e.target.closest('.view-reasoning-btn')) {
                    e.preventDefault();
                    const btn = e.target.closest('.view-reasoning-btn');
                    const reasoning = btn.dataset.reasoning;
                    BenchmarkUtils.BenchmarkRenderer.renderPromptModal(reasoning, 'modal-generic-content-container', 'benchmarkGenericModal', 'Reasoning Chain');
                }
            });
        }
    };
