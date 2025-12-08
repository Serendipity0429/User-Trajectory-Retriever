const BenchmarkUtils = {
    /**
     * Test the LLM connection.
     * @param {string} url - The URL to the test connection view.
     * @param {string} csrfToken - The CSRF token.
     * @param {object} data - The data to send (llm_base_url, llm_api_key).
     * @param {string} resultDivId - The ID of the div to display results.
     * @param {string} btnId - The ID of the test button.
     */
    testConnection: function(url, csrfToken, data, resultDivId, btnId) {
        const resultDiv = document.getElementById(resultDivId);
        const btn = document.getElementById(btnId);
        const originalText = btn.innerHTML;
        
        resultDiv.innerHTML = '';
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Testing...';

        fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify(data)
        })
        .then(response => response.json().then(data => ({status: response.status, body: data})))
        .then(({status, body}) => {
            if (status === 200) {
                resultDiv.innerHTML = `<div class="alert alert-success" role="alert">${body.message}</div>`;
            } else {
                resultDiv.innerHTML = `<div class="alert alert-danger" role="alert">${body.message}</div>`;
            }
        })
        .catch(error => {
            resultDiv.innerHTML = `<div class="alert alert-danger" role="alert">A network error occurred.</div>`;
            console.error('Error:', error);
        })
        .finally(() => {
            btn.disabled = false;
            btn.innerHTML = originalText;
        });
    },

    /**
     * Save settings to the server.
     * @param {string} url - The URL to the save settings view.
     * @param {string} csrfToken - The CSRF token.
     * @param {object} data - The settings data to save.
     * @param {string} btnId - The ID of the save button (to show feedback).
     */
    saveSettings: function(url, csrfToken, data, btnId) {
        fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify(data)
        })
        .then(response => response.json())
        .then(resData => {
            if (resData.status === 'ok') {
                const btn = document.getElementById(btnId);
                const originalText = btn.innerHTML;
                const originalClass = btn.className;
                
                btn.innerHTML = '<i class="bi bi-check-lg me-1"></i> Saved!';
                btn.classList.remove('btn-outline-primary', 'btn-primary', 'btn-outline-secondary');
                btn.classList.add('btn-success');
                
                setTimeout(() => {
                    btn.innerHTML = originalText;
                    btn.className = originalClass; 
                }, 1500);
            } else {
                alert('Error saving settings: ' + (resData.message || 'Unknown error'));
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('A network error occurred while saving settings.');
        });
    },

    /**
     * Restore default settings from .env via server.
     * @param {string} url - The URL to fetch default settings.
     * @param {function} callback - Callback function receiving the data.
     */
    restoreDefaults: function(url, callback) {
        fetch(url)
            .then(response => response.json())
            .then(data => {
                if(data.error) {
                    alert('Error loading .env variables: ' + data.error);
                } else {
                    callback(data);
                }
            })
            .catch(error => {
                console.error('Error restoring defaults:', error);
                alert('Failed to restore defaults.');
            });
    },

    /**
     * Generate a UUID.
     * @returns {string} UUID.
     */
    generateUUID: function() {
        if (typeof crypto !== 'undefined' && crypto.randomUUID) {
            return crypto.randomUUID();
        }
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
            var r = Math.random() * 16 | 0, v = c == 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });
    },

    /**
     * Stop a running pipeline.
     * @param {string} url - The URL to the stop pipeline view.
     * @param {string} csrfToken - The CSRF token.
     * @param {string} pipelineId - The ID of the pipeline to stop.
     */
    stopPipeline: function(url, csrfToken, pipelineId) {
        if (!pipelineId) return;
        
        const data = JSON.stringify({ pipeline_id: pipelineId });

        // Prefer fetch with keepalive
        fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: data,
            keepalive: true
        }).catch(e => console.error("Stop request failed", e));
    },

    /**
     * Load saved runs and populate the list.
     * @param {string} listUrl - URL to list runs.
     * @param {function} loadRunCallback - Function to call when a run is clicked.
     * @param {function} deleteRunCallback - Function to call when delete is clicked.
     * @param {string} listId - ID of the list element.
     * @param {string} noRunsId - ID of the no runs message element.
     */
    loadSavedRuns: function(listUrl, loadRunCallback, deleteRunCallback, listId = 'saved-runs-list', noRunsId = 'no-runs-message') {
        const savedRunsList = document.getElementById(listId);
        const noRunsMessage = document.getElementById(noRunsId);
        savedRunsList.innerHTML = ''; 

        fetch(listUrl)
            .then(response => response.json())
            .then(data => {
                if (data.runs && data.runs.length > 0) {
                    noRunsMessage.style.display = 'none';
                    savedRunsList.style.display = 'block';
                    data.runs.forEach(run => {
                        const runItem = document.createElement('div');
                        runItem.className = 'list-group-item list-group-item-action d-flex justify-content-between align-items-center';
                        
                        const runNameContainer = document.createElement('div');
                        runNameContainer.style.cursor = 'pointer';
                        runNameContainer.className = 'flex-grow-1';
                        runNameContainer.onclick = () => loadRunCallback(run.id);

                        const runName = document.createElement('span');
                        runName.textContent = run.name;
                        runNameContainer.appendChild(runName);

                        const deleteBtn = document.createElement('button');
                        deleteBtn.className = 'btn btn-sm btn-outline-danger ms-2';
                        deleteBtn.innerHTML = '<i class="bi bi-trash"></i>';
                        deleteBtn.title = 'Delete run';
                        deleteBtn.onclick = (e) => {
                            e.stopPropagation();
                            deleteRunCallback(run.id);
                        };

                        runItem.appendChild(runNameContainer);
                        runItem.appendChild(deleteBtn);
                        savedRunsList.appendChild(runItem);
                    });
                } else {
                    noRunsMessage.style.display = 'block';
                    savedRunsList.style.display = 'none';
                }
            });
    },

    /**
     * Delete a run.
     * @param {string} url - URL to delete the run.
     * @param {string} csrfToken - CSRF token.
     */
    deleteRun: function(url, csrfToken) {
        if (!confirm(`Are you sure you want to delete this run? This action cannot be undone.`)) {
            return;
        }

        fetch(url, {
            method: 'DELETE',
            headers: { 'X-CSRFToken': csrfToken }
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'ok') {
                window.location.reload();
            } else {
                alert('Error deleting run: ' + (data.message || 'Unknown error'));
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('An network error occurred while deleting the run.');
        });
    },

    /**
     * Debounce a function.
     * @param {function} func - The function to debounce.
     * @param {number} wait - The delay in milliseconds.
     * @returns {function} The debounced function.
     */
    debounce: function(func, wait) {
        let timeout;
        return function(...args) {
            const context = this;
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(context, args), wait);
        };
    },
    displayRunResults: function(runData, renderFunc, updateSummaryFunc) {
        const resultsContainer = document.getElementById('pipeline-results-container');
        const progressContainer = document.getElementById('progress-container');
        const saveRunBtn = document.getElementById('save-run-btn');
        const resultsHeader = document.getElementById('results-header-text');
        const resultsBody = document.getElementById('pipeline-results-body');

        resultsContainer.style.display = 'block';
        if (progressContainer) progressContainer.style.display = 'none';
        if (saveRunBtn) saveRunBtn.disabled = true;

        resultsHeader.textContent = `Results for: ${runData.name}`;
        resultsBody.innerHTML = '';

        let stats = {
            total: runData.results.length,
            ruleCorrect: 0,
            llmCorrect: 0,
            llmErrors: 0,
            agreements: 0,
            totalDocsUsed: 0
        };

        runData.results.forEach((result, index) => {
            const summary = renderFunc(result, resultsBody, index + 1);
            if (summary.ruleCorrect) stats.ruleCorrect++;
            if (summary.llmCorrect) stats.llmCorrect++;
            if (summary.llmCorrect === null) stats.llmErrors++;
            if (summary.llmCorrect !== null && summary.ruleCorrect === summary.llmCorrect) {
                stats.agreements++;
            }
            stats.totalDocsUsed += (result.num_docs_used || 0);
        });

        if (updateSummaryFunc) {
            updateSummaryFunc(stats);
        }

        if (saveRunBtn) saveRunBtn.disabled = true;
        const retryBtn = document.getElementById('retry-btn');
        if (retryBtn) retryBtn.style.display = 'none';
    }
};
