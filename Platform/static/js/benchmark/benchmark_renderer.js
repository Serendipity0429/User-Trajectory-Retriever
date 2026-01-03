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
                    
                    if (data.search_query) {
                        const queryDiv = document.createElement('div');
                        queryDiv.className = 'small text-muted mb-2 font-monospace text-truncate';
                        queryDiv.style.maxWidth = '200px';
                        queryDiv.title = `Query: ${data.search_query}`;
                        queryDiv.innerHTML = `<i class="bi bi-search me-1"></i>${data.search_query}`;
                        tdSearch.appendChild(queryDiv);
                    }

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
                    const fullContent = res.content || '';
                    
                    let domain = '';
                    try {
                        if (linkUrl && linkUrl !== '#') {
                            const urlObj = new URL(linkUrl);
                            domain = urlObj.hostname.replace('www.', '');
                        }
                    } catch(err) {}

                    const item = document.createElement('div');
                    item.className = 'list-group-item p-3 border rounded mb-3 shadow-sm bg-white';

                    // Title and Link
                    const header = document.createElement('div');
                    header.className = 'd-flex w-100 justify-content-between align-items-center mb-2';
                    
                    const titleWrapper = document.createElement('h6');
                    titleWrapper.className = 'mb-0 text-primary fw-bold d-flex align-items-center';
                    
                    const idxBadge = document.createElement('span');
                    idxBadge.className = 'badge bg-light text-muted border me-2';
                    idxBadge.textContent = idx + 1;
                    titleWrapper.appendChild(idxBadge);
                    
                    const aTitle = document.createElement('a');
                    aTitle.href = linkUrl;
                    aTitle.target = '_blank';
                    aTitle.className = 'text-decoration-none';
                    aTitle.textContent = linkTitle;
                    titleWrapper.appendChild(aTitle);
                    
                    header.appendChild(titleWrapper);
                    
                    if (domain) {
                        const domainBadge = document.createElement('span');
                        domainBadge.className = 'badge bg-light text-secondary border-0';
                        domainBadge.style.fontSize = '0.75rem';
                        domainBadge.textContent = domain;
                        header.appendChild(domainBadge);
                    }
                    
                    item.appendChild(header);

                    // Snippet
                    const pSnippet = document.createElement('p');
                    pSnippet.className = 'mb-2 text-dark small';
                    pSnippet.style.lineHeight = '1.5';
                    pSnippet.textContent = snippet;
                    item.appendChild(pSnippet);

                    // Link URL
                    const smallLink = document.createElement('div');
                    smallLink.className = 'text-muted mb-2 text-truncate font-monospace';
                    smallLink.style.fontSize = '0.7rem';
                    smallLink.innerHTML = `<i class="bi bi-link-45deg"></i> ${linkUrl}`;
                    item.appendChild(smallLink);

                    // Full Content (Collapsible)
                    if (fullContent && fullContent !== snippet) {
                        const collapseId = `content-collapse-${idx}-${Math.random().toString(36).substr(2, 9)}`;
                        
                        const contentContainer = document.createElement('div');
                        contentContainer.className = 'mt-3 pt-2 border-top';
                        
                        const toggleBtn = document.createElement('button');
                        toggleBtn.className = 'btn btn-sm btn-outline-secondary d-flex align-items-center collapsed';
                        toggleBtn.type = 'button';
                        toggleBtn.dataset.bsToggle = 'collapse';
                        toggleBtn.dataset.bsTarget = `#${collapseId}`;
                        toggleBtn.innerHTML = `
                            <i class="bi bi-file-text me-1"></i> 
                            <span>Show Full Content</span>
                            <i class="bi bi-chevron-down ms-auto ps-3"></i>
                        `;
                        
                        // Sync text on toggle
                        toggleBtn.addEventListener('click', function() {
                            const isExpanded = this.getAttribute('aria-expanded') === 'true';
                            this.querySelector('span').textContent = isExpanded ? 'Hide Full Content' : 'Show Full Content';
                            this.querySelector('.bi-chevron-down').className = isExpanded ? 'bi bi-chevron-up ms-auto ps-3' : 'bi bi-chevron-down ms-auto ps-3';
                        });

                        const collapseDiv = document.createElement('div');
                        collapseDiv.className = 'collapse';
                        collapseDiv.id = collapseId;
                        
                        const contentBody = document.createElement('div');
                        contentBody.className = 'card card-body bg-light border-0 mt-2 small text-secondary';
                        contentBody.style.maxHeight = '300px';
                        contentBody.style.overflowY = 'auto';
                        contentBody.style.whiteSpace = 'pre-wrap';
                        contentBody.textContent = fullContent;
                        
                        collapseDiv.appendChild(contentBody);
                        contentContainer.appendChild(toggleBtn);
                        contentContainer.appendChild(collapseDiv);
                        item.appendChild(contentContainer);
                    }
                    
                    container.appendChild(item);
                });
            } else {
                const noResultsDiv = document.createElement('div');
                noResultsDiv.className = 'p-5 text-center text-muted';
                noResultsDiv.innerHTML = `
                    <i class="bi bi-search fs-1 d-block mb-3 opacity-25"></i>
                    <p>No search results data found for this trial.</p>
                `;
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

        renderTrial: function(trial, isCompleted, trialCount, maxRetries, questionText, pipelineType = 'vanilla_llm_multi_turn') {
            const trialDiv = document.createElement('div');
            trialDiv.className = 'mb-4';
            trialDiv.id = `trial-${trial.id}`;

            const isRag = pipelineType.includes('rag');

            // Helper to create message bubbles
            const createMessageBubble = (role, content, extraClass = '', iconClass = '') => {
                const isUser = role === 'user';
                // User: Right aligned, white bg, right border accent
                // Assistant: Left aligned, white bg, left border accent
                const alignment = isUser ? 'justify-content-end' : 'justify-content-start';
                
                let bubbleStyleClass = 'bg-white shadow-sm text-dark border';
                let borderStyle = '';

                if (isUser) {
                    borderStyle = 'border-right: 4px solid #0d6efd;'; // Bootstrap primary blue
                } else {
                     borderStyle = 'border-left: 4px solid #6c757d;'; // Bootstrap secondary gray
                }

                const icon = iconClass || (isUser ? 'bi-person' : 'bi-robot');
                
                // Helper to abbreviate long text
                const abbreviateText = (text, maxLength = 300) => {
                    if (!text || text.length <= maxLength) return text;
                    const id = 'collapse-' + Math.random().toString(36).substr(2, 9);
                    const visiblePart = text.substring(0, maxLength);
                    const hiddenPart = text.substring(maxLength);
                    return `
                        ${visiblePart}<span id="${id}" class="collapse">${hiddenPart}</span>
                        <a href="javascript:void(0);" class="text-decoration-none small ms-1" onclick="
                            const el = document.getElementById('${id}');
                            if (el.classList.contains('show')) {
                                el.classList.remove('show');
                                this.innerText = '...Show More';
                            } else {
                                el.classList.add('show');
                                this.innerText = ' Show Less';
                            }
                        ">...Show More</a>
                    `;
                };

                // Trim and handle newlines if it's plain text
                if (!content.includes('<div') && !content.includes('<span') && !content.includes('<code')) {
                    content = content.trim();
                    content = abbreviateText(content);
                    // Preserve newlines for plain text by converting to BR
                    content = content.replace(/\n/g, '<br>');
                }

                return `
                    <div class="d-flex ${alignment} mb-3 message-bubble">
                        ${!isUser ? `
                        <div class="flex-shrink-0 me-3">
                            <div class="rounded-circle bg-light border d-flex align-items-center justify-content-center" style="width: 38px; height: 38px;">
                                <i class="bi ${icon} text-secondary fs-5"></i>
                            </div>
                        </div>` : ''}
                        
                        <div class="p-3 rounded-3 ${bubbleStyleClass} ${extraClass}" style="max-width: 85%; ${borderStyle}">${content}</div>

                        ${isUser ? `
                        <div class="flex-shrink-0 ms-3">
                            <div class="rounded-circle bg-primary bg-opacity-10 border border-primary border-opacity-25 d-flex align-items-center justify-content-center" style="width: 38px; height: 38px;">
                                <i class="bi ${icon} text-primary fs-5"></i>
                            </div>
                        </div>` : ''}
                    </div>
                `;
            };

            let chatContent = '';

            // 1. User Instruction (Split into System and User bubbles if applicable)
            let instructionText = '';
            
            // Check if we have the new instruction format with split markers
            if (trial.query_instruction && trial.query_instruction.includes('*** SYSTEM PROMPT ***')) {
                const parts = trial.query_instruction.split('*** USER INPUT ***');
                const systemPart = parts[0].replace('*** SYSTEM PROMPT ***', '').trim();
                const userPart = parts[1] ? parts[1].trim() : '';

                // 1a. Render System Prompt Bubble
                // We use a specific style for System (e.g., dark grey or specific icon)
                const systemHtml = `
                    <div class="d-flex align-items-center mb-2 text-secondary fw-bold small">
                        <i class="bi bi-gear-fill me-2"></i> SYSTEM PROMPT
                    </div>
                    <div class="small font-monospace text-muted" style="white-space: pre-wrap;">${systemPart}</div>
                `;
                // Use 'assistant' alignment (left) but distinct styling
                chatContent += `
                    <div class="d-flex justify-content-start mb-3 message-bubble">
                        <div class="flex-shrink-0 me-3">
                            <div class="rounded-circle bg-secondary bg-opacity-10 border border-secondary border-opacity-25 d-flex align-items-center justify-content-center" style="width: 38px; height: 38px;">
                                <i class="bi bi-cpu-fill text-secondary fs-5"></i>
                            </div>
                        </div>
                        <div class="p-3 rounded-3 bg-light border shadow-sm" style="max-width: 85%; border-left: 4px solid #6c757d;">
                            ${systemHtml}
                        </div>
                    </div>
                `;

                // 1b. Render User Input Bubble
                // This is the standard User bubble
                chatContent += createMessageBubble('user', userPart.replace(/\n/g, '<br>'));

            } else {
                // Legacy / Fallback handling
                if (trial.query_instruction) {
                    instructionText = trial.query_instruction.replace(/\n/g, '<br>');
                } else if (trial.instruction) {
                    instructionText = trial.instruction.replace(/\n/g, '<br>');
                } else {
                     // Fallback (DEBUG INDICATOR)
                    const debugTag = '<span class="badge bg-warning text-dark mb-2" style="font-size: 0.6em;">MISSING BACKEND INSTRUCTION</span><br>';
                    
                    if (trial.trial_number === 1) {
                        if (isRag) {
                            instructionText = `${debugTag}<strong>Question:</strong> ${questionText || '...'}<br><br>Please generate a search query to answer this question.`;
                        } else {
                            instructionText = `${debugTag}<strong>Question:</strong> ${questionText || '...'}`;
                        }
                    } else {
                        if (isRag) {
                            instructionText = `${debugTag}Your previous answer was incorrect. Please try again with a different search query.`;
                        } else {
                            instructionText = `${debugTag}Your previous answer was incorrect. Answer the question again, potentially correcting yourself.`;
                        }
                    }
                }
                chatContent += createMessageBubble('user', instructionText);
            }

            // 2. Assistant Search Query
            if (trial.search_query) {
                let queryBody = `
                    <div class="d-flex align-items-center mb-2">
                        <i class="bi bi-search text-primary me-2"></i>
                        <span class="fw-bold text-primary small text-uppercase" style="letter-spacing: 0.5px;">Search Query Generation</span>
                    </div>
                    <code class="d-block p-2 bg-light border rounded text-primary mb-2">${trial.search_query}</code>
                `;

                if (trial.query_full_response && trial.query_full_response !== trial.search_query) {
                    const qCollapseId = `query-reasoning-${trial.id}`;
                    queryBody = `
                        <div class="mb-2">
                            <button class="btn btn-sm btn-outline-secondary p-1 px-2 collapsed text-secondary d-flex align-items-center fw-bold shadow-sm mb-2" type="button" data-bs-toggle="collapse" data-bs-target="#${qCollapseId}">
                                <i class="bi bi-cpu me-2"></i> Query Reasoning
                                <i class="bi bi-chevron-down ms-3 small"></i>
                            </button>
                            <div class="collapse mt-2" id="${qCollapseId}">
                                <div class="p-2 bg-light rounded small font-monospace text-dark border mb-2" style="white-space: pre-wrap; font-size: 0.8em; max-height: 200px; overflow-y: auto;">${trial.query_full_response}</div>
                            </div>
                        </div>
                        ${queryBody}
                    `;
                }

                chatContent += createMessageBubble('assistant', queryBody, 'p-3', 'bi-search');
            }

            // 3. Search Results (System/Tool)
            if (trial.search_query) { // Only show results if there was a query
                const resultsCount = trial.search_results ? trial.search_results.length : 0;
                let resultsHtml = '';
                
                if (resultsCount > 0) {
                     const resultsJson = trial.search_results ? encodeURIComponent(JSON.stringify(trial.search_results)) : '';
                     resultsHtml = `
                        <div>
                            <div class="d-flex align-items-center justify-content-between mb-2">
                                <div class="fw-bold">
                                    <i class="bi bi-globe me-2"></i>
                                    <span>Found ${resultsCount} results</span>
                                </div>
                                <button class="btn btn-sm btn-outline-secondary bg-white view-search-results-btn ms-3 shadow-sm" data-results="${resultsJson}">
                                    <i class="bi bi-list-ul me-1"></i> View Detail
                                </button>
                            </div>
                        </div>
                     `;
                } else {
                     resultsHtml = `<div class="text-muted"><i class="bi bi-search me-2"></i>No results found.</div>`;
                }
                
                // Tool Bubble (Center or full width, distinct style)
                chatContent += `
                    <div class="d-flex justify-content-center mb-4">
                        <div class="bg-light border rounded p-3 small text-secondary shadow-sm" style="max-width: 90%; border-style: dashed !important;">
                            ${resultsHtml}
                        </div>
                    </div>
                `;

                // 3b. User Answer Instruction (Separate Bubble)
                if (trial.final_answer_instruction) {
                    let instrContent = trial.final_answer_instruction;
                    
                    const escapeHtml = (text) => {
                        return text
                            .replace(/&/g, "&amp;")
                            .replace(/</g, "&lt;")
                            .replace(/>/g, "&gt;")
                            .replace(/"/g, "&quot;")
                            .replace(/'/g, "&#039;");
                    };

                    const parts = [];
                    let lastIndex = 0;
                    const sourceRegex = /<source (\d+)>([\s\S]*?)<\/source \1>/gi;
                    let match;
                    
                    while ((match = sourceRegex.exec(trial.final_answer_instruction)) !== null) {
                        // Text before match
                        const textBefore = trial.final_answer_instruction.substring(lastIndex, match.index);
                        if (textBefore) {
                            parts.push(escapeHtml(textBefore).replace(/\n/g, '<br>'));
                        }
                        
                        // Process match
                        const id = match[1];
                        let content = match[2].trim();
                        // Extract title
                        const firstLineEnd = content.indexOf('\n');
                        let title = 'Source ' + id;
                        let body = content;
                        
                        if (firstLineEnd > 0) {
                            title = content.substring(0, firstLineEnd).trim();
                            body = content.substring(firstLineEnd + 1).trim();
                        }
                        
                        const collapseId = `source-collapse-${trial.id}-${id}`;
                        // We escape the title and body for display inside the widget
                        const safeTitle = escapeHtml(title);
                        const safeBody = escapeHtml(body);

                        const widget = `
                            <div class="card my-2 border-secondary border-opacity-25 text-start">
                                <div class="card-header bg-light py-1 px-2 d-flex justify-content-between align-items-center">
                                    <span class="small fw-bold text-secondary text-truncate" style="max-width: 80%;" title="${safeTitle}">
                                        <span class="badge bg-secondary me-2">Source ${id}</span> ${safeTitle}
                                    </span>
                                    <button class="btn btn-sm btn-link text-decoration-none p-0 collapsed text-secondary" type="button" data-bs-toggle="collapse" data-bs-target="#${collapseId}">
                                        <i class="bi bi-chevron-down small"></i>
                                    </button>
                                </div>
                                <div class="collapse" id="${collapseId}">
                                    <div class="card-body p-2 bg-white small font-monospace text-muted" style="white-space: pre-wrap; font-size: 0.75em; max-height: 200px; overflow-y: auto;">${safeBody}</div>
                                </div>
                            </div>
                        `;
                        parts.push(widget);
                        lastIndex = sourceRegex.lastIndex;
                    }
                    
                    // Text after last match
                    const textAfter = trial.final_answer_instruction.substring(lastIndex);
                    if (textAfter) {
                        parts.push(escapeHtml(textAfter).replace(/\n/g, '<br>'));
                    }
                    
                    if (parts.length > 0) {
                         instrContent = parts.join('');
                    } else {
                         // No sources found, just format newlines
                         instrContent = escapeHtml(instrContent).replace(/\n/g, '<br>');
                    }
                    
                    chatContent += createMessageBubble('user', instrContent);
                }
            }

            // 4. Assistant Final Answer (and CoT)
            let answerBody = '';
            
            if (trial.status === 'processing') {
                 answerBody = `<div class="d-flex align-items-center p-2">
                                <span class="spinner-border spinner-border-sm me-3 text-primary" role="status" aria-hidden="true"></span>
                                <span class="fw-bold">Assistant is thinking...</span>
                             </div>`;
            } else if (trial.status === 'error') {
                 answerBody = `<div class="text-danger p-2"><i class="bi bi-exclamation-triangle-fill me-2"></i> <strong>Error:</strong> Failed to process trial.</div>`;
            } else {
                 // Reasoning
                 let reasoningHtml = '';
                 if (trial.full_response && trial.full_response !== trial.answer) {
                    const collapseId = `reasoning-collapse-${trial.id}`;
                    reasoningHtml = `
                        <div class="mb-3 border-bottom pb-2">
                            <button class="btn btn-sm btn-outline-secondary p-1 px-2 collapsed text-secondary d-flex align-items-center fw-bold shadow-sm" type="button" data-bs-toggle="collapse" data-bs-target="#${collapseId}">
                                <i class="bi bi-cpu me-2"></i> Reasoning Trace (CoT)
                                <i class="bi bi-chevron-down ms-auto ms-3 small"></i>
                            </button>
                            <div class="collapse mt-2" id="${collapseId}">
                                <div class="p-3 bg-light rounded small font-monospace text-dark border shadow-inner" style="white-space: pre-wrap; font-size: 0.82em; max-height: 400px; overflow-y: auto; border-left: 3px solid #6c757d !important;">${trial.full_response}</div>
                            </div>
                        </div>
                    `;
                 }
                 
                 answerBody = `
                    <div class="p-1">
                        ${reasoningHtml}
                        <div class="small text-uppercase text-muted mb-2 fw-bold" style="font-size: 0.7rem; letter-spacing: 1px;">Final Answer Submission</div>
                        <div class="fs-6 lh-base" style="color: #212529;">${trial.answer || ''}</div>
                        
                        <!-- DEBUG INFO -->
                        <div class="mt-3 pt-2 border-top">
                            <button class="btn btn-sm btn-link p-0 text-muted small text-decoration-none" type="button" data-bs-toggle="collapse" data-bs-target="#debug-info-${trial.id}">
                                <i class="bi bi-bug me-1"></i> Debug Info
                            </button>
                            <div class="collapse" id="debug-info-${trial.id}">
                                <div class="mt-2 p-2 bg-light border rounded small font-monospace text-muted" style="font-size: 0.7em;">
                                    <div class="mb-2 pb-2 border-bottom">
                                        <strong>Settings:</strong> Allow Reasoning = <span class="${trial.allow_reasoning ? 'text-success' : 'text-danger'}">${trial.allow_reasoning}</span>
                                    </div>

                                    <div class="mb-2 pb-2 border-bottom">
                                        <strong>Step 1: Query Generation</strong><br>
                                        <span class="text-secondary">Instruction:</span>
                                        <pre class="mb-1 bg-white p-1 border" style="white-space: pre-wrap;">${(trial.query_instruction || '').replace(/</g, '&lt;')}</pre>
                                        <span class="text-secondary">Full Response:</span>
                                        <pre class="mb-1 bg-white p-1 border" style="white-space: pre-wrap;">${(trial.query_full_response || '').replace(/</g, '&lt;')}</pre>
                                        <span class="text-secondary">Parsed Query:</span>
                                        <pre class="mb-0 bg-white p-1 border" style="white-space: pre-wrap;">${(trial.search_query || '').replace(/</g, '&lt;')}</pre>
                                    </div>

                                    <div>
                                        <strong>Step 2: Final Answer</strong><br>
                                        <span class="text-secondary">Instruction:</span>
                                        <pre class="mb-1 bg-white p-1 border" style="white-space: pre-wrap;">${(trial.final_answer_instruction || '').replace(/</g, '&lt;')}</pre>
                                        <span class="text-secondary">Full Response:</span>
                                        <pre class="mb-1 bg-white p-1 border" style="white-space: pre-wrap;">${(trial.full_response || '').replace(/</g, '&lt;')}</pre>
                                        <span class="text-secondary">Parsed Answer:</span>
                                        <pre class="mb-0 bg-white p-1 border" style="white-space: pre-wrap;">${(trial.answer || '').replace(/</g, '&lt;')}</pre>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                 `;
            }
            
            chatContent += createMessageBubble('assistant', answerBody, 'p-3', 'bi-chat-quote-fill');

            // 5. Verdict / Feedback
            if (trial.status === 'completed' && trial.feedback) {
                const isCorrect = trial.is_correct;
                const alertClass = isCorrect ? 'alert-success' : 'alert-danger';
                const icon = isCorrect ? 'bi-check-circle-fill' : 'bi-x-circle-fill';
                
                chatContent += `
                    <div class="d-flex justify-content-center mb-3">
                        <div class="alert ${alertClass} border-0 py-2 px-3 d-flex align-items-center shadow-sm small">
                            <i class="bi ${icon} me-2"></i>
                            <strong>Verdict: ${trial.feedback}</strong>
                        </div>
                    </div>
                `;
            }
            
            // Header for the Trial Card (Turn #N)
            let statusBadge = '';
            if (isCompleted || (trialCount >= maxRetries) || trial.is_correct === true) {
                if (trial.is_correct) {
                    statusBadge = '<span class="badge bg-success rounded-pill shadow-sm"><i class="bi bi-check-lg me-1"></i>Correct</span>';
                } else if (trial.is_correct === false) {
                     statusBadge = '<span class="badge bg-danger rounded-pill shadow-sm"><i class="bi bi-x-lg me-1"></i>Incorrect</span>';
                }
            }
            
            // Removed Prompt Button

            trialDiv.innerHTML = `
                <div class="card border-0 shadow-sm overflow-hidden mb-3">
                    <div class="card-header bg-white border-bottom py-2 d-flex justify-content-between align-items-center">
                        <div class="d-flex align-items-center">
                            <h6 class="mb-0 fw-bold text-secondary text-uppercase small" style="letter-spacing: 1px;">
                                <i class="bi bi-arrow-return-right me-2"></i>Turn #${trial.trial_number}
                            </h6>
                        </div>
                        <div>${statusBadge}</div>
                    </div>
                    <div class="card-body bg-light bg-opacity-10 p-3">
                        ${chatContent}
                    </div>
                </div>
            `;

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
