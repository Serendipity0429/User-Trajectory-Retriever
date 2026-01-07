window.BenchmarkUtils.BenchmarkRenderer = {
    ...BenchmarkComponents,
    
    renderProcessingRow: function(item, resultsBody, colSpan = 7) {
        const rowId = `processing-row`; 
        
        // Remove existing if any
        const existing = document.getElementById(rowId);
        if (existing) existing.remove();

        const tr = BenchmarkUtils.renderTemplate('tpl-processing-row', {
            'root': { attrs: { id: rowId } },
            '.processing-col': { attrs: { colspan: colSpan } },
            '.processing-question-text': { text: item.question || 'Unknown' }
        });
        
        resultsBody.insertAdjacentElement('afterbegin', tr); 
        return tr;
    },
    
    // Helper to render ground truths list with expansion
    renderGroundTruthsList: function(groundTruthsArray, displayLimit = 3) {
        const ul = document.createElement('ul');
        ul.className = 'list-unstyled mb-0';

        const visibleItems = groundTruthsArray.slice(0, displayLimit);
        const hiddenItems = groundTruthsArray.slice(displayLimit);

        visibleItems.forEach(gt => {
            const li = BenchmarkUtils.renderTemplate('tpl-ground-truth-item', {
                '.gt-text': { text: gt }
            });
            ul.appendChild(li);
        });

        if (hiddenItems.length > 0) {
            const hiddenContainer = document.createElement('div');
            hiddenContainer.style.display = 'none';
            hiddenItems.forEach(gt => {
                const li = BenchmarkUtils.renderTemplate('tpl-ground-truth-item', {
                    '.gt-text': { text: gt }
                });
                hiddenContainer.appendChild(li);
            });
            ul.appendChild(hiddenContainer);

            const toggleLi = BenchmarkUtils.renderTemplate('tpl-ground-truth-toggle', {
                '.show-more-btn': {
                    text: `... Show ${hiddenItems.length} more`,
                    onclick: (e) => {
                        e.stopPropagation();
                        hiddenContainer.style.display = 'block';
                        toggleLi.querySelector('.show-more-btn').style.display = 'none';
                        toggleLi.querySelector('.show-less-btn').style.display = 'inline-block';
                    }
                },
                '.show-less-btn': {
                    onclick: (e) => {
                        e.stopPropagation();
                        hiddenContainer.style.display = 'none';
                        toggleLi.querySelector('.show-more-btn').style.display = 'inline-block';
                        toggleLi.querySelector('.show-less-btn').style.display = 'none';
                    }
                }
            });
            ul.appendChild(toggleLi);
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
        resultsListElement.innerHTML = ''; 
        if (results && results.length > 0) {
            results.forEach((res, index) => {
                const item = BenchmarkUtils.renderTemplate('tpl-search-result-item', {
                    '.search-result-link': { href: res.link || '#' },
                    '.search-result-title': { text: `${index + 1}. ${res.title || 'No Title'}` },
                    '.search-result-snippet': { text: res.snippet || 'No snippet available.' },
                    '.search-result-url': { text: res.link || '' }
                });
                resultsListElement.appendChild(item);
            });
        } else {
            this.renderNoSearchResults(resultsListElement);
        }
    },

    renderNoSearchResults: function(resultsListElement) {
        resultsListElement.innerHTML = '';
        const alertDiv = document.createElement('div');
        alertDiv.className = 'alert alert-info';
        alertDiv.textContent = 'No results found.';
        resultsListElement.appendChild(alertDiv);
    },

    renderSearchError: function(resultsListElement, errorMessage) {
        resultsListElement.innerHTML = '';
        const alertDiv = document.createElement('div');
        alertDiv.className = 'alert alert-danger';
        alertDiv.textContent = errorMessage;
        resultsListElement.appendChild(alertDiv);
    },

    renderModalSearchResults: function(results, container, modalId = 'benchmarkGenericModal') {
        const modalTitle = document.getElementById(modalId + 'Label');
        if (modalTitle) modalTitle.textContent = 'Search Results';
        container.innerHTML = ''; 

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
                
                // Base setup for the item
                const itemData = {
                    '.result-idx': { text: idx + 1 },
                    '.result-link': { href: linkUrl, text: linkTitle },
                    '.domain-badge': { text: domain },
                    '.result-snippet': { text: snippet },
                    '.url-content': { text: linkUrl }
                };
                
                const itemElement = BenchmarkUtils.renderTemplate('tpl-modal-search-result-item', itemData);

                // Handle Full Content Collapse
                if (fullContent && fullContent !== snippet) {
                    const collapseId = `content-collapse-${idx}-${Math.random().toString(36).substr(2, 9)}`;
                    const contentContainer = itemElement.querySelector('.content-container');
                    const toggleBtn = itemElement.querySelector('.toggle-content-btn');
                    const collapseDiv = itemElement.querySelector('.content-collapse');
                    const contentBody = itemElement.querySelector('.full-content-body');
                    const btnText = itemElement.querySelector('.btn-text');
                    const icon = itemElement.querySelector('.icon-chevron');

                    if (contentContainer) contentContainer.style.display = 'block';
                    if (toggleBtn) toggleBtn.setAttribute('data-bs-target', `#${collapseId}`);
                    if (collapseDiv) collapseDiv.id = collapseId;
                    if (contentBody) contentBody.textContent = fullContent;

                    if (toggleBtn) {
                        toggleBtn.addEventListener('click', function() {
                            const isExpanded = this.getAttribute('aria-expanded') === 'true';
                            // Wait for BS collapse event or just toggle immediately for text
                             setTimeout(() => {
                                 const actuallyExpanded = collapseDiv.classList.contains('show');
                                 if (btnText) btnText.textContent = actuallyExpanded ? 'Hide Full Content' : 'Show Full Content';
                                 if (icon) icon.className = actuallyExpanded ? 'bi bi-chevron-up ms-auto ps-3 icon-chevron' : 'bi bi-chevron-down ms-auto ps-3 icon-chevron';
                             }, 350); // Slight delay to sync with BS animation
                        });
                    }
                }

                container.appendChild(itemElement);
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

        const modal = bootstrap.Modal.getOrCreateInstance(document.getElementById(modalId));
        modal.show();
    },

    renderMultiTurnResultRow: function(result, index, loadSessionCallback) {
        const tr = BenchmarkUtils.renderTemplate('tpl-multiturn-result-row', {
            '.result-row': {
                onclick: loadSessionCallback ? () => loadSessionCallback(result.session_id) : null
            },
            '.idx-col': { text: index + 1 },
            '.question-col': { text: result.question },
            '.answer-col': { html: `<em>“${result.final_answer || 'N/A'}”</em>` },
            '.trials-col': { text: result.trials }
        });

        // Cell 4: Ground Truths
        tr.querySelector('.gt-col').appendChild(this.renderGroundTruthsList(result.ground_truths));

        // Cell 5: Status Badge
        const statusCol = tr.querySelector('.status-col');
        const llmVerdictDiv = statusCol.querySelector('.llm-verdict');
        const ruleVerdictDiv = statusCol.querySelector('.rule-verdict');

        if (result.correct === true) {
            llmVerdictDiv.appendChild(this.createBadge('LLM: Correct', true));
        } else if (result.correct === false) {
            llmVerdictDiv.appendChild(this.createBadge('LLM: Incorrect', false));
        } else {
            const span = document.createElement('span');
            span.className = 'badge bg-warning text-dark';
            span.textContent = 'LLM: Error';
            llmVerdictDiv.appendChild(span);
        }

        if (result.is_correct_rule !== undefined && result.is_correct_rule !== null) {
            ruleVerdictDiv.appendChild(this.createBadge(result.is_correct_rule ? 'Rule: Correct' : 'Rule: Incorrect', result.is_correct_rule));
        }
        
        return tr;
    },

    createMessageBubble: function(role, content, extraClass = '', iconClass = '') {
        const isUser = role === 'user';
        const isSystem = role === 'system';
        const isAssistant = !isUser && !isSystem;
        
        const alignment = isUser ? 'justify-content-end' : 'justify-content-start';
        
        let icon = iconClass;
        if (!icon) {
            if (isUser) icon = 'bi-person-fill';
            else if (isSystem) icon = 'bi-gear-wide-connected';
            else icon = 'bi-robot';
        }

        let borderAccent = '';
        let bubbleClass = 'bg-white';
        let textClass = 'text-dark';

        if (isUser) {
            borderAccent = '4px solid #0d6efd';
        } else if (isSystem) {
            bubbleClass = 'bg-light';
            textClass = 'text-muted small';
            borderAccent = 'none';
        } else {
            borderAccent = '4px solid #6c757d';
        }

        // Logic to strip container styles if transparent (for tool outputs)
        let removeClasses = '';
        if (extraClass && extraClass.includes('bg-transparent')) {
            removeClasses = 'bg-white shadow-sm border p-3';
            // Also ensure we don't re-add bg-white from bubbleClass
            if (bubbleClass === 'bg-white') bubbleClass = '';
        }

        const avatarColor = isUser ? '#f0f7ff' : (isSystem ? '#f8f9fa' : '#ffffff');
        const avatarIconColor = isUser ? 'text-primary' : 'text-secondary';
        const avatarBorder = '1px solid #dee2e6';

        const bubble = BenchmarkUtils.renderTemplate('tpl-message-bubble', {
            'root': { addClass: `${alignment}` },
            '.message-bubble-content': { 
                html: content,
                addClass: `${bubbleClass} ${textClass} ${extraClass}`,
                removeClass: removeClasses,
                style: { borderLeft: !isUser && !isSystem ? borderAccent : 'none', borderRight: isUser ? borderAccent : 'none' }
            },
            // Left avatar for Assistant/System
            '.avatar-left': { 
                style: { backgroundColor: avatarColor },
                addClass: isUser ? 'd-none' : 'd-md-block', 
                removeClass: isUser ? 'd-md-block' : 'd-none'
            },
            '.avatar-left .avatar-circle': {
                style: { backgroundColor: avatarColor, border: avatarBorder }
            },
            '.avatar-left .avatar-icon': {
                addClass: `${icon} ${avatarIconColor}`
            },
            // Right avatar for User
            '.avatar-right': { 
                style: { backgroundColor: avatarColor },
                addClass: isUser ? 'd-md-block' : 'd-none',
                removeClass: isUser ? 'd-none' : 'd-md-block'
            },
            '.avatar-right .avatar-circle': {
                style: { backgroundColor: avatarColor, border: avatarBorder }
            },
            '.avatar-right .avatar-icon': {
                addClass: `${icon} ${avatarIconColor}`
            }
        });

        return bubble;
    },

    renderAgentStep: function(step, idx, trialId, finalAnswerText) {
        const role = step.role || 'assistant';
        const type = step.step_type || 'text'; // thought, action, observation, text
        let content = step.content || '';
        const name = step.name || ''; 

        const parseContent = (str) => {
            if (typeof str !== 'string') return str;
            try { return JSON.parse(str); } catch (e) { return null; }
        };

        // --- 1. Assistant: Thought ---
        if (type === 'thought') {
            const tId = `thought-${trialId}-${idx}`;
            const thoughtElement = BenchmarkUtils.renderTemplate('tpl-agent-thought', {
                '.collapse-btn': { attrs: { 'data-bs-target': `#${tId}` } },
                '.collapse-target': { attrs: { id: tId } },
                '.thinking-content': { text: content }
            });
            return this.createMessageBubble('assistant', thoughtElement.outerHTML, 'bg-transparent border-0 shadow-none p-0', 'bi-robot');
        }

        // --- 2. Assistant: Action (Tool Call) ---
        if (type === 'action') {
            let title = 'Tool Execution';
            let icon = 'bi-tools';
            let badgeClass = 'bg-primary bg-opacity-10 text-primary border border-primary border-opacity-25';
            
            if (typeof content === 'string' && content.trim().startsWith('Search Query:')) {
                title = 'Search Query';
                icon = 'bi-search';
                badgeClass = 'bg-info bg-opacity-10 text-info border-info border-opacity-25';
                
                const actionElement = BenchmarkUtils.renderTemplate('tpl-agent-action', {
                    '.agent-badge-text': { addClass: badgeClass },
                    '.badge-icon': { addClass: icon },
                    '.badge-label': { text: title },
                    '.tool-content': { text: content }
                });
                return this.createMessageBubble('assistant', actionElement.outerHTML, 'bg-transparent border-0 shadow-none p-0', 'bi-gear');
            }

            // General Tool Parsing
            let toolName = null;
            let toolInput = null;
            try {
                const toolData = (typeof content === 'string') ? JSON.parse(content) : content;
                if (toolData && toolData.name && toolData.input) {
                    toolName = toolData.name;
                    toolInput = JSON.stringify(toolData.input, null, 2);
                }
            } catch(e) {}

            if (toolName) {
                const innerHtml = `
                    <div class="card border border-light shadow-sm">
                         <div class="card-header bg-light bg-gradient border-bottom py-2 px-3 d-flex align-items-center">
                            <i class="bi bi-terminal-fill text-secondary me-2"></i>
                            <span class="fw-bold font-monospace text-primary">${toolName}</span>
                         </div>
                         <div class="card-body p-2 bg-white">
                            <div class="text-muted small text-uppercase fw-bold mb-2" style="font-size: 0.7rem; letter-spacing: 0.5px;">Input Parameters</div>
                            <div class="p-2 bg-light border rounded font-monospace small text-dark" style="white-space: pre-wrap;">${toolInput}</div>
                         </div>
                    </div>
                `;
                const actionElement = BenchmarkUtils.renderTemplate('tpl-agent-action', {
                    '.agent-badge-text': { addClass: badgeClass },
                    '.badge-icon': { addClass: icon },
                    '.badge-label': { text: title },
                    '.tool-content': { 
                        html: innerHtml, 
                        removeClass: 'p-3 bg-white border rounded-3 shadow-sm font-monospace small text-dark',
                        style: { 'white-space': 'normal' } 
                    }
                });
                return this.createMessageBubble('assistant', actionElement.outerHTML, 'bg-transparent border-0 shadow-none p-0', 'bi-gear');
            } else {
                 const actionElement = BenchmarkUtils.renderTemplate('tpl-agent-action', {
                    '.agent-badge-text': { addClass: badgeClass },
                    '.badge-icon': { addClass: icon },
                    '.badge-label': { text: title },
                    '.tool-content': { text: content }
                });
                return this.createMessageBubble('assistant', actionElement.outerHTML, 'bg-transparent border-0 shadow-none p-0', 'bi-gear');
            }
        }

        // --- 3. Assistant: Observation (Tool Output) ---
        if (type === 'observation') {
            let parsedData = parseContent(content);
            let isSearch = false;
            let isFinalAnswer = false;
            let displayContent = content;
            
            if (name === 'web_search_tool' || (parsedData && Array.isArray(parsedData) && parsedData.length > 0 && parsedData[0].title)) {
                isSearch = true;
            }

            if (typeof content === 'string' && content.startsWith('Search Results:')) {
                isSearch = true;
                displayContent = content.replace('Search Results:', '').trim();
                try {
                    const jsonMatch = displayContent.match(/<!-- JSON_DATA_FOR_UI: (.*?) -->/s);
                    if (jsonMatch && jsonMatch[1]) parsedData = JSON.parse(jsonMatch[1]);
                    else {
                        const extractedJson = JSON.parse(displayContent);
                        if (Array.isArray(extractedJson)) parsedData = extractedJson;
                    }
                } catch(e) {
                    const sourceRegex = /<source (\d+)>\s*(.*?)\n([\s\S]*?)<\/source \1>/g;
                    let match;
                    const extractedResults = [];
                    while ((match = sourceRegex.exec(displayContent)) !== null) {
                        extractedResults.push({
                            title: match[2].trim(),
                            snippet: match[3].trim().substring(0, 300) + (match[3].length > 300 ? '...' : ''),
                            content: match[3].trim()
                        });
                    }
                    if (extractedResults.length > 0) parsedData = extractedResults;
                }
            }
            
            if ((parsedData && parsedData.name === 'answer_question') || (typeof content === 'string' && content.includes('Answer submitted successfully'))) {
                isFinalAnswer = true;
            }

            if (isSearch) {
                if (parsedData && Array.isArray(parsedData)) {
                    const resultsJson = encodeURIComponent(JSON.stringify(parsedData));
                    const obsSearch = BenchmarkUtils.renderTemplate('tpl-agent-obs-search', {
                        '.search-count': { text: `${parsedData.length} relevant documents found` },
                        '.view-details-btn': {
                            attrs: { 'data-results': resultsJson },
                            onclick: function() {
                                const data = JSON.parse(decodeURIComponent(this.dataset.results));
                                const container = document.getElementById('modal-generic-content-container'); 
                                window.BenchmarkUtils.BenchmarkRenderer.renderModalSearchResults(data, container);
                                bootstrap.Modal.getOrCreateInstance(document.getElementById('benchmarkGenericModal')).show();
                            }
                        }
                    });
                    return this.createMessageBubble('assistant', obsSearch.outerHTML, 'bg-transparent border-0 shadow-none p-0', 'bi-eye');
                } else {
                    const obsGeneric = BenchmarkUtils.renderTemplate('tpl-agent-obs-generic', {
                         '.obs-content': { text: displayContent }
                    });
                    return this.createMessageBubble('assistant', obsGeneric.outerHTML, 'bg-transparent border-0 shadow-none p-0', 'bi-eye');
                }
            } else if (isFinalAnswer) {
                const finalAnswer = BenchmarkUtils.renderTemplate('tpl-agent-final-answer', {
                    '.response-text': { text: finalAnswerText || '' }
                });
                return this.createMessageBubble('assistant', finalAnswer.outerHTML, '', 'bi-chat-left-dots');
            } else {
                const obsGeneric = BenchmarkUtils.renderTemplate('tpl-agent-obs-generic', {
                    '.obs-content': { text: content }
                });
                return this.createMessageBubble('assistant', obsGeneric.outerHTML, 'bg-transparent border-0 shadow-none p-0', 'bi-eye');
            }
        }

        // --- 4. System Prompt ---
        if (role === 'system') {
            const systemPrompt = BenchmarkUtils.renderTemplate('tpl-system-prompt', {
                '.system-config-content': { text: content }
            });
            return this.createMessageBubble('system', systemPrompt.outerHTML, 'bg-light border-secondary border-opacity-10 shadow-none');
        }

        // --- 5. User Input ---
        if (role === 'user') {
            if (typeof content === 'string' && content.includes('<source')) {
                const sourceRegex = /<source (\d+)>\s*(.*?)\n([\s\S]*?)<\/source \1>/g;
                let match;
                const extractedResults = [];
                while ((match = sourceRegex.exec(content)) !== null) {
                    extractedResults.push({
                        title: match[2].trim(),
                        snippet: match[3].trim().substring(0, 300) + (match[3].length > 300 ? '...' : ''),
                        content: match[3].trim()
                    });
                }

                if (extractedResults.length > 0) {
                    const resultsJson = encodeURIComponent(JSON.stringify(extractedResults));
                    const injection = BenchmarkUtils.renderTemplate('tpl-user-search-injection', {
                        '.docs-count-text': { text: `${extractedResults.length} documents provided in context` },
                        '.view-search-results-btn': {
                            attrs: { 'data-results': resultsJson },
                            onclick: function() {
                                const data = JSON.parse(decodeURIComponent(this.dataset.results));
                                const container = document.getElementById('modal-generic-content-container'); 
                                window.BenchmarkUtils.BenchmarkRenderer.renderModalSearchResults(data, container);
                                bootstrap.Modal.getOrCreateInstance(document.getElementById('benchmarkGenericModal')).show();
                            }
                        }
                    });
                    
                    let displayContent = content.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
                    const placeholder = "<!--___RESULTS_CARD_PLACEHOLDER___-->";
                    const escapedSourceBlockRegex = /(?:&lt;source \d+&gt;[\s\S]*?&lt;\/source \d+&gt;\s*)+/;
                    const blockMatch = displayContent.match(escapedSourceBlockRegex);
                    
                    if (blockMatch) {
                        const rawSourceBlock = blockMatch[0];
                        displayContent = displayContent.replace(escapedSourceBlockRegex, placeholder);
                        displayContent = displayContent.replace(/\n/g, '<br>');
                        
                        const collapseId = `raw-source-${extractedResults.length}-${Math.random().toString(36).substr(2, 5)}`;
                        injection.querySelector('.raw-source-toggle').setAttribute('data-bs-target', `#${collapseId}`);
                        injection.querySelector('.raw-source-collapse').id = collapseId;
                        injection.querySelector('.raw-source-pre').textContent = rawSourceBlock;

                        displayContent = displayContent.replace(placeholder, injection.outerHTML);
                        return this.createMessageBubble('user', displayContent);
                    }
                }
            }
            return this.createMessageBubble('user', content.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/\n/g, '<br>'));
        }

        // --- 6. Fallback ---
        if (typeof content === 'string') {
             content = content.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/\n/g, '<br>');
        }
        return this.createMessageBubble('assistant', content, '', 'bi-chat-left-dots');
    },

    renderTrial: function(trial, isCompleted, trialCount, maxRetries, questionText, pipelineType = 'vanilla_llm') {
        const trialDiv = BenchmarkUtils.renderTemplate('tpl-trial-wrapper', {
            'root': { attrs: { id: `trial-${trial.id}` } },
            '.turn-label': { text: `TURN ${trial.trial_number}` }
        });

        const wrapper = trialDiv.querySelector('.trial-wrapper');
        
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
             
             if (window.BenchmarkUtils && window.BenchmarkUtils.MultiTurnPage && window.BenchmarkUtils.MultiTurnPage.startPolling) {
                setTimeout(() => window.BenchmarkUtils.MultiTurnPage.startPolling(trial.id, pipelineType), 100);
             }
        }

        if (trace && trace.length > 0) {
            trace.forEach((step, idx) => {
                const stepEl = this.renderAgentStep(step, idx, trial.id, trial.answer);
                if (typeof stepEl === 'string') {
                    wrapper.insertAdjacentHTML('beforeend', stepEl);
                } else {
                    wrapper.appendChild(stepEl);
                }
            });
            if (indicatorHtml) {
                if (typeof indicatorHtml === 'string') {
                    wrapper.insertAdjacentHTML('beforeend', indicatorHtml);
                } else {
                    wrapper.appendChild(indicatorHtml);
                }
            }
        } else {
            if (indicatorHtml) {
                if (typeof indicatorHtml === 'string') {
                    wrapper.insertAdjacentHTML('beforeend', indicatorHtml);
                } else {
                    wrapper.appendChild(indicatorHtml);
                }
            } else {
                wrapper.appendChild(this.createMessageBubble('system', 'No execution trace available for this trial.', 'bg-light border-secondary border-opacity-10 shadow-none'));
            }
        }

        if (trial.status === 'completed' && (trial.feedback || trial.is_correct_rule !== undefined)) {
            const verdictHtml = this.renderTrialVerdict(trial);
            if (verdictHtml) wrapper.appendChild(verdictHtml);
        }
        
        const container = document.createElement('div');
        container.appendChild(trialDiv);

        if (trial.trial_number < trialCount) {
            const divider = BenchmarkUtils.renderTemplate('tpl-turn-divider', {
                '.turn-divider-text': { text: `End of Turn ${trial.trial_number}` }
            });
            container.appendChild(divider);
        }
        
        return container.children.length > 1 ? container : trialDiv;
    },       
     
    renderTrialVerdict: function(trial) {
        const isCorrectLLM = trial.is_correct_llm !== undefined ? trial.is_correct_llm : trial.is_correct;
        const isCorrectRule = trial.is_correct_rule;
        
        if (isCorrectLLM === undefined && isCorrectRule === undefined) return null;

        const container = BenchmarkUtils.renderTemplate('tpl-trial-verdict-container');
        
        // LLM Verdict
        if (isCorrectLLM !== undefined && isCorrectLLM !== null) {
            const llmColor = isCorrectLLM ? 'success' : 'danger';
            const llmIcon = isCorrectLLM ? 'bi-check-circle-fill' : 'bi-x-circle-fill';
            const card = BenchmarkUtils.renderTemplate('tpl-trial-verdict-card', {
                '.verdict-icon': { addClass: `${llmIcon} text-${llmColor}` },
                '.verdict-text': { addClass: `text-${llmColor}`, text: `Verdict (LLM): ${isCorrectLLM ? 'Correct' : 'Incorrect'}` }
            });
            container.appendChild(card);
        }

        // Rule Verdict
        if (isCorrectRule !== undefined && isCorrectRule !== null) {
            const ruleColor = isCorrectRule ? 'success' : 'danger';
            const ruleIcon = isCorrectRule ? 'bi-check-circle-fill' : 'bi-x-circle-fill';
            const card = BenchmarkUtils.renderTemplate('tpl-trial-verdict-card', {
                '.verdict-icon': { addClass: `${ruleIcon} text-${ruleColor}` },
                '.verdict-text': { addClass: `text-${ruleColor}`, text: `Verdict (Rule): ${isCorrectRule ? 'Correct' : 'Incorrect'}` }
            });
            container.appendChild(card);
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
            const item = BenchmarkUtils.renderTemplate('tpl-run-config-item', {
                '.config-icon': { addClass: icon },
                '.config-detail-label': { text: label },
                '.config-value': { text: value, attrs: { title: value } }
            });
            configDetails.appendChild(item);
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
