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







    // --- Configuration Management ---
    function restoreDefaultRagPrompt() {
        const btn = document.getElementById('restore-rag-defaults-btn');
        const originalText = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Restoring...';

        fetch(window.benchmarkUrls.getDefaultRagPrompt)
            .then(response => response.json())
            .then(data => {
                if (data.default_prompt) {
                    rag_prompt_template = data.default_prompt;
                    saveRagSettings(); // Automatically save
                } else {
                    alert('Error fetching default prompt.');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Failed to load default prompt.');
            })
            .finally(() => {
                btn.disabled = false;
                btn.innerHTML = originalText;
            });
    }

    function saveLlmSettings() {
        const data = {
            llm_base_url: document.getElementById('llm_base_url').value,
            llm_api_key: document.getElementById('llm_api_key').value,
            llm_model: document.getElementById('llm_model').value,
        };
        const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
        BenchmarkUtils.saveSettings(window.benchmarkUrls.saveLlmSettings, csrfToken, data, 'save-llm-settings-btn');
    }

    function saveRagSettings() {
        const data = {
            prompt_template: rag_prompt_template,
        };
        const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
        BenchmarkUtils.saveSettings(window.benchmarkUrls.saveRagSettings, csrfToken, data, 'save-rag-settings-btn');
    }


    function restoreDefaults() {
        BenchmarkUtils.restoreDefaults(window.benchmarkUrls.getLlmEnvVars, function(data) {
            document.getElementById('llm_base_url').value = data.llm_base_url;
            document.getElementById('llm_api_key').value = data.llm_api_key;
            document.getElementById('llm_model').value = data.llm_model;
            saveLlmSettings();
        });
    }

    function testConnection() {
        const data = {
            llm_base_url: document.getElementById('llm_base_url').value,
            llm_api_key: document.getElementById('llm_api_key').value,
        };
        const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
        BenchmarkUtils.testConnection(window.benchmarkUrls.testLlmConnection, csrfToken, data, 'test-connection-result', 'test-connection-btn');
    }

    function updateSummary(stats) {
        document.getElementById('rule-correct-count').textContent = stats.ruleCorrect;
        const ruleIncorrect = stats.total - stats.ruleCorrect;
        document.getElementById('rule-incorrect-count').textContent = ruleIncorrect;
        
        const ruleAccuracy = stats.total > 0 ? (stats.ruleCorrect / stats.total) * 100 : 0;
        document.getElementById('rule-accuracy-rate').textContent = `${ruleAccuracy.toFixed(2)}%`;

        document.getElementById('llm-correct-count').textContent = stats.llmCorrect;
        const llmIncorrect = stats.total - stats.llmCorrect - stats.llmErrors;
        document.getElementById('llm-incorrect-count').textContent = llmIncorrect;

        const llmAccuracy = stats.total > 0 ? (stats.llmCorrect / stats.total) * 100 : 0;
        document.getElementById('llm-accuracy-rate').textContent = `${llmAccuracy.toFixed(2)}%`;

        document.getElementById('processed-count').textContent = stats.total;
        
        const agreementRate = stats.total > 0 ? (stats.agreements / stats.total) * 100 : 0;
        document.getElementById('agreement-rate').textContent = `${agreementRate.toFixed(2)}%`;

        // RAG Specifics
        if (document.getElementById('total-searches-count')) {
            document.getElementById('total-searches-count').textContent = stats.total; // Assuming 1 search per question roughly
        }
        if (document.getElementById('avg-docs-count')) {
            const avgDocs = stats.total > 0 ? (stats.totalDocsUsed / stats.total) : 0;
            document.getElementById('avg-docs-count').textContent = avgDocs.toFixed(1);
        }
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
                    BenchmarkUtils.displayRunResults(runData, updateSummary, 'rag_adhoc');
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

    document.getElementById('save-run-btn').addEventListener('click', function() {
        const defaultName = `RAG Run ${new Date().toISOString().slice(0, 19).replace('T', ' ')}`;
        const runName = prompt("Please enter a name for this run:", defaultName);
        
        if (runName && currentRunResults.length > 0) {
            const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
            
            fetch(window.benchmarkUrls.ragAdhoc, {
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
                    window.location.href = window.benchmarkUrls.ragAdhoc;
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

    async function processRagAdhocQuestion(questionData, groupId = null) {
        const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
        const createSessionResponse = await fetch(window.benchmarkUrls.createSession, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify({
                question: questionData.question,
                ground_truths: questionData.ground_truths || questionData.answer, // Accommodate both keys
                group_id: groupId,
                pipeline_type: 'rag_adhoc'
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
            rule_result: trialData.is_correct, // For RAG adhoc, this is the result of the rule
            llm_result: trialData.is_correct, // For RAG adhoc, this is the result of the LLM judge
            answer: trialData.answer,
            ground_truths: questionData.ground_truths || questionData.answer,
            num_docs_used: trialData.num_docs_used,
            search_results: trialData.search_results || []
        };
    }

    // --- Single Question RAG Run Logic ---
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

        const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

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
                    pipeline_type: 'rag_adhoc' // Specify RAG pipeline type
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
            document.getElementById('single-result-answer').textContent = trialData.answer || 'N/A';
            
            const singleResultRuleCorrect = document.getElementById('single-result-rule-correct');
            if (singleResultRuleCorrect) {
                const ruleBadge = document.createElement('span');
                ruleBadge.className = trialData.is_correct ? 'badge bg-success' : 'badge bg-danger';
                ruleBadge.textContent = trialData.is_correct ? 'Correct' : 'Incorrect';
                singleResultRuleCorrect.innerHTML = ''; // Clear existing content
                singleResultRuleCorrect.appendChild(ruleBadge);
            }

            const singleResultLlmCorrect = document.getElementById('single-result-llm-correct');
            if (singleResultLlmCorrect) {
                const llmBadge = document.createElement('span');
                llmBadge.className = trialData.is_correct ? 'badge bg-success' : 'badge bg-danger';
                llmBadge.textContent = trialData.is_correct ? 'Correct' : 'Incorrect';
                singleResultLlmCorrect.innerHTML = ''; // Clear existing content
                singleResultLlmCorrect.appendChild(llmBadge);
            }
            document.getElementById('single-result-docs-used').textContent = trialData.num_docs_used !== undefined ? trialData.num_docs_used : 'N/A';
            document.getElementById('single-result-details').textContent = trialData.error ? `Error: ${trialData.error}` : 'Run completed.';

        } catch (error) {
            resultsDiv.style.display = 'block';
            document.getElementById('single-result-answer').textContent = 'Error';
            document.getElementById('single-result-rule-correct').textContent = '-';
            document.getElementById('single-result-llm-correct').textContent = '-';
            document.getElementById('single-result-docs-used').textContent = '-';
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
        document.getElementById('results-header-text').textContent = "RAG Pipeline Results";
        document.getElementById('running-spinner').style.display = 'inline-block';

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
            prompt_template: rag_prompt_template,
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
                        buffer = lines.pop();

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
                                // if (data.is_meta) return; // Removed, and assumed renderRunConfiguration is handled initially

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
                                updateSummary(stats);

                            } catch (e) {
                                console.error("Failed to parse JSON chunk:", e, line);
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

    document.getElementById('retry-btn').addEventListener('click', function() {
        // Retry logic might need adjustment for RAG specifics if different parameters are needed.
        // For now, let's assume it's similar enough.
        alert("Retry logic not fully implemented for RAG yet.");
    });

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
    document.getElementById('save-llm-settings-btn').addEventListener('click', saveLlmSettings);
    document.getElementById('save-rag-settings-btn').addEventListener('click', saveRagSettings);
    document.getElementById('restore-defaults-btn').addEventListener('click', restoreDefaults);
    document.getElementById('restore-rag-defaults-btn').addEventListener('click', restoreDefaultRagPrompt);
    document.getElementById('test-connection-btn').addEventListener('click', testConnection);

    // Autosave for LLM Settings
    const autosaveLlmSettings = BenchmarkUtils.debounce(saveLlmSettings, 1000);
    ['llm_base_url', 'llm_model', 'llm_api_key'].forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener('input', autosaveLlmSettings);
        }
    });

    // Autosave for RAG Settings
    const autosaveRagSettings = BenchmarkUtils.debounce(saveRagSettings, 1000);
    const ragPromptEl = document.getElementById('rag-prompt-template');
    if (ragPromptEl) {
        ragPromptEl.addEventListener('input', autosaveRagSettings);
    }

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
        if (currentRunResults.length === 0) {
            alert("No results to export.");
            return;
        }

        const headers = ["#", "Question", "Model Answer", "Ground Truths", "Num Docs Used", "Rule-based Correct", "LLM Judge Correct", "Agreement"];
        const csvRows = [headers.join(',')];

        currentRunResults.forEach((result, index) => {
            const ruleCorrect = result.hasOwnProperty('is_correct_rule') ? result.is_correct_rule : result.rule_result;
            const llmCorrect = result.hasOwnProperty('is_correct_llm') ? result.is_correct_llm : result.llm_result;
            const agreement = (llmCorrect !== null && ruleCorrect === llmCorrect);
            const groundTruths = result.ground_truths || result.answer || [];

            const row = [
                index + 1,
                `"${(result.question || '').replace(/"/g, '""')}"`,
                `"${(result.answer || '').replace(/"/g, '""')}"`,
                `"${(Array.isArray(groundTruths) ? groundTruths.join('; ') : groundTruths).replace(/"/g, '""')}"`,
                result.num_docs_used || 0,
                ruleCorrect ? 'Correct' : 'Incorrect',
                llmCorrect === null ? 'Error' : (llmCorrect ? 'Correct' : 'Incorrect'),
                agreement ? 'Yes' : 'No'
            ];
            csvRows.push(row.join(','));
        });

        const csvString = csvRows.join('\n');
        const blob = new Blob([csvString], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement("a");
        if (link.download !== undefined) {
            const url = URL.createObjectURL(blob);
            const headerText = document.getElementById("results-header-text").textContent;
            const filename = `rag-adhoc-${headerText.replace(/[^a-zA-Z0-9]/g, '_')}.csv`;
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
