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
                <div class="small text-dark fw-bold mt-1 processing-question-text">
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

        // Cell 5: Status Badge (LLM & Rule)
        const td5 = document.createElement('td');
        td5.className = 'px-4 text-center';
        
        const llmBadge = document.createElement('div');
        llmBadge.className = 'mb-1';
        if (result.correct === true) {
            llmBadge.appendChild(this.createBadge('LLM: Correct', true));
        } else if (result.correct === false) {
            llmBadge.appendChild(this.createBadge('LLM: Incorrect', false));
        } else {
            const span = document.createElement('span');
            span.className = 'badge bg-warning text-dark';
            span.textContent = 'LLM: Error';
            llmBadge.appendChild(span);
        }
        td5.appendChild(llmBadge);

        if (result.is_correct_rule !== undefined && result.is_correct_rule !== null) {
            const ruleBadge = document.createElement('div');
            ruleBadge.appendChild(this.createBadge(result.is_correct_rule ? 'Rule: Correct' : 'Rule: Incorrect', result.is_correct_rule));
            td5.appendChild(ruleBadge);
        }
        
        row.appendChild(td5);

        // Cell 6: Trials
        const td6 = document.createElement('td');
        td6.className = 'px-4 text-center';
        td6.textContent = result.trials;
        row.appendChild(td6);
        
        return row;
    },

    createMessageBubble: function(role, content, extraClass = '', iconClass = '') {
        const isUser = role === 'user';
        const isSystem = role === 'system';
        
        const alignment = isUser ? 'justify-content-end' : 'justify-content-start';
        
        let icon = iconClass;
        if (!icon) {
            if (isUser) icon = 'bi-person-fill';
            else if (isSystem) icon = 'bi-gear-wide-connected';
            else icon = 'bi-robot';
        }

        let bubbleClass = 'p-3 rounded-4 shadow-sm position-relative bg-white border';
        let textClass = 'text-dark';
        let borderAccent = '';
        
        if (isUser) {
            borderAccent = 'border-right: 4px solid #0d6efd;'; 
        } else if (isSystem) {
            bubbleClass = 'p-3 rounded-4 shadow-sm position-relative bg-light border';
            textClass = 'text-muted small';
        } else {
            borderAccent = 'border-left: 4px solid #6c757d;'; 
        }

        const avatarColor = isUser ? '#f0f7ff' : (isSystem ? '#f8f9fa' : '#ffffff');
        const avatarIconColor = isUser ? 'text-primary' : 'text-secondary';
        const avatarBorder = '1px solid #dee2e6';

        const avatar = `
            <div class="flex-shrink-0 ${isUser ? 'ms-3' : 'me-3'} d-none d-md-block avatar-container">
                <div class="rounded-circle d-flex align-items-center justify-content-center shadow-sm" 
                        style="width: 36px; height: 36px; background-color: ${avatarColor}; border: ${avatarBorder};">
                    <i class="bi ${icon} ${avatarIconColor}"></i>
                </div>
            </div>
        `;                
        const abbreviateText = (text, maxLength = 800) => {
            if (!text || text.length <= maxLength) return text;
            const id = 'collapse-' + Math.random().toString(36).substr(2, 9);
            const visiblePart = text.substring(0, maxLength);
            const hiddenPart = text.substring(maxLength);
            return `
                ${visiblePart}<span id="${id}" class="collapse">${hiddenPart}</span>
                <a href="javascript:void(0);" class="text-primary text-decoration-none small ms-1" onclick="
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

        if (!content.includes('<div') && !content.includes('<span') && !content.includes('<p') && !content.includes('<code')) {
                content = content.replace(/</g, '&lt;').replace(/>/g, '&gt;');
                content = abbreviateText(content);
                content = content.replace(/\n/g, '<br>');
        }

        return `
            <div class="d-flex ${alignment} mb-3 message-bubble">
                ${!isUser ? avatar : ''}
                <div class="${bubbleClass} ${extraClass} ${textClass} message-bubble-content" style="${borderAccent}">
                    ${content}
                </div>
                ${isUser ? avatar : ''}
            </div>
        `;
    },

    renderAgentStep: function(step, idx, trialId, finalAnswerText) {
        const role = step.role || 'assistant';
        const type = step.step_type || 'text'; // thought, action, observation, text
        let content = step.content || '';
        const name = step.name || ''; // Tool name often appears here for observations

        // Helper to parse JSON content safely
        const parseContent = (str) => {
            if (typeof str !== 'string') return str;
            try { return JSON.parse(str); } catch (e) { return null; }
        };

        // --- 1. Assistant: Thought ---
        if (type === 'thought') {
            const tId = `thought-${trialId}-${idx}`;
            const thoughtHtml = `
                <div class="mb-2">
                     <button class="btn btn-sm btn-light border d-flex align-items-center fw-bold text-secondary shadow-sm px-3 py-2 rounded-3" type="button" data-bs-toggle="collapse" data-bs-target="#${tId}">
                        <i class="bi bi-lightbulb text-warning me-2"></i>
                        <span>Thinking Process</span>
                        <i class="bi bi-chevron-down ms-3 small"></i>
                     </button>
                     <div class="collapse show mt-2" id="${tId}">
                        <div class="p-3 bg-light border-start border-3 border-warning rounded-3 small text-secondary font-monospace thinking-process-content">${content}</div>
                     </div>
                </div>
            `;
            return this.createMessageBubble('assistant', thoughtHtml, 'bg-transparent border-0 shadow-none p-0', 'bi-robot');
        }

        // --- 2. Assistant: Action (Tool Call) ---
        if (type === 'action') {
            const toolHtml = `
                <div class="d-flex flex-column">
                    <div class="d-flex align-items-center mb-2">
                        <span class="badge bg-primary bg-opacity-10 text-primary border border-primary border-opacity-25 text-uppercase agent-badge-text">
                            <i class="bi bi-tools me-1"></i> Tool Execution
                        </span>
                    </div>
                    <div class="p-3 bg-white border rounded-3 shadow-sm font-monospace small text-dark tool-execution-content">${content}</div>
                </div>
            `;
            return this.createMessageBubble('assistant', toolHtml, '', 'bi-gear');
        }

        // --- 3. Assistant: Observation (Tool Output) ---
        if (type === 'observation') {
            let parsedData = parseContent(content);
            let isSearch = false;
            let isFinalAnswer = false;
            let displayContent = content;
            
            // Heuristic to detect search results
            if (parsedData && Array.isArray(parsedData) && parsedData.length > 0) {
                if (parsedData[0].title && (parsedData[0].link || parsedData[0].url)) {
                    isSearch = true;
                }
            }
            if (name === 'web_search_tool') isSearch = true;

            // Handle RAG simulated search results (string starting with "Search Results:")
            if (typeof content === 'string' && content.startsWith('Search Results:')) {
                isSearch = true;
                displayContent = content.replace('Search Results:', '').trim();
                // For simulated results, we don't have parsed JSON data easily
                // but we can still render the text block.
            }
            
            // Check for Final Answer
            if (parsedData && parsedData.name === 'answer_question') {
                isFinalAnswer = true;
            } else if (typeof content === 'string' && content.includes('Answer submitted successfully')) {
                isFinalAnswer = true;
            }

            if (isSearch) {
                let resultsHtml = '';
                if (parsedData && Array.isArray(parsedData)) {
                    // Render Search Results (Integrated into Observation)
                    const resultsCount = parsedData.length;
                    const resultsJson = encodeURIComponent(JSON.stringify(parsedData));
                    
                    resultsHtml = `
                        <div class="d-flex align-items-center justify-content-between p-2 bg-white border rounded mb-2">
                            <div class="d-flex align-items-center">
                                <div class="rounded-circle bg-success bg-opacity-10 p-2 me-3">
                                    <i class="bi bi-globe text-success"></i>
                                </div>
                                <div>
                                    <div class="fw-bold text-dark search-results-title">Web Search Results</div>
                                    <div class="small text-muted">${resultsCount} relevant documents found</div>
                                </div>
                            </div>
                            <button class="btn btn-sm btn-outline-success rounded-pill px-3 ms-3 view-search-results-btn" data-results="${resultsJson}" onclick="
                                const data = JSON.parse(decodeURIComponent(this.dataset.results));
                                const container = document.getElementById('modal-generic-content-container'); 
                                if(window.BenchmarkUtils && window.BenchmarkUtils.BenchmarkRenderer) {
                                    window.BenchmarkUtils.BenchmarkRenderer.renderModalSearchResults(data, container);
                                    new bootstrap.Modal(document.getElementById('benchmarkGenericModal')).show();
                                }
                            ">
                                <i class="bi bi-eye me-1"></i> View Detail
                            </button>
                        </div>
                    `;
                } else {
                    // Fallback for string-based search results
                    resultsHtml = `<div class="p-2 bg-white border rounded mb-2 font-monospace small" style="white-space: pre-wrap;">${displayContent}</div>`;
                }
                
                const obsHtml = `
                    <div class="d-flex flex-column">
                         <div class="d-flex align-items-center mb-2">
                            <span class="badge bg-success bg-opacity-10 text-success border border-success border-opacity-25 text-uppercase agent-badge-text">
                                <i class="bi bi-eye me-1"></i> Observation
                            </span>
                        </div>
                        <div class="p-3 bg-light border rounded-3 shadow-sm font-monospace small text-muted">
                             ${resultsHtml}
                             <div class="text-secondary small mt-1"><i>Search completed successfully.</i></div>
                        </div>
                    </div>
                `;
                return this.createMessageBubble('assistant', obsHtml, '', 'bi-eye');
                
            } else if (isFinalAnswer) {
                // Render ONLY Final Answer Bubble for answer_question observation
                let answerBody = `
                   <div class="position-relative">
                       <div class="text-uppercase text-muted fw-bold mb-2 response-label">Response</div>
                       <div class="fs-6 text-dark response-text">${finalAnswerText || ''}</div>
                   </div>
                   `;
                
                return this.createMessageBubble('assistant', answerBody, '', 'bi-chat-left-dots');

            } else {
                // Generic Observation
                const obsHtml = `
                    <div class="d-flex flex-column">
                         <div class="d-flex align-items-center mb-2">
                            <span class="badge bg-success bg-opacity-10 text-success border border-success border-opacity-25 text-uppercase agent-badge-text">
                                <i class="bi bi-eye me-1"></i> Observation
                            </span>
                        </div>
                        <div class="p-3 bg-light border rounded-3 shadow-sm font-monospace small text-muted generic-observation-content">${content}</div>
                    </div>
                `;
                return this.createMessageBubble('assistant', obsHtml, '', 'bi-eye');
            }
        }

        // --- 4. System Prompt ---
        if (role === 'system') {
            const systemHtml = `
                <div class="d-flex align-items-center mb-2 pb-2 border-bottom border-secondary border-opacity-25">
                    <i class="bi bi-cpu-fill text-secondary me-2"></i> 
                    <span class="text-uppercase fw-bold text-secondary small system-config-header">System Configuration</span>
                </div>
                <div class="font-monospace text-muted small system-config-content">${content}</div>
            `;
            return this.createMessageBubble('system', systemHtml, 'bg-light border-secondary border-opacity-10 shadow-none');
        }

        // --- 5. User Input ---
        if (role === 'user') {
            return this.createMessageBubble('user', content);
        }

        // --- 6. Fallback (Text / Assistant Message) ---
        return this.createMessageBubble('assistant', content, '', 'bi-chat-left-dots');
    },

    renderTrial: function(trial, isCompleted, trialCount, maxRetries, questionText, pipelineType = 'vanilla_llm_multi_turn') {
        const trialDiv = document.createElement('div');
        trialDiv.className = 'trial-container position-relative'; 
        trialDiv.id = `trial-${trial.id}`;

        let chatContent = '';
        
        let trace = trial.trace || [];
        if (typeof trace === 'string') {
            try { trace = JSON.parse(trace); } catch(e) { trace = []; }
        }
        
        if (trace.length === 0 && trial.full_response && pipelineType.includes('agent')) {
            try { trace = JSON.parse(trial.full_response); } catch(e) {}
        }

        let indicatorHtml = '';
        if (trial.status === 'processing') {
             const config = (window.BenchmarkUtils && window.BenchmarkUtils.MultiTurnPage && window.BenchmarkUtils.MultiTurnPage.PIPELINE_CONFIGS) 
                ? window.BenchmarkUtils.MultiTurnPage.PIPELINE_CONFIGS[pipelineType] || {}
                : {};
             const text = config.loadingText || 'Thinking...';
             const icon = config.icon || 'bi-robot';
             indicatorHtml = this.createMessageBubble('assistant', `<div class="d-flex align-items-center trial-processing-indicator"><span class="spinner-border spinner-border-sm text-primary me-2"></span>${text}</div>`, '', icon);
             
             // Trigger Polling automatically if supported
             if (window.BenchmarkUtils && window.BenchmarkUtils.MultiTurnPage && window.BenchmarkUtils.MultiTurnPage.startPolling) {
                setTimeout(() => window.BenchmarkUtils.MultiTurnPage.startPolling(trial.id, pipelineType), 100);
             }
        }

        if (trace && trace.length > 0) {
            trace.forEach((step, idx) => {
                chatContent += this.renderAgentStep(step, idx, trial.id, trial.answer);
            });
            chatContent += indicatorHtml;
        } else {
            if (indicatorHtml) {
                chatContent += indicatorHtml;
            } else {
                chatContent += this.createMessageBubble('system', 'No execution trace available for this trial.', 'bg-light border-secondary border-opacity-10 shadow-none');
            }
        }

        if (trial.status === 'completed' && (trial.feedback || trial.is_correct_rule !== undefined)) {
            const verdictHtml = this.renderTrialVerdict(trial);
            if (verdictHtml) chatContent += verdictHtml.outerHTML;
        }
        
        const turnSeparator = trial.trial_number > 1 ? `
            <div class="d-flex align-items-center my-5 turn-divider">
                <div class="flex-grow-1 border-top turn-divider-line"></div>
                <div class="mx-4 text-uppercase text-muted fw-bold small turn-divider-text">End of Turn ${trial.trial_number - 1}</div>
                <div class="flex-grow-1 border-top turn-divider-line"></div>
            </div>
        ` : '';

        trialDiv.innerHTML = `
            ${turnSeparator}
            <div class="trial-wrapper position-relative pb-2">
                <div class="d-flex align-items-center justify-content-center mb-4">
                    <div class="bg-primary bg-opacity-10 text-primary border border-primary border-opacity-25 rounded-pill px-4 py-1 small fw-bold turn-label">TURN ${trial.trial_number}</div>
                </div>
                ${chatContent}
            </div>
        `;
        
        return trialDiv;
    },       
     
    renderTrialVerdict: function(trial) {
        const isCorrectLLM = trial.is_correct_llm !== undefined ? trial.is_correct_llm : trial.is_correct;
        const isCorrectRule = trial.is_correct_rule;
        
        if (isCorrectLLM === undefined && isCorrectRule === undefined) return null;

        const container = document.createElement('div');
        container.className = 'd-flex flex-row justify-content-center flex-wrap gap-3 mt-2 mb-2 fade-in trial-verdict-container';
        
        // LLM Verdict
        if (isCorrectLLM !== undefined && isCorrectLLM !== null) {
            const llmColor = isCorrectLLM ? 'success' : 'danger';
            const llmIcon = isCorrectLLM ? 'bi-check-circle-fill' : 'bi-x-circle-fill';
            container.innerHTML += `
                <div class="card border-0 shadow-sm rounded-pill px-2" style="background-color: #f8f9fa;">
                    <div class="card-body py-2 px-4 d-flex align-items-center">
                        <i class="bi ${llmIcon} text-${llmColor} fs-5 me-2"></i>
                        <div class="fw-bold text-${llmColor} text-uppercase small verdict-text">Verdict (LLM): ${isCorrectLLM ? 'Correct' : 'Incorrect'}</div>
                    </div>
                </div>`;
        }

        // Rule Verdict
        if (isCorrectRule !== undefined && isCorrectRule !== null) {
            const ruleColor = isCorrectRule ? 'success' : 'danger';
            const ruleIcon = isCorrectRule ? 'bi-check-circle-fill' : 'bi-x-circle-fill';
            container.innerHTML += `
                <div class="card border-0 shadow-sm rounded-pill px-2" style="background-color: #f8f9fa;">
                    <div class="card-body py-2 px-4 d-flex align-items-center">
                        <i class="bi ${ruleIcon} text-${ruleColor} fs-5 me-2"></i>
                        <div class="fw-bold text-${ruleColor} text-uppercase small verdict-text">Verdict (Rule): ${isCorrectRule ? 'Correct' : 'Incorrect'}</div>
                    </div>
                </div>`;
        }
        
        return container;
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
            divLabel.className = 'text-muted text-uppercase config-detail-label';
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
