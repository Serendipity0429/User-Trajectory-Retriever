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
    BenchmarkRenderer: {
        createBadge: function(text, isCorrect, showNAForNull = false) {
            const span = document.createElement('span');
            span.className = 'badge';
            if (isCorrect === null && showNAForNull) {
                span.classList.add('bg-secondary');
                span.textContent = 'N/A';
            } else if (isCorrect) {
                span.classList.add('bg-success');
                span.textContent = text || 'Correct';
            } else {
                span.classList.add('bg-danger');
                span.textContent = text || 'Incorrect';
            }
            return span;
        },

        createIcon: function(className) {
            const i = document.createElement('i');
            i.className = className;
            return i;
        },

        createTextElement: function(tagName, className, textContent, title = '') {
            const element = document.createElement(tagName);
            element.className = className;
            element.textContent = textContent;
            if (title) {
                element.title = title;
            }
            return element;
        },

        createLink: function(href, className, textContent, target = '_self') {
            const link = document.createElement('a');
            link.href = href;
            link.className = className;
            link.textContent = textContent;
            link.target = target;
            return link;
        },
        
        // This will be the new centralized render function
        renderResultRow: function(data, resultsBody, index, type = 'vanilla_adhoc', isRetry = false) {
            const rowId = `result-${Date.now()}-${Math.random()}`;
            const tr = document.createElement('tr');
            tr.dataset.id = rowId;

            if (data.error) {
                tr.className = "table-warning";
                const td = document.createElement('td');
                td.colSpan = (type === 'rag_adhoc') ? 8 : 7;
                td.textContent = `Error: ${data.error}`;
                tr.appendChild(td);
                if (!isRetry) {
                    // This 'failedItems' needs to be managed externally or passed in
                    // For now, it will remain in adhoc files.
                    // failedItems.push({ ...data, rowId }); 
                }
            } else {
                const ruleCorrect = data.hasOwnProperty('is_correct_rule') ? data.is_correct_rule : data.rule_result;
                const llmCorrect = data.hasOwnProperty('is_correct_llm') ? data.is_correct_llm : data.llm_result;
                
                // Use LLM result for styling if available, otherwise fallback to rule or neutral
                let rowClass = 'table-light';
                let textClass = 'text-dark';

                if (llmCorrect === true) {
                    rowClass = 'table-success-light';
                    textClass = 'text-success-dark';
                } else if (llmCorrect === false) {
                    rowClass = 'table-danger-light';
                    textClass = 'text-danger-dark';
                } else if (ruleCorrect === true) {
                     // Fallback to rule if LLM is null (optional, or just leave neutral)
                     // But user emphasized LLM judge. If LLM is null, maybe just keep neutral/warning.
                     // Let's stick to strict LLM judge as requested, but maybe show warning if null.
                     rowClass = 'table-warning-light'; 
                }

                tr.className = rowClass;
                const textColorClass = textClass;

                // Cell 1: Index or empty
                const td1 = document.createElement('td');
                td1.className = 'px-4 fw-bold text-muted small';
                if (index) { // Only add index if provided (e.g., for pipeline runs)
                    td1.textContent = index;
                }
                tr.appendChild(td1);

                // Cell 2: Question
                const td2 = document.createElement('td');
                td2.className = 'px-4';
                const divQuestion = this.createTextElement('div', `compact-cell fw-bold ${textColorClass}`, data.question);
                td2.appendChild(divQuestion);
                tr.appendChild(td2);

                // Cell 3: Answer
                const td3 = document.createElement('td');
                td3.className = 'px-4';
                const divAnswer = this.createTextElement('div', `compact-cell ${textColorClass}`, data.answer);
                td3.appendChild(divAnswer);
                tr.appendChild(td3);

                // Cell 4: Ground Truths
                const td4 = document.createElement('td');
                const groundTruthsArray = data.ground_truths || [];
                const remainingCount = groundTruthsArray.length - 3;
                const ul = document.createElement('ul');
                ul.className = 'list-unstyled mb-0';
                ul.dataset.expanded = 'false';
                ul.dataset.remaining = remainingCount.toString();

                groundTruthsArray.forEach((gt, gtIndex) => {
                    const li = document.createElement('li');
                    li.className = 'text-secondary small ground-truth-item';
                    if (gtIndex >= 3) {
                        li.style.display = 'none';
                    }
                    li.appendChild(this.createIcon('bi bi-dot me-1 text-muted'));
                    li.appendChild(document.createTextNode(gt));
                    ul.appendChild(li);
                });

                if (groundTruthsArray.length > 3) {
                    const liShowMore = document.createElement('li');
                    liShowMore.className = 'show-more-item';
                    const a = this.createLink('#', 'toggle-answers-link small text-decoration-none', `... Show ${remainingCount} more`);
                    liShowMore.appendChild(a);
                    ul.appendChild(liShowMore);
                }
                td4.appendChild(ul);
                tr.appendChild(td4);

                // Cell for Search Results (RAG Adhoc specific)
                if (type === 'rag_adhoc') {
                    const tdSearch = document.createElement('td');
                    tdSearch.className = 'px-4';
                    if (data.search_results && data.search_results.length > 0) {
                        const resultsJson = encodeURIComponent(JSON.stringify(data.search_results));
                        const count = data.search_results.length;
                        const button = document.createElement('button');
                        button.className = 'btn btn-sm btn-outline-primary view-all-results-btn';
                        button.type = 'button';
                        button.dataset.results = resultsJson;
                        button.appendChild(this.createIcon('bi bi-list-ul me-1'));
                        button.appendChild(document.createTextNode(`View ${count} Results`));
                        tdSearch.appendChild(button);
                    } else {
                        tdSearch.appendChild(this.createTextElement('span', 'text-muted fst-italic small', 'No results'));
                    }
                    tr.appendChild(tdSearch);
                }

                // Cell 5/6: Rule Badge
                const tdRuleBadge = document.createElement('td');
                tdRuleBadge.className = 'px-4 text-center align-middle';
                tdRuleBadge.appendChild(this.createBadge(null, ruleCorrect));
                tr.appendChild(tdRuleBadge);

                // Cell 6/7: LLM Badge
                const tdLlmBadge = document.createElement('td');
                tdLlmBadge.className = 'px-4 text-center align-middle';
                tdLlmBadge.appendChild(this.createBadge(null, llmCorrect, true)); // show N/A for null
                tr.appendChild(tdLlmBadge);

                // Cell 7/8: Agreement Icon
                const tdAgreement = document.createElement('td');
                tdAgreement.className = 'px-4 text-center align-middle';
                const agreementIconI = this.createIcon((llmCorrect !== null && ruleCorrect === llmCorrect)
                    ? 'bi bi-check-circle-fill text-success fs-5'
                    : 'bi bi-x-circle-fill text-danger fs-5');
                tdAgreement.appendChild(agreementIconI);
                tr.appendChild(tdAgreement);
            }

            if (isRetry && data.originalRowId) {
                const originalRow = resultsBody.querySelector(`[data-id="${data.originalRowId}"]`);
                if (originalRow) {
                    resultsBody.replaceChild(tr, originalRow);
                } else {
                     resultsBody.insertAdjacentElement('afterbegin', tr);
                }
            } else {
                resultsBody.insertAdjacentElement('afterbegin', tr);
            }
            
            const finalRuleCorrect = data.hasOwnProperty('is_correct_rule') ? data.is_correct_rule : data.rule_result;
            const finalLlmCorrect = data.hasOwnProperty('is_correct_llm') ? data.is_correct_llm : data.llm_result;
            
            return { ruleCorrect: finalRuleCorrect, llmCorrect: finalLlmCorrect };
        },

        renderSearchResults: function(results, resultsListElement) {
            resultsListElement.innerHTML = ''; // Clear previous results
            if (results && results.length > 0) {
                results.forEach((res, index) => {
                    const item = document.createElement('a');
                    item.href = res.link || '#';
                    item.target = "_blank";
                    item.className = "list-group-item list-group-item-action";

                    const divFlex = document.createElement('div');
                    divFlex.className = "d-flex w-100 justify-content-between";

                    const h6Title = document.createElement('h6');
                    h6Title.className = "mb-1 text-primary";
                    h6Title.textContent = `${index + 1}. ${res.title || 'No Title'}`;
                    divFlex.appendChild(h6Title);
                    item.appendChild(divFlex);

                    const pSnippet = document.createElement('p');
                    pSnippet.className = "mb-1 small text-muted";
                    pSnippet.textContent = res.snippet || 'No snippet available.';
                    item.appendChild(pSnippet);

                    const smallLink = document.createElement('small');
                    smallLink.className = "text-truncate d-block text-secondary";
                    smallLink.textContent = res.link || '';
                    item.appendChild(smallLink);
                    
                    resultsListElement.appendChild(item);
                });
            } else {
                this.renderNoSearchResults(resultsListElement);
            }
        },

        renderNoSearchResults: function(resultsListElement) {
            resultsListElement.innerHTML = ''; // Clear previous results
            const alertDiv = document.createElement('div');
            alertDiv.className = 'alert alert-info';
            alertDiv.textContent = 'No results found.';
            resultsListElement.appendChild(alertDiv);
        },

        renderSearchError: function(resultsListElement, errorMessage) {
            resultsListElement.innerHTML = ''; // Clear previous results
            const alertDiv = document.createElement('div');
            alertDiv.className = 'alert alert-danger';
            alertDiv.textContent = errorMessage;
            resultsListElement.appendChild(alertDiv);
        },

        renderModalSearchResults: function(results, container) {
            container.innerHTML = ''; // Clear existing content

            if (results && results.length > 0) {
                results.forEach((res, idx) => {
                    const linkUrl = res.link || res.url || '#';
                    const linkTitle = res.title || 'No Title';
                    const snippet = res.snippet || 'No snippet available.';
                    
                    let domain = '';
                    try {
                        if (linkUrl && linkUrl !== '#') {
                            const urlObj = new URL(linkUrl);
                            domain = urlObj.hostname.replace('www.', '');
                        }
                    } catch(err) {}

                    const item = document.createElement('div');
                    item.className = 'list-group-item p-3';

                    const div1 = document.createElement('div');
                    div1.className = 'd-flex w-100 justify-content-between mb-1';
                    item.appendChild(div1);

                    const h6 = document.createElement('h6');
                    h6.className = 'mb-0 text-primary fw-bold';
                    div1.appendChild(h6);

                    const spanIdx = document.createElement('span');
                    spanIdx.className = 'text-muted fw-normal me-2';
                    spanIdx.textContent = `#${idx + 1}`;
                    h6.appendChild(spanIdx);

                    const aTitle = document.createElement('a');
                    aTitle.href = linkUrl;
                    aTitle.target = '_blank';
                    aTitle.className = 'text-decoration-none';
                    aTitle.textContent = linkTitle;
                    h6.appendChild(aTitle);

                    const smallDomain = document.createElement('small');
                    smallDomain.className = 'text-muted text-end ms-2';
                    smallDomain.textContent = domain;
                    div1.appendChild(smallDomain);

                    const pSnippet = document.createElement('p');
                    pSnippet.className = 'mb-1 text-dark';
                    pSnippet.style.fontSize = '0.95rem';
                    pSnippet.style.lineHeight = '1.4';
                    pSnippet.textContent = snippet;
                    item.appendChild(pSnippet);

                    const smallLink = document.createElement('small');
                    smallLink.className = 'text-muted font-monospace';
                    smallLink.style.fontSize = '0.75rem';
                    item.appendChild(smallLink);

                    const iLink = document.createElement('i');
                    iLink.className = 'bi bi-link-45deg';
                    smallLink.appendChild(iLink);
                    smallLink.appendChild(document.createTextNode(` ${linkUrl}`));
                    
                    container.appendChild(item);
                });
            } else {
                const noResultsDiv = document.createElement('div');
                noResultsDiv.className = 'p-3 text-center text-muted';
                noResultsDiv.textContent = 'No results data found.';
                container.appendChild(noResultsDiv);
            }
        },

        renderMultiTurnResultRow: function(result, index, loadSessionCallback) {
            const row = document.createElement('tr');
            row.style.cursor = "pointer";
            if (loadSessionCallback) {
                row.onclick = () => loadSessionCallback(result.session_id);
            }

            let resultBadge;
            if (result.correct === true) {
                resultBadge = document.createElement('span');
                resultBadge.className = 'badge bg-success';
                resultBadge.textContent = 'Correct';
            } else if (result.correct === false) {
                resultBadge = document.createElement('span');
                resultBadge.className = 'badge bg-danger';
                resultBadge.textContent = 'Incorrect';
            } else {
                resultBadge = document.createElement('span');
                resultBadge.className = 'badge bg-warning text-dark';
                resultBadge.textContent = 'Error';
            }
            
            const GROUNDTRUTH_DISPLAY_LIMIT = 3; 
            const ulGroundTruths = document.createElement('ul');
            ulGroundTruths.className = 'list-unstyled mb-0';

            const initialGroundTruths = result.ground_truths.slice(0, GROUNDTRUTH_DISPLAY_LIMIT);
            initialGroundTruths.forEach(gt => {
                const li = document.createElement('li');
                li.className = 'text-secondary small';
                const icon = document.createElement('i');
                icon.className = 'bi bi-dot me-1 text-muted';
                li.appendChild(icon);
                li.appendChild(document.createTextNode(gt));
                ulGroundTruths.appendChild(li);
            });

            const fullGroundTruthsDiv = document.createElement('div');
            fullGroundTruthsDiv.style.display = 'none';
            result.ground_truths.slice(GROUNDTRUTH_DISPLAY_LIMIT).forEach(gt => {
                const li = document.createElement('li');
                li.className = 'text-secondary small';
                const icon = document.createElement('i');
                icon.className = 'bi bi-dot me-1 text-muted';
                li.appendChild(icon);
                li.appendChild(document.createTextNode(gt));
                fullGroundTruthsDiv.appendChild(li);
            });
            ulGroundTruths.appendChild(fullGroundTruthsDiv);

            let showMoreButton;
            let showLessButton;

            if (result.ground_truths.length > GROUNDTRUTH_DISPLAY_LIMIT) {
                showMoreButton = document.createElement('button');
                showMoreButton.className = 'btn btn-link btn-sm p-0 mt-1 show-more-groundtruths';
                showMoreButton.type = 'button';
                showMoreButton.textContent = `Show ${result.ground_truths.length - GROUNDTRUTH_DISPLAY_LIMIT} more`;
                
                showLessButton = document.createElement('button');
                showLessButton.className = 'btn btn-link btn-sm p-0 mt-1 show-less-groundtruths';
                showLessButton.type = 'button';
                showLessButton.style.display = 'none';
                showLessButton.textContent = 'Show less';

                showMoreButton.onclick = (e) => {
                    e.stopPropagation();
                    fullGroundTruthsDiv.style.display = 'block';
                    showMoreButton.style.display = 'none';
                    showLessButton.style.display = 'inline';
                };

                showLessButton.onclick = (e) => {
                    e.stopPropagation();
                    fullGroundTruthsDiv.style.display = 'none';
                    showMoreButton.style.display = 'inline';
                    showLessButton.style.display = 'none';
                };
            }
            
            const td1 = document.createElement('td');
            td1.className = 'px-4 fw-bold text-muted small';
            td1.textContent = index + 1;
            row.appendChild(td1);

            const td2 = document.createElement('td');
            td2.className = 'px-4';
            td2.textContent = result.question;
            row.appendChild(td2);

            const td3 = document.createElement('td');
            td3.className = 'px-4';
            const em = document.createElement('em');
            em.textContent = `“${result.final_answer || 'N/A'}”`;
            td3.appendChild(em);
            row.appendChild(td3);

            const td4 = document.createElement('td');
            td4.className = 'px-4';
            td4.appendChild(ulGroundTruths);
            if (showMoreButton) {
                td4.appendChild(showMoreButton);
                td4.appendChild(showLessButton);
            }
            row.appendChild(td4);

            const td5 = document.createElement('td');
            td5.className = 'px-4 text-center';
            td5.appendChild(resultBadge);
            row.appendChild(td5);

            const td6 = document.createElement('td');
            td6.className = 'px-4 text-center';
            td6.textContent = result.trials;
            row.appendChild(td6);
            
            return row;
        },

        renderTrial: function(trial, isCompleted, trialCount, maxRetries) {
            const trialDiv = document.createElement('div');
            trialDiv.className = 'mb-4';
            trialDiv.id = `trial-${trial.id}`;
    
            let searchSection = '';
            if (trial.search_query) {
                const resultsCount = trial.search_results ? trial.search_results.length : 0;
                const resultsJson = trial.search_results ? encodeURIComponent(JSON.stringify(trial.search_results)) : '';
                
                let resultsBadge = '';
                if (resultsCount > 0) {
                    resultsBadge = `
                        <button class="btn btn-sm btn-white bg-white border shadow-sm ms-auto view-search-results-btn d-flex align-items-center" data-results="${resultsJson}" style="font-size: 0.85rem; height: 32px;">
                            <i class="bi bi-list-task text-primary me-2"></i>
                            <span class="fw-semibold text-dark">${resultsCount}</span>
                            <span class="text-muted ms-1 small d-none d-sm-inline">results</span>
                        </button>
                    `;
                } else {
                    resultsBadge = `<span class="badge bg-secondary bg-opacity-10 text-secondary border ms-auto">No results</span>`;
                }
    
                searchSection = `
                    <div class="d-flex align-items-center bg-light bg-opacity-50 rounded p-2 mb-3 border border-light-subtle">
                        <div class="d-flex align-items-center flex-grow-1 overflow-hidden">
                            <div class="bg-white rounded-circle border d-flex align-items-center justify-content-center me-3 shadow-sm" style="width: 36px; height: 36px; min-width: 36px;">
                                <i class="bi bi-search text-primary" style="font-size: 1rem;"></i>
                            </div>
                            <div class="d-flex flex-column overflow-hidden me-3">
                                <span class="text-uppercase text-muted fw-bold" style="font-size: 0.65rem; letter-spacing: 1px;">Search Query</span>
                                <span class="text-dark fw-medium text-truncate font-monospace small" title="${trial.search_query}">${trial.search_query}</span>
                            </div>
                        </div>
                        ${resultsBadge}
                    </div>
                `;
            }
    
    
            let trialBody = '';
            if (trial.status === 'processing') {
                trialBody = `<div class="d-flex align-items-center py-3">
                                <div class="spinner-border text-primary me-3" role="status" style="width: 2rem; height: 2rem;">
                                    <span class="visually-hidden">Loading...</span>
                                </div>
                                <div>
                                    <h6 class="mb-0 text-dark">Processing...</h6>
                                    <small class="text-muted">Waiting for LLM response</small>
                                </div>
                             </div>`;
            } else if (trial.status === 'error') {
                trialBody = `<div class="alert alert-danger border-0 shadow-sm d-flex align-items-center">
                                <i class="bi bi-exclamation-triangle-fill me-3 fs-4"></i>
                                <div>
                                    <strong>Error</strong>
                                    <div class="small">An error occurred while running this trial.</div>
                                </div>
                             </div>`;
            } else { // completed
                let feedbackControls = '';
                if (!isCompleted && trialCount < maxRetries) {
                    if (trial.is_correct === false) {
                        feedbackControls = `<div class="d-flex align-items-center mt-3 text-warning bg-warning bg-opacity-10 p-2 rounded">
                                                <span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>
                                                <span class="small fw-medium">Answer was incorrect. Automatically retrying...</span>
                                             </div>`;
                    } else if (trial.is_correct === null) {
                        feedbackControls = `<p class="mt-2 text-muted small"><i class="bi bi-hourglass-split me-1"></i>Awaiting automated judgment...</p>`;
                    }
                }
    
                trialBody = `
                            ${searchSection}
                            <div class="p-3 bg-white rounded border-start border-4 border-primary shadow-sm mb-3">
                                <div class="d-flex align-items-start">
                                    <i class="bi bi-chat-quote text-primary opacity-50 fs-3 me-3"></i>
                                    <div>
                                        <span class="text-uppercase text-muted fw-bold d-block mb-1" style="font-size: 0.65rem; letter-spacing: 1px;">LLM Answer</span>
                                        <p class="mb-0 fs-6 text-dark">${trial.answer}</p>
                                    </div>
                                </div>
                            </div>`;
                if (trial.feedback) {
                    const isCorrect = trial.is_correct;
                    const alertClass = isCorrect ? 'alert-success' : 'alert-danger';
                    const icon = isCorrect ? '<i class="bi bi-check-circle-fill me-2 fs-5"></i>' : '<i class="bi bi-x-circle-fill me-2 fs-5"></i>';
                    trialBody += `<div class="alert ${alertClass} border-0 d-flex align-items-center mt-3 shadow-sm" role="alert">
                                    ${icon}
                                    <div>
                                        <strong class="d-block text-uppercase" style="font-size: 0.7rem; letter-spacing: 0.5px;">Verdict</strong>
                                        ${trial.feedback}
                                    </div>
                                  </div>`;
                }
                trialBody += feedbackControls;
            }
    
            const isLastAttempt = trialCount >= maxRetries;
            let statusBadge = '';
            if (isCompleted || isLastAttempt || trial.is_correct === true) {
                if (trial.is_correct) {
                    statusBadge = '<span class="badge bg-success rounded-pill shadow-sm"><i class="bi bi-check-lg me-1"></i>Correct</span>';
                } else if (trial.is_correct === false) {
                     statusBadge = '<span class="badge bg-danger rounded-pill shadow-sm"><i class="bi bi-x-lg me-1"></i>Incorrect</span>';
                }
            }
    
            trialDiv.innerHTML = `
                <div class="card border-0 shadow-sm overflow-hidden">
                    <div class="card-header bg-white border-bottom py-3 d-flex justify-content-between align-items-center">
                        <h6 class="mb-0 fw-bold text-secondary text-uppercase small" style="letter-spacing: 1px;">
                            <i class="bi bi-arrow-return-right me-2"></i>Trial #${trial.trial_number}
                        </h6>
                        <div>${statusBadge}</div>
                    </div>
                    <div class="card-body bg-light bg-opacity-10">
                        ${trialBody}
                    </div>
                </div>`;
            return trialDiv;
        },
    },
    displayRunResults: function(runData, updateSummaryFunc, pipelineType = 'vanilla_adhoc') {
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
            const summary = BenchmarkUtils.BenchmarkRenderer.renderResultRow(result, resultsBody, index + 1, pipelineType);
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
    },

    renderRunConfiguration: function(snapshot, whitelist = null) {
        const configCard = document.getElementById('run-config-card');
        const configDetails = document.getElementById('run-config-details');
        
        if (!configCard || !configDetails) return;

        snapshot = snapshot || {}; 

        configDetails.innerHTML = '';
        
        const addItem = (label, value, icon) => {
            const col = document.createElement('div');
            col.className = 'col-md-4 col-sm-6';

            const divFlex = document.createElement('div');
            divFlex.className = 'd-flex align-items-center bg-white p-2 rounded border';

            const iconElement = document.createElement('i');
            iconElement.className = `bi ${icon} text-secondary me-2 fs-5`;
            divFlex.appendChild(iconElement);

            const divOverflow = document.createElement('div');
            divOverflow.className = 'overflow-hidden';

            const divLabel = document.createElement('div');
            divLabel.className = 'text-muted text-uppercase';
            divLabel.style.fontSize = '0.65rem';
            divLabel.style.letterSpacing = '0.5px';
            divLabel.textContent = label;
            divOverflow.appendChild(divLabel);

            const divValue = document.createElement('div');
            divValue.className = 'fw-medium text-truncate';
            divValue.title = value;
            divValue.textContent = value; 
            divOverflow.appendChild(divValue);

            divFlex.appendChild(divOverflow);
            col.appendChild(divFlex);
            configDetails.appendChild(col);
        };

        const shouldShow = (key) => !whitelist || whitelist.includes(key);
        const getValue = (obj, key, domId) => {
            if (obj && (obj[key] !== undefined && obj[key] !== null && obj[key] !== '')) return obj[key];
            const el = document.getElementById(domId);
            return el ? el.value : null;
        };
        
        // Check for nested first (if full snapshot passed)
        let llmSettings = snapshot.llm_settings || snapshot; 

        if (shouldShow('llm_model')) {
            const val = getValue(llmSettings, 'llm_model', 'llm_model');
            if (val) addItem('LLM Model', val, 'bi-cpu');
        }
        if (shouldShow('max_retries')) {
            const val = getValue(llmSettings, 'max_retries', 'max_retries');
            if (val) addItem('Max Retries', val, 'bi-arrow-repeat');
        }
        if (shouldShow('llm_base_url')) {
            const val = getValue(llmSettings, 'llm_base_url', 'llm_base_url');
            if (val) addItem('Base URL', val, 'bi-link-45deg');
        }

        if (shouldShow('rag_settings')) {
            const rs = snapshot.rag_settings || {};
            let prompt = rs.prompt_template;
            if (!prompt && document.getElementById('rag_prompt_template')) {
                prompt = document.getElementById('rag_prompt_template').value;
            }
            if (prompt) {
                const snippet = prompt.substring(0, 30) + '...';
                addItem('RAG Prompt', snippet, 'bi-chat-text');
            }
        }
        
        if (shouldShow('search_settings')) {
            const ss = snapshot.search_settings || {};
            let provider = ss.search_provider;
            if (!provider && document.querySelector('input[name="search_provider"]:checked')) {
                provider = document.querySelector('input[name="search_provider"]:checked').value;
            }
            if (provider) {
                addItem('Search Provider', provider === 'mcp' ? 'MCP Server' : (provider === 'serper' ? 'Serper API' : provider), 'bi-globe');
            }
            
            // Full content
            let fullContent = ss.serper_fetch_full_content;
             if (fullContent === undefined && document.getElementById('serper_fetch_full_content')) {
                 fullContent = document.getElementById('serper_fetch_full_content').checked;
             }
            
            if (fullContent !== undefined) {
                addItem('Full Content', fullContent ? 'Enabled' : 'Disabled', 'bi-file-text');
            }
        }

        if (configDetails.children.length > 0) {
            configCard.style.display = 'block';
        } else {
            configCard.style.display = 'none';
        }
    },

    /**
     * Export data to CSV.
     * @param {Array} data - Array of data objects.
     * @param {string} filenamePrefix - Prefix for the filename.
     * @param {Array} headers - Array of header strings.
     * @param {Function} rowMapper - Function that takes a data item and index, returns an array of cell values.
     */
    exportToCSV: function(data, filenamePrefix, headers, rowMapper) {
        if (!data || data.length === 0) {
            alert("No results to export.");
            return;
        }

        const csvRows = [headers.join(',')];

        data.forEach((item, index) => {
            const rowValues = rowMapper(item, index);
            // Escape quotes and wrap in quotes
            const escapedRow = rowValues.map(val => {
                if (val === null || val === undefined) return '';
                const str = String(val);
                return `"${str.replace(/"/g, '""')}"`;
            });
            csvRows.push(escapedRow.join(','));
        });

        const csvString = csvRows.join('\n');
        const blob = new Blob([csvString], { type: 'text/csv;charset=utf-8;' });

        const link = document.createElement("a");
        if (link.download !== undefined) {
            const url = URL.createObjectURL(blob);
            
            // Try to get a meaningful name from the UI if possible, else use timestamp
            let nameSuffix = '';
            const resultsHeader = document.getElementById("results-header-text");
            if (resultsHeader && resultsHeader.textContent) {
                nameSuffix = resultsHeader.textContent.replace('Results for', '').trim();
            }
            if (!nameSuffix) {
                nameSuffix = new Date().toISOString().slice(0, 19).replace('T', '_').replace(/:/g, '-');
            }

            const filename = `${filenamePrefix}-${nameSuffix.replace(/[^a-zA-Z0-9-_]/g, '_')}.csv`;
            
            link.setAttribute("href", url);
            link.setAttribute("download", filename);
            link.style.visibility = 'hidden';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }
    },

    /**
     * Process a streamed JSON response (NDJSON).
     * @param {Response} response - The fetch Response object.
     * @param {Function} onData - Callback for each parsed JSON object.
     * @param {Function} onComplete - Callback when stream completes.
     * @param {Function} onError - Callback on error.
     * @param {AbortSignal} abortSignal - Signal to check for abortion.
     */
    processStreamedResponse: function(response, onData, onComplete, onError, abortSignal) {
        if (!response.ok) {
            onError(new Error(`HTTP error! status: ${response.status}`));
            return;
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        function push() {
            reader.read().then(({ done, value }) => {
                if (done) {
                    if (onComplete) onComplete();
                    return;
                }

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop(); // Keep partial line

                lines.forEach(line => {
                    if (abortSignal && abortSignal.aborted) {
                        reader.cancel();
                        return;
                    }
                    if (line.trim() === '') return;

                    try {
                        let data = JSON.parse(line);
                        // Handle double-encoded JSON if necessary (though ideally backend shouldn't do this)
                        if (typeof data === 'string') {
                            try { data = JSON.parse(data); } catch(e) {}
                        }
                        onData(data);
                    } catch (e) {
                        console.error("Failed to parse JSON chunk:", e, line);
                    }
                });
                
                if (abortSignal && abortSignal.aborted) {
                     return; // Don't continue reading
                }

                push();
            }).catch(error => {
                if (onError) onError(error);
            });
        }
        push();
    },

    /**
     * Update standard Adhoc pipeline statistics UI.
     * @param {object} stats - Stats object { total, ruleCorrect, llmCorrect, llmErrors, agreements, totalDocsUsed }.
     */
    updateAdhocStatsUI: function(stats) {
        if (document.getElementById('rule-correct-count')) {
            document.getElementById('rule-correct-count').textContent = stats.ruleCorrect;
        }
        if (document.getElementById('rule-incorrect-count')) {
            const ruleIncorrect = stats.total - stats.ruleCorrect;
            document.getElementById('rule-incorrect-count').textContent = ruleIncorrect;
        }
        if (document.getElementById('rule-accuracy-rate')) {
            const ruleAccuracy = stats.total > 0 ? (stats.ruleCorrect / stats.total) * 100 : 0;
            document.getElementById('rule-accuracy-rate').textContent = `${ruleAccuracy.toFixed(2)}%`;
        }

        if (document.getElementById('llm-correct-count')) {
            document.getElementById('llm-correct-count').textContent = stats.llmCorrect;
        }
        if (document.getElementById('llm-incorrect-count')) {
            const llmIncorrect = stats.total - stats.llmCorrect - stats.llmErrors;
            document.getElementById('llm-incorrect-count').textContent = llmIncorrect;
        }
        if (document.getElementById('llm-accuracy-rate')) {
            const llmAccuracy = stats.total > 0 ? (stats.llmCorrect / stats.total) * 100 : 0;
            document.getElementById('llm-accuracy-rate').textContent = `${llmAccuracy.toFixed(2)}%`;
        }

        if (document.getElementById('processed-count')) {
            document.getElementById('processed-count').textContent = stats.total;
        }
        
        if (document.getElementById('agreement-rate')) {
            const agreementRate = stats.total > 0 ? (stats.agreements / stats.total) * 100 : 0;
            document.getElementById('agreement-rate').textContent = `${agreementRate.toFixed(2)}%`;
        }

        if (document.getElementById('total-searches-count')) {
            document.getElementById('total-searches-count').textContent = stats.total; 
        }
        if (document.getElementById('avg-docs-count')) {
            const avgDocs = stats.total > 0 ? (stats.totalDocsUsed / stats.total) : 0;
            document.getElementById('avg-docs-count').textContent = avgDocs.toFixed(1);
        }
    },

    MultiTurnUtils: {
        /**
         * Update Multi-turn pipeline statistics UI.
         * @param {Array} results - The array of result objects.
         * @param {string} groupName - The name of the group.
         * @param {function} loadSessionCallback - Callback when a row is clicked.
         */
        updateStatsUI: function(results, groupName, loadSessionCallback) {
            const totalQuestions = results.length;
            // if (totalQuestions === 0) return; // Allow updating to clear stats if empty

            const header = document.getElementById("results-header-text");
            if (header) header.textContent = `Results for ${groupName}`;

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

            const setText = (id, text) => {
                const el = document.getElementById(id);
                if (el) el.textContent = text;
            };

            setText('stats-accuracy', `${accuracy.toFixed(2)}%`);
            setText('stats-correct-count', correctCount);
            setText('stats-incorrect-count', incorrectCount);
            setText('stats-error-count', errorCount);
            setText('stats-avg-trials-all', avgTrialsAll.toFixed(2));
            setText('stats-avg-trials-success', avgTrialsSuccess.toFixed(2));
            setText('stats-first-try-success', `${firstTrySuccessRate.toFixed(2)}%`);
            setText('stats-give-up-rate', `${giveUpRate.toFixed(2)}%`);

            const tbody = document.getElementById('stats-details-tbody');
            if (tbody) {
                tbody.innerHTML = '';
                results.forEach((result, index) => {
                    const row = BenchmarkUtils.BenchmarkRenderer.renderMultiTurnResultRow(result, index, loadSessionCallback);
                    tbody.appendChild(row);
                });
            }

            const statsContainer = document.getElementById('statistics-container');
            if (statsContainer) statsContainer.style.display = 'block';
        },

        /**
         * Add a new session to the session list UI.
         * @param {string} sessionListId - The ID of the session list container.
         * @param {string} sessionId - The session ID.
         * @param {object} questionData - Data about the question (e.g., {question: "..."}).
         * @param {function} selectAllHandler - Function to handle select all checkbox change.
         * @param {string} groupId - The group ID (optional).
         * @param {string} groupName - The group name (optional).
         * @param {string} statusText - The status text to display.
         */
        addNewSessionToList: function(sessionListId, sessionId, questionData, selectAllHandler, groupId = null, groupName = null, statusText = 'Now') {
            const sessionList = document.getElementById(sessionListId);
            if (!sessionList) return;

            // Check if session already exists
            const existingCheckbox = document.querySelector(`.session-checkbox[value="${sessionId}"]`);
            if (existingCheckbox) {
                const sessionDetails = document.querySelector(`.session-details[data-session-id="${sessionId}"]`);
                if (sessionDetails) {
                     const timeEl = sessionDetails.querySelector('small.text-muted');
                     if (timeEl) {
                         timeEl.textContent = statusText;
                     }
                }
                return;
            }

            // If this is the first session ever, remove "no sessions" and add select-all header
            if (document.querySelector('.no-sessions')) {
                const noSessions = document.querySelector('.no-sessions');
                if (noSessions) noSessions.remove();
                
                // Only create if it doesn't exist
                if (!document.getElementById('select-all-container')) {
                    const selectAllContainer = document.createElement('div');
                    selectAllContainer.className = 'list-group-item bg-light';
                    selectAllContainer.id = 'select-all-container';
                    selectAllContainer.innerHTML = `
                        <input class="form-check-input" type="checkbox" id="select-all-checkbox">
                        <label class="form-check-label ms-2" for="select-all-checkbox">Select All</label>`;
                    sessionList.prepend(selectAllContainer);
                    const cb = document.getElementById('select-all-checkbox');
                    if (cb && selectAllHandler) cb.addEventListener('change', selectAllHandler);
                }
            }

            const newSessionItem = document.createElement('div');
            newSessionItem.className = 'list-group-item d-flex align-items-center session-item-container';
            newSessionItem.innerHTML = `
                <input class="form-check-input session-checkbox" type="checkbox" value="${sessionId}" data-session-id="${sessionId}">
                <div class="ms-3 flex-grow-1 session-details" data-session-id="${sessionId}" style="cursor: pointer;">
                    <div class="d-flex w-100 justify-content-between">
                        <h6 class="mb-1">Session #${sessionId}</h6>
                        <small class="text-muted">${statusText}</small>
                    </div>
                    <p class="mb-1 small text-muted">${(questionData.question || '').substring(0, 100)}...</p>
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
                    if (selectAllDiv) {
                        selectAllDiv.after(groupEl);
                    } else {
                        sessionList.prepend(groupEl);
                    }
                    groupContainer = document.getElementById(`session-group-${groupId}`);
                }
                newSessionItem.classList.add("ps-4");
                groupContainer.prepend(newSessionItem);
                
                // Update session count
                const countEl = document.getElementById(`group-session-count-${groupId}`);
                if (countEl) {
                    const currentCount = groupContainer.children.length;
                    countEl.textContent = `(${currentCount} sessions)`;
                }

            } else {
                const selectAllDiv = document.getElementById('select-all-container');
                if (selectAllDiv) {
                    selectAllDiv.after(newSessionItem);
                } else {
                    sessionList.appendChild(newSessionItem);
                }
            }
        }
    }
};
