window.BenchmarkUtils.BenchmarkRenderer = {
        ...BenchmarkComponents,
        
        renderProcessingRow: function(item, resultsBody, colSpan = 7) {
            const rowId = `processing-row`; // Fixed ID for easier finding
            const tr = document.createElement('tr');
            tr.id = rowId;
            tr.className = 'table-light border-bottom-0 processing-row';
            
            const td = document.createElement('td');
            td.colSpan = colSpan;
            td.className = 'text-center py-4 text-muted';
            
            td.innerHTML = `
                <div class="d-flex flex-column align-items-center justify-content-center">
                    <div class="spinner-border text-primary mb-2" role="status">
                        <span class="visually-hidden">Loading...</span>
                    </div>
                    <div class="fw-medium">Processing Question:</div>
                    <div class="small text-dark fw-bold mt-1" style="max-width: 80%; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                        ${item.question || 'Unknown'}
                    </div>
                </div>
            `;
            
            tr.appendChild(td);
            resultsBody.insertAdjacentElement('afterbegin', tr); // Add to top
            return tr;
        },
        
        // Helper to render ground truths list with expansion
        renderGroundTruthsList: function(groundTruthsArray, displayLimit = 3) {
            const ul = document.createElement('ul');
            ul.className = 'list-unstyled mb-0';

            const visibleItems = groundTruthsArray.slice(0, displayLimit);
            const hiddenItems = groundTruthsArray.slice(displayLimit);

            const createItem = (text) => {
                const li = document.createElement('li');
                li.className = 'text-secondary small ground-truth-item';
                li.appendChild(this.createIcon('bi bi-dot me-1 text-muted'));
                li.appendChild(document.createTextNode(text));
                return li;
            };

            visibleItems.forEach(gt => ul.appendChild(createItem(gt)));

            if (hiddenItems.length > 0) {
                const hiddenContainer = document.createElement('div');
                hiddenContainer.style.display = 'none';
                hiddenItems.forEach(gt => hiddenContainer.appendChild(createItem(gt)));
                ul.appendChild(hiddenContainer);

                const liBtn = document.createElement('li');
                liBtn.className = 'show-more-item';
                
                const showMoreBtn = document.createElement('button');
                showMoreBtn.className = 'btn btn-link btn-sm p-0 text-decoration-none small toggle-answers-link';
                showMoreBtn.textContent = `... Show ${hiddenItems.length} more`;
                showMoreBtn.type = 'button';
                
                const showLessBtn = document.createElement('button');
                showLessBtn.className = 'btn btn-link btn-sm p-0 text-decoration-none small toggle-answers-link';
                showLessBtn.textContent = 'Show less';
                showLessBtn.type = 'button';
                showLessBtn.style.display = 'none';

                showMoreBtn.onclick = (e) => {
                    e.stopPropagation();
                    hiddenContainer.style.display = 'block';
                    showMoreBtn.style.display = 'none';
                    showLessBtn.style.display = 'inline-block';
                };

                showLessBtn.onclick = (e) => {
                    e.stopPropagation();
                    hiddenContainer.style.display = 'none';
                    showMoreBtn.style.display = 'inline-block';
                    showLessBtn.style.display = 'none';
                };

                liBtn.appendChild(showMoreBtn);
                liBtn.appendChild(showLessBtn);
                ul.appendChild(liBtn);
            }
            return ul;
        },

        // Helper to render ground truths as badges with expansion
        renderGroundTruthsBadges: function(groundTruthsArray, displayLimit = 3) {
            const container = document.createElement('div');
            
            const createBadge = (text) => {
                const el = document.createElement('span');
                el.className = 'badge bg-secondary me-1';
                el.textContent = text;
                return el;
            };

            const visibleItems = groundTruthsArray.slice(0, displayLimit);
            const hiddenItems = groundTruthsArray.slice(displayLimit);

            visibleItems.forEach(gt => container.appendChild(createBadge(gt)));

            if (hiddenItems.length > 0) {
                const hiddenContainer = document.createElement('div');
                hiddenContainer.style.display = 'none';
                hiddenContainer.className = 'mt-1';
                hiddenItems.forEach(gt => hiddenContainer.appendChild(createBadge(gt)));
                container.appendChild(hiddenContainer);

                const showMoreBtn = document.createElement('button');
                showMoreBtn.className = 'btn btn-link btn-sm p-0';
                showMoreBtn.textContent = `Show ${hiddenItems.length} more`;
                showMoreBtn.type = 'button';
                
                const showLessBtn = document.createElement('button');
                showLessBtn.className = 'btn btn-link btn-sm p-0 ms-2';
                showLessBtn.textContent = 'Show less';
                showLessBtn.type = 'button';
                showLessBtn.style.display = 'none';

                showMoreBtn.onclick = (e) => {
                    e.stopPropagation();
                    hiddenContainer.style.display = 'block';
                    showMoreBtn.style.display = 'none';
                    showLessBtn.style.display = 'inline-block';
                };

                showLessBtn.onclick = (e) => {
                    e.stopPropagation();
                    hiddenContainer.style.display = 'none';
                    showMoreBtn.style.display = 'inline-block';
                    showLessBtn.style.display = 'none';
                };

                container.appendChild(showMoreBtn);
                container.appendChild(showLessBtn);
            }
            return container;
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
            } else {
                const ruleCorrect = data.hasOwnProperty('is_correct_rule') ? data.is_correct_rule : data.rule_result;
                const llmCorrect = data.hasOwnProperty('is_correct_llm') ? data.is_correct_llm : data.llm_result;
                
                let rowClass = 'table-light';
                let textClass = 'text-dark';

                if (llmCorrect === true) {
                    rowClass = 'table-success-light';
                    textClass = 'text-success-dark';
                } else if (llmCorrect === false) {
                    rowClass = 'table-danger-light';
                    textClass = 'text-danger-dark';
                } else if (ruleCorrect === true) {
                     rowClass = 'table-warning-light'; 
                }

                tr.className = rowClass;
                const textColorClass = textClass;

                // Cell 1: Index
                const td1 = document.createElement('td');
                td1.className = 'px-4 fw-bold text-muted small';
                if (index) td1.textContent = index;
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

                if (data.full_response && data.full_response !== data.answer) {
                    const reasoningContainer = document.createElement('div');
                    reasoningContainer.className = 'mt-1';
                    const viewReasoningBtn = document.createElement('button');
                    viewReasoningBtn.className = 'btn btn-link btn-sm p-0 text-decoration-none small view-reasoning-btn';
                    viewReasoningBtn.dataset.reasoning = data.full_response;
                    viewReasoningBtn.type = 'button';
                    viewReasoningBtn.innerHTML = '<i class="bi bi-card-text"></i> View Reasoning';
                    viewReasoningBtn.style.fontSize = '0.9rem';
                    viewReasoningBtn.classList.add(textColorClass);
                    reasoningContainer.appendChild(viewReasoningBtn);
                    td3.appendChild(reasoningContainer);
                }
                tr.appendChild(td3);

                // Cell 4: Ground Truths
                const td4 = document.createElement('td');
                const groundTruthsArray = data.ground_truths || [];
                td4.appendChild(this.renderGroundTruthsList(groundTruthsArray));
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
            
            return { ruleCorrect: finalRuleCorrect, llmCorrect: finalLlmCorrect, rowId: rowId };
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

        renderModalSearchResults: function(results, container, modalId = 'benchmarkGenericModal') {
            const modalTitle = document.getElementById(modalId + 'Label');
            if (modalTitle) modalTitle.textContent = 'Search Results';
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

        /**
         * Renders a modal with the full RAG prompt content.
         * @param {string} promptContent - The full RAG prompt text.
         * @param {string} containerId - The ID of the modal body container.
         * @param {string} modalId - The ID of the modal itself.
         * @param {string} title - The title to display in the modal header.
         */
        renderPromptModal: function(promptContent, containerId, modalId = 'benchmarkGenericModal', title = 'RAG Prompt') {
            const modalTitle = document.getElementById(modalId + 'Label');
            if (modalTitle) modalTitle.textContent = title;

            const container = document.getElementById(containerId);
            if (!container) return;

            container.innerHTML = ''; // Clear existing content

            const pre = document.createElement('pre');
            pre.className = 'p-3 bg-light border rounded small text-secondary';
            pre.style.whiteSpace = 'pre-wrap';
            pre.textContent = promptContent;
            container.appendChild(pre);

            const modal = new bootstrap.Modal(document.getElementById(modalId));
            modal.show();
        },

        renderMultiTurnResultRow: function(result, index, loadSessionCallback) {
            const row = document.createElement('tr');
            row.style.cursor = "pointer";
            if (loadSessionCallback) {
                row.onclick = () => loadSessionCallback(result.session_id);
            }

            // Cell 1: Index
            const td1 = document.createElement('td');
            td1.className = 'px-4 fw-bold text-muted small';
            td1.textContent = index + 1;
            row.appendChild(td1);

            // Cell 2: Question
            const td2 = document.createElement('td');
            td2.className = 'px-4';
            td2.textContent = result.question;
            row.appendChild(td2);

            // Cell 3: Answer
            const td3 = document.createElement('td');
            td3.className = 'px-4';
            const em = document.createElement('em');
            em.textContent = `“${result.final_answer || 'N/A'}”`;
            td3.appendChild(em);
            row.appendChild(td3);

            // Cell 4: Ground Truths
            const td4 = document.createElement('td');
            td4.className = 'px-4';
            td4.appendChild(this.renderGroundTruthsList(result.ground_truths));
            row.appendChild(td4);

            // Cell 5: Status Badge
            const td5 = document.createElement('td');
            td5.className = 'px-4 text-center';
            if (result.correct === true) {
                td5.appendChild(this.createBadge(null, true));
            } else if (result.correct === false) {
                td5.appendChild(this.createBadge(null, false));
            } else {
                 // Error/Unknown state
                 const span = document.createElement('span');
                 span.className = 'badge bg-warning text-dark';
                 span.textContent = 'Error';
                 td5.appendChild(span);
            }
            row.appendChild(td5);

            // Cell 6: Trials
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
    
                // Determine if we have reasoning to show
                let reasoningSection = '';
                if (trial.full_response && trial.full_response !== trial.answer) {
                    // We generate a unique ID for the collapse element
                    const collapseId = `reasoning-collapse-${trial.id || Math.random().toString(36).substr(2, 9)}`;
                    reasoningSection = `
                        <div class="mt-2">
                            <button class="btn btn-sm btn-link text-decoration-none p-0 collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#${collapseId}" aria-expanded="false" aria-controls="${collapseId}">
                                <i class="bi bi-caret-right-fill"></i> Show Chain of Thought
                            </button>
                            <div class="collapse mt-2" id="${collapseId}">
                                <div class="card card-body bg-light border-0 small text-secondary" style="white-space: pre-wrap;">${trial.full_response}</div>
                            </div>
                        </div>
                    `;
                }

                trialBody = `
                            ${searchSection}
                            <div class="p-3 bg-white rounded border-start border-4 border-primary shadow-sm mb-3">
                                <div class="d-flex align-items-start">
                                    <i class="bi bi-chat-quote text-primary opacity-50 fs-3 me-3"></i>
                                    <div class="w-100">
                                        <span class="text-uppercase text-muted fw-bold d-block mb-1" style="font-size: 0.65rem; letter-spacing: 1px;">LLM Answer</span>
                                        <p class="mb-0 fs-6 text-dark">${trial.answer}</p>
                                        ${reasoningSection}
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
        
        // Ensure status and processing rows are cleared
        const statusDiv = document.getElementById('pipeline-status');
        if (statusDiv) statusDiv.style.display = 'none';
        const processingRow = document.getElementById('processing-row');
        if (processingRow) processingRow.remove();

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
            result.rowId = summary.rowId; // Attach rowId for future reference (e.g. retry)
            
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
        if (shouldShow('allow_reasoning')) {
            let val = getValue(llmSettings, 'allow_reasoning', 'allow_reasoning');
            // If pulling from DOM checkbox
            if (val === 'on' || val === true) val = 'Enabled';
            else if (val === false) val = 'Disabled';
            
            // If pulling from snapshot (boolean)
            if (val === true) val = 'Enabled';
            if (val === false) val = 'Disabled';

            if (val) addItem('Reasoning', val, 'bi-lightbulb');
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
                const col = document.createElement('div');
                col.className = 'col-md-4 col-sm-6';

                const divFlex = document.createElement('div');
                divFlex.className = 'd-flex align-items-center bg-white p-2 rounded border';

                const iconElement = document.createElement('i');
                iconElement.className = 'bi bi-chat-text text-secondary me-2 fs-5';
                divFlex.appendChild(iconElement);

                const divOverflow = document.createElement('div');
                divOverflow.className = 'overflow-hidden flex-grow-1';

                const divLabel = document.createElement('div');
                divLabel.className = 'text-muted text-uppercase';
                divLabel.style.fontSize = '0.65rem';
                divLabel.style.letterSpacing = '0.5px';
                divLabel.textContent = 'RAG Prompt';
                divOverflow.appendChild(divLabel);

                const button = document.createElement('button');
                button.className = 'btn btn-sm btn-outline-secondary mt-1';
                button.type = 'button';
                button.textContent = 'View Full Prompt';
                button.onclick = () => {
                    BenchmarkUtils.BenchmarkRenderer.renderPromptModal(prompt, 'modal-generic-content-container', 'benchmarkGenericModal', 'RAG Prompt');
                };

                divOverflow.appendChild(button);
                divFlex.appendChild(divOverflow);
                col.appendChild(divFlex);
                configDetails.appendChild(col);
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
            
            // Search Limit
            let searchLimit = ss.search_limit;
            if ((searchLimit === undefined || searchLimit === '') && document.getElementById('search_limit')) {
                searchLimit = document.getElementById('search_limit').value;
            }
            if (searchLimit) {
                addItem('Top-K Limit', searchLimit, 'bi-list-ol');
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
        
        if (shouldShow('agent_config')) {
            const ac = snapshot.agent_config || {};
            // If pulling from DOM
            let memory = ac.memory_type;
             if (!memory && document.getElementById('agent_memory_type')) {
                 memory = document.getElementById('agent_memory_type').value;
             }
             if (memory) {
                 const memoryMap = {
                     'naive': 'Naive Memory',
                     'mem0': 'Mem0 Memory',
                     'reme': 'ReMe Memory'
                 };
                 addItem('Agent Memory', memoryMap[memory] || memory, 'bi-memory');
             }
        }

        if (configDetails.children.length > 0) {
            configCard.style.display = 'block';
        } else {
            configCard.style.display = 'none';
        }
    }
};
