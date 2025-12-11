document.addEventListener('DOMContentLoaded', function() {
    BenchmarkUtils.setupConfigurationHandlers();
    const questionsData = JSON.parse(document.getElementById('questions-data') ? document.getElementById('questions-data').textContent : '[]');
    // Removed questionSelector and runSingleQuestionBtn

    let pipelineController;
    let currentRunResults = [];
    let failedItems = [];

    // --- Configuration Management ---
    const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

    // LLM Settings
    document.getElementById('test-connection-btn').addEventListener('click', function() {
        const data = {
            llm_base_url: document.getElementById('llm_base_url').value,
            llm_api_key: document.getElementById('llm_api_key').value,
            llm_model: document.getElementById('llm_model').value
        };
        BenchmarkUtils.testConnection(window.benchmarkUrls.testLlmConnection, csrfToken, data, 'connection-status', 'test-connection-btn');
    });

    document.getElementById('save-llm-settings-btn').addEventListener('click', function() {
        const data = {
            llm_base_url: document.getElementById('llm_base_url').value,
            llm_api_key: document.getElementById('llm_api_key').value,
            llm_model: document.getElementById('llm_model').value,
            max_retries: document.getElementById('max_retries') ? document.getElementById('max_retries').value : 3
        };
        BenchmarkUtils.saveSettings(window.benchmarkUrls.saveLlmSettings, csrfToken, data, 'save-llm-settings-btn');
    });

    document.getElementById('restore-defaults-btn').addEventListener('click', function() {
        BenchmarkUtils.restoreDefaults(window.benchmarkUrls.getLlmEnvVars, (data) => {
            if (data.llm_base_url) document.getElementById('llm_base_url').value = data.llm_base_url;
            if (data.llm_api_key) document.getElementById('llm_api_key').value = data.llm_api_key;
            if (data.llm_model) document.getElementById('llm_model').value = data.llm_model;
        });
    });

    // RAG Settings
    if (document.getElementById('save-rag-settings-btn')) {
        document.getElementById('save-rag-settings-btn').addEventListener('click', function() {
            const data = {
                prompt_template: document.getElementById('rag_prompt_template').value
            };
            BenchmarkUtils.saveSettings(window.benchmarkUrls.saveRagSettings, csrfToken, data, 'save-rag-settings-btn');
        });
    }

    if (document.getElementById('restore-rag-defaults-btn')) {
        document.getElementById('restore-rag-defaults-btn').addEventListener('click', function() {
             fetch(window.benchmarkUrls.getDefaultRagPrompt)
                .then(res => res.json())
                .then(data => {
                    if(data.default_prompt) {
                         document.getElementById('rag_prompt_template').value = data.default_prompt;
                    }
                })
                .catch(err => console.error(err));
        });
    }

    // Search Settings
    if (document.getElementById('save-search-settings-btn')) {
        document.getElementById('save-search-settings-btn').addEventListener('click', function() {
            let searchProvider = 'serper'; // default
            const checkedProvider = document.querySelector('input[name="search_provider"]:checked');
            if (checkedProvider) searchProvider = checkedProvider.value;

            const serperApiKey = document.getElementById('serper_api_key').value;
            const serperFetchFullContent = document.getElementById('serper_fetch_full_content') ? document.getElementById('serper_fetch_full_content').checked : false;
            
            const data = {
                search_provider: searchProvider,
                serper_api_key: serperApiKey,
                serper_fetch_full_content: serperFetchFullContent
            };
            BenchmarkUtils.saveSettings(window.benchmarkUrls.saveSearchSettings, csrfToken, data, 'save-search-settings-btn');
        });
    }

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
        
        // We need to wait for the fetch in loadSavedRuns to complete to show/hide the container.
        // Since loadSavedRuns is async but doesn't return a promise we can wait on, 
        // we can check existence of items after a short delay or modify loadSavedRuns to return promise.
        // For now, let's use a MutationObserver on the list.
    }

    // Observer to show/hide "Select All" based on list content
    const savedRunsList = document.getElementById('saved-runs-list');
    const selectAllContainer = document.getElementById('select-all-container');
    const observer = new MutationObserver((mutations) => {
        if (savedRunsList.children.length > 0) {
            selectAllContainer.style.display = 'block';
        } else {
            selectAllContainer.style.display = 'none';
        }
        toggleDeleteButton(); // Re-evaluate button state
    });
    observer.observe(savedRunsList, { childList: true });

    // --- Batch Delete Logic ---
    const deleteSelectedBtn = document.getElementById('delete-selected-btn');
    const selectAllCheckbox = document.getElementById('select-all-checkbox');

    function getRunCheckboxes() {
        return document.querySelectorAll('.run-checkbox');
    }

    function toggleDeleteButton() {
        const checkboxes = getRunCheckboxes();
        const anyChecked = Array.from(checkboxes).some(cb => cb.checked);
        deleteSelectedBtn.style.display = anyChecked ? 'inline-block' : 'none';
        
        // Update Select All state
        if (checkboxes.length > 0) {
            const allChecked = Array.from(checkboxes).every(cb => cb.checked);
            selectAllCheckbox.checked = allChecked;
        } else {
            selectAllCheckbox.checked = false;
        }
    }

    if (selectAllCheckbox) {
        selectAllCheckbox.addEventListener('change', function(e) {
            const isChecked = e.target.checked;
            getRunCheckboxes().forEach(cb => cb.checked = isChecked);
            toggleDeleteButton();
        });
    }

    if (deleteSelectedBtn) {
        deleteSelectedBtn.addEventListener('click', function() {
            const selectedRunIds = Array.from(getRunCheckboxes())
                .filter(cb => cb.checked)
                .map(cb => cb.dataset.runId);

            if (selectedRunIds.length === 0) return;

            if (!confirm(`Are you sure you want to delete ${selectedRunIds.length} run(s)?`)) {
                return;
            }

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
                    // clear current results if deleted
                    // Optional: check if current displayed run is among deleted
                } else {
                    alert('Error deleting runs: ' + data.message);
                }
            })
            .catch(err => {
                console.error('Error:', err);
                alert('An error occurred during deletion.');
            });
        });
    }
    
        function loadRun(runId) {
            document.getElementById('pipeline-results-container').style.display = 'block';
            document.getElementById('progress-container').style.display = 'none';

            fetch(`/benchmark/api/rag_adhoc/get_run/${runId}/`)
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        alert('Error loading run: ' + data.error);
                        return;
                    }
                    currentRunResults = data.results;
                    
                    document.getElementById('results-header-text').textContent = `Results for: ${data.name}`;
        BenchmarkUtils.renderRunConfiguration(data.settings, ['llm_model', 'llm_base_url', 'rag_settings', 'search_settings']);
                    // Replace manual stats calculation and rendering with displayRunResults
                    const runData = {
                        name: data.name,
                        results: data.results
                    };
                    BenchmarkUtils.displayRunResults(runData, BenchmarkUtils.updateAdhocStatsUI, 'rag_adhoc');
                })
                .catch(error => {
                    console.error('Error loading run:', error);
                    alert(`Failed to load run data.`);
                });
        }
    
        function deleteRun(runId) {
        const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
        BenchmarkUtils.deleteRun(`/benchmark/api/rag_adhoc/delete_run/${runId}/`, csrfToken);
    }

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

    document.getElementById('run-pipeline-btn').addEventListener('click', runQAPipeline);

    function runQAPipeline() {
        const runBtn = document.getElementById('run-pipeline-btn');
        const stopBtn = document.getElementById('stop-pipeline-btn');
        const retryBtn = document.getElementById('retry-btn');
        const progressContainer = document.getElementById('progress-container');
        const progressBar = document.getElementById('progress-bar');
        const resultsBody = document.getElementById('pipeline-results-body');
        const resultsContainer = document.getElementById('pipeline-results-container');
        const totalQuestions = questionsData.length;

        // Generate a new pipeline ID
        currentPipelineId = BenchmarkUtils.generateUUID();

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
        document.getElementById('results-header-text').textContent = "RAG Pipeline Results";
        document.getElementById('running-spinner').style.display = 'inline-block';
        BenchmarkUtils.toggleConfigurationInputs(true);

        // Controller to stop the fetch
        pipelineController = new AbortController();
        const signal = pipelineController.signal;

        // Get current LLM settings
        const currentLlmSettings = {
            llm_base_url: document.getElementById('llm_base_url').value,
            llm_api_key: document.getElementById('llm_api_key').value,
            llm_model: document.getElementById('llm_model').value,
        };

        // Get current RAG settings
        const currentRagSettings = {
            prompt_template: document.getElementById('rag_prompt_template').value,
        };
        
        // Get current Search settings
        // Assuming existence of these elements based on renderRunConfiguration logic
        const searchProviderEl = document.getElementById('search_provider');
        const serperFetchFullContentEl = document.getElementById('serper_fetch_full_content');

        const currentSearchSettings = {
            search_provider: searchProviderEl ? searchProviderEl.value : null,
            serper_fetch_full_content: serperFetchFullContentEl ? serperFetchFullContentEl.checked : null,
        };

        const initialSnapshot = {
            llm_settings: currentLlmSettings,
            rag_settings: currentRagSettings,
            search_settings: currentSearchSettings
        };
        
        // Render the configuration immediately upon pipeline start
        BenchmarkUtils.renderRunConfiguration(initialSnapshot);


        const datasetId = document.getElementById('dataset-selector').value;
        const formData = new FormData();
        formData.append('csrfmiddlewaretoken', document.querySelector('meta[name="csrf-token"]').getAttribute('content'));
        formData.append('dataset_id', datasetId);
        formData.append('llm_base_url', currentLlmSettings.llm_base_url);
        formData.append('llm_api_key', currentLlmSettings.llm_api_key);
        formData.append('llm_model', currentLlmSettings.llm_model);
        formData.append('rag_prompt_template', currentRagSettings.prompt_template);
        if (currentSearchSettings.search_provider) {
            formData.append('search_provider', currentSearchSettings.search_provider);
        }
        if (currentSearchSettings.serper_fetch_full_content !== null) { // Check for null, as `false` is a valid value
            formData.append('serper_fetch_full_content', currentSearchSettings.serper_fetch_full_content);
        }
        formData.append('pipeline_id', currentPipelineId);
        
        let processedCount = 0;
        let stats = {
            total: 0,
            ruleCorrect: 0,
            llmCorrect: 0,
            llmErrors: 0,
            agreements: 0,
            totalDocsUsed: 0
        };

        fetch(window.benchmarkUrls.runPipeline, { method: 'POST', body: formData, signal: signal })
        .then(response => {
            BenchmarkUtils.processStreamedResponse(
                response,
                (data) => {
                    if (data.is_meta) return;

                    currentRunResults.push(data);
                    
                    processedCount++;
                    const resultSummary = BenchmarkUtils.BenchmarkRenderer.renderResultRow(data, resultsBody, processedCount, 'rag_adhoc', false);
                    
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
                    stats.totalDocsUsed += (data.num_docs_used || 0);
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

    document.getElementById('retry-btn').addEventListener('click', function() {
        alert("Retry logic not fully implemented for RAG yet.");
    });

    // Autosave for RAG Settings
    // --- Web Search Test Logic ---
    document.getElementById('test-web-search-btn').addEventListener('click', function() {
        const query = document.getElementById('web-search-query').value.trim();
        if (!query) {
            alert('Please enter a search query.');
            return;
        }

        const btn = this;
        const originalHtml = btn.innerHTML;
        const resultsContainer = document.getElementById('web-search-results');
        const resultsList = document.getElementById('web-search-results-list');

        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Searching...';
        resultsContainer.style.display = 'none';
        resultsList.innerHTML = '';

        const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

        fetch(window.benchmarkUrls.webSearch, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
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
        
        // Delegated event listener for search result items
        if (e.target && e.target.closest('.view-all-results-btn')) {
            e.preventDefault();
            const btn = e.target.closest('.view-all-results-btn');
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

    function exportResultsAsCSV() {
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
        BenchmarkUtils.exportToCSV(currentRunResults, 'rag-adhoc', headers, rowMapper);
    }

    document.getElementById('export-results-btn').addEventListener('click', exportResultsAsCSV);
});
