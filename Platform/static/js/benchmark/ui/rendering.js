/**
 * Consolidated UI rendering components for benchmark
 * Handles: ground truths, search results, message bubbles, tool cards, agent steps, verdict cards
 */

window.BenchmarkUI = window.BenchmarkUI || {};

// =============================================================================
// Ground Truths
// =============================================================================

window.BenchmarkUI.GroundTruths = {
    /**
     * Render ground truths as a list with expand/collapse functionality
     * @param {Array|string} groundTruths - Array or comma-separated string of ground truths
     * @returns {HTMLElement} Container with ground truths
     */
    renderList: function(groundTruths) {
        const container = document.createElement('div');

        if (!groundTruths) {
            container.innerHTML = '<span class="text-muted">N/A</span>';
            return container;
        }

        const gtArray = Array.isArray(groundTruths) ? groundTruths : groundTruths.split(',').map(s => s.trim()).filter(s => s);

        if (gtArray.length === 0) {
            container.innerHTML = '<span class="text-muted">N/A</span>';
            return container;
        }

        // Build ground truths element directly (no template dependency)
        const gtElement = document.createElement('div');
        gtElement.innerHTML = `
            <div class="d-flex align-items-center">
                <span class="badge bg-success bg-opacity-10 text-success border border-success border-opacity-25 ground-truth-summary">${gtArray.length} Ground Truth${gtArray.length > 1 ? 's' : ''}</span>
                <button class="btn btn-link btn-sm p-0 ms-2 text-decoration-none show-ground-truths-btn" type="button">
                    <i class="bi bi-chevron-down small"></i>
                </button>
                <button class="btn btn-link btn-sm p-0 ms-2 text-decoration-none hide-ground-truths-btn" type="button">
                    <i class="bi bi-chevron-up small"></i>
                </button>
            </div>
            <div class="ground-truths-list-container mt-2">
                <ul class="list-group list-group-flush ground-truths-list"></ul>
            </div>`;

        const ul = gtElement.querySelector('.ground-truths-list');
        gtArray.forEach((gt, idx) => {
            const li = document.createElement('li');
            li.className = 'list-group-item px-0 py-1 border-0 small text-dark';
            li.innerHTML = `<i class="bi bi-check2 text-success me-2"></i><span class="fw-medium">${idx + 1}.</span> ${BenchmarkHelpers.escapeHtml(gt)}`;
            ul.appendChild(li);
        });

        const showBtn = gtElement.querySelector('.show-ground-truths-btn');
        const hideBtn = gtElement.querySelector('.hide-ground-truths-btn');
        const listContainer = gtElement.querySelector('.ground-truths-list-container');

        BenchmarkHelpers.createExpandableToggle(showBtn, hideBtn, listContainer);

        container.appendChild(gtElement);
        return container;
    },

    /**
     * Render ground truths as inline badges
     * @param {Array|string} groundTruths - Array or comma-separated string
     * @returns {HTMLElement} Container with badges
     */
    renderBadges: function(groundTruths) {
        const container = document.createElement('div');

        if (!groundTruths) {
            container.innerHTML = '<span class="text-muted fst-italic">N/A</span>';
            return container;
        }

        const gtArray = Array.isArray(groundTruths) ? groundTruths : groundTruths.split(',').map(s => s.trim()).filter(s => s);

        if (gtArray.length === 0) {
            container.innerHTML = '<span class="text-muted fst-italic">N/A</span>';
            return container;
        }

        gtArray.forEach(gt => {
            const badge = document.createElement('span');
            badge.className = 'badge bg-success text-white fw-medium me-2';
            badge.textContent = gt;
            container.appendChild(badge);
        });

        return container;
    }
};

// =============================================================================
// Search Results
// =============================================================================

window.BenchmarkUI.SearchResults = {
    /**
     * Render search results into a list element
     */
    render: function(results, resultsListElement) {
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
            this.renderEmpty(resultsListElement);
        }
    },

    /**
     * Render empty state for no results
     */
    renderEmpty: function(resultsListElement) {
        resultsListElement.innerHTML = '';
        const alertDiv = document.createElement('div');
        alertDiv.className = 'alert alert-info';
        alertDiv.textContent = 'No results found.';
        resultsListElement.appendChild(alertDiv);
    },

    /**
     * Render error state for search
     */
    renderError: function(resultsListElement, errorMessage) {
        resultsListElement.innerHTML = '';
        const alertDiv = document.createElement('div');
        alertDiv.className = 'alert alert-danger';
        alertDiv.textContent = errorMessage;
        resultsListElement.appendChild(alertDiv);
    },

    /**
     * Render search results in a modal with collapsible full content
     */
    renderModal: function(results, container, modalId = 'benchmarkGenericModal') {
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
                } catch (err) { }

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
                            setTimeout(() => {
                                const actuallyExpanded = collapseDiv.classList.contains('show');
                                if (btnText) btnText.textContent = actuallyExpanded ? 'Hide Full Content' : 'Show Full Content';
                                if (icon) icon.className = actuallyExpanded ? 'bi bi-chevron-up ms-auto ps-3 icon-chevron' : 'bi bi-chevron-down ms-auto ps-3 icon-chevron';
                            }, 350);
                        });
                    }
                }

                container.appendChild(itemElement);
            });
        } else {
            const noResultsDiv = document.createElement('div');
            noResultsDiv.className = 'p-5 text-center text-muted';
            noResultsDiv.innerHTML = '<i class="bi bi-search fs-1 d-block mb-3 opacity-25"></i><p>No search results data found for this trial.</p>';
            container.appendChild(noResultsDiv);
        }
    },

    /**
     * Show search results in modal
     */
    showInModal: function(results, containerId = 'modal-generic-content-container', modalId = 'benchmarkGenericModal') {
        const container = document.getElementById(containerId);
        if (!container) return;

        this.renderModal(results, container, modalId);
        bootstrap.Modal.getOrCreateInstance(document.getElementById(modalId)).show();
    }
};

// =============================================================================
// Message Bubble
// =============================================================================

window.BenchmarkUI.MessageBubble = {
    ROLE_CONFIG: {
        user: {
            alignment: 'justify-content-end',
            bubbleClass: 'bg-white shadow-sm border text-dark',
            icon: 'bi-person-fill',
            showIcon: true,
            iconSide: 'right'
        },
        system: {
            alignment: 'justify-content-center',
            bubbleClass: 'bg-light text-muted',
            icon: 'bi-gear-fill',
            showIcon: false
        },
        assistant: {
            alignment: 'justify-content-start',
            bubbleClass: 'bg-white border shadow-sm',
            icon: 'bi-robot',
            showIcon: true,
            iconSide: 'left'
        }
    },

    /**
     * Create a message bubble for chat-style display
     * @param {string} role - 'user', 'system', or 'assistant'
     * @param {string} content - HTML content for the bubble
     * @param {string} extraBubbleClass - Additional CSS classes for bubble
     * @param {string} overrideIcon - Override default icon
     * @returns {HTMLElement} Message row element
     */
    create: function(role, content, extraBubbleClass = '', overrideIcon = null) {
        const config = this.ROLE_CONFIG[role] || this.ROLE_CONFIG.assistant;
        const iconClass = overrideIcon || config.icon;

        const row = document.createElement('div');
        row.className = `d-flex ${config.alignment} mb-3 message-bubble`;

        // Icon element
        let iconEl = null;
        if (config.showIcon) {
            iconEl = document.createElement('div');
            iconEl.className = `d-flex align-items-start ${config.iconSide === 'left' ? 'me-2' : 'ms-2'}`;
            iconEl.innerHTML = `<span class="badge rounded-circle bg-secondary-subtle text-secondary p-2"><i class="bi ${iconClass}"></i></span>`;
        }

        // Bubble element
        const bubble = document.createElement('div');
        bubble.className = `p-3 rounded-3 ${config.bubbleClass} ${extraBubbleClass}`.trim();
        bubble.style.maxWidth = '85%';
        bubble.innerHTML = content;

        // Assemble
        if (config.iconSide === 'left' && iconEl) row.appendChild(iconEl);
        row.appendChild(bubble);
        if (config.iconSide === 'right' && iconEl) row.appendChild(iconEl);

        return row;
    }
};

// =============================================================================
// Tool Cards
// =============================================================================

window.BenchmarkUI.ToolCards = {
    BADGE_CONFIG: {
        action: {
            label: 'Tool Execution',
            icon: 'bi-tools',
            class: 'bg-primary bg-opacity-10 text-primary border border-primary border-opacity-25'
        },
        observation: {
            label: 'Observation',
            icon: 'bi-eye',
            class: 'bg-success bg-opacity-10 text-success border border-success border-opacity-25'
        }
    },

    /**
     * Render a unified tool card for both actions and observations
     */
    render: function(type, toolName, content, options = {}) {
        const isAction = type === 'action';
        const badgeConfig = this.BADGE_CONFIG[type] || this.BADGE_CONFIG.observation;

        let innerHtml = '';
        let contentStyle = {};
        let removeClasses = '';

        // Special handling for search results (observation only)
        if (!isAction && options.isSearch && options.parsedData && Array.isArray(options.parsedData)) {
            const searchContent = this._renderSearchResultsCard(options.parsedData);
            // Wrap search results in structured card with tool name header
            innerHtml = this._wrapInCard(toolName || 'web_search_tool', searchContent, isAction);
            contentStyle = { 'white-space': 'normal' };
            removeClasses = 'p-3 bg-white border rounded-3 shadow-sm font-monospace small text-dark';
        } else if (toolName && toolName !== 'undefined') {
            innerHtml = this._renderStructuredCard(toolName, content, isAction);
            contentStyle = { 'white-space': 'normal' };
            removeClasses = 'p-3 bg-white border rounded-3 shadow-sm font-monospace small text-dark';
        } else {
            innerHtml = typeof content === 'string' ? content : JSON.stringify(content, null, 2);
            contentStyle = { 'white-space': 'pre-wrap', 'max-height': '500px', 'overflow-y': 'auto', 'font-size': '0.9rem' };
            removeClasses = 'small';
        }

        const element = BenchmarkUtils.renderTemplate('tpl-agent-action', {
            '.agent-badge-text': { addClass: badgeConfig.class },
            '.badge-icon': { addClass: badgeConfig.icon },
            '.badge-label': { text: badgeConfig.label },
            '.tool-content': { html: innerHtml, style: contentStyle, removeClass: removeClasses }
        });

        const icon = isAction ? 'bi-gear' : 'bi-eye';
        return BenchmarkUI.MessageBubble.create('assistant', element.outerHTML, 'bg-transparent border-0 shadow-none p-0', icon);
    },

    /**
     * Wrap content in a card with tool name header
     */
    _wrapInCard: function(toolName, bodyContent, isAction) {
        const titleColor = isAction ? 'text-primary' : 'text-success';
        const escapeHtml = BenchmarkHelpers.escapeHtml;

        return `
            <div class="card border border-light shadow-sm">
                <div class="card-header bg-light bg-gradient border-bottom py-2 px-3 d-flex align-items-center">
                    <i class="bi bi-terminal-fill text-secondary me-2"></i>
                    <span class="fw-bold font-monospace ${titleColor}">${escapeHtml(toolName)}</span>
                </div>
                <div class="card-body p-3 bg-white">
                    ${bodyContent}
                </div>
            </div>`;
    },

    _renderSearchResultsCard: function(parsedData) {
        const displayLimit = 5;
        const visibleItems = parsedData.slice(0, displayLimit);
        const escapeHtml = BenchmarkHelpers.escapeHtml;

        let listHtml = '<div class="list-group list-group-flush">';

        visibleItems.forEach((item, idx) => {
            let snippet = item.snippet || '';
            if (snippet.length > 120) snippet = snippet.substring(0, 120) + '...';

            const safeTitle = escapeHtml(item.title || 'No Title');
            const safeSnippet = escapeHtml(snippet);
            const safeLink = escapeHtml(item.link || item.url || '#');

            listHtml += `
                <div class="list-group-item bg-transparent px-0 py-2 border-bottom border-light">
                    <div class="d-flex w-100 justify-content-between align-items-start mb-1">
                        <div class="d-flex align-items-start" style="max-width: 90%;">
                            <span class="badge bg-light text-secondary border me-2 flex-shrink-0" style="font-size: 0.75rem;">${idx + 1}</span>
                            <h6 class="mb-0 text-primary fw-bold text-wrap" style="line-height: 1.4; font-size: 0.95rem;">${safeTitle}</h6>
                        </div>
                        <a href="${safeLink}" target="_blank" class="text-secondary opacity-50 hover-opacity-100 ms-2"><i class="bi bi-box-arrow-up-right"></i></a>
                    </div>
                    <p class="mb-0 text-muted ps-4 ms-1" style="font-size: 0.85rem;">${safeSnippet}</p>
                </div>`;
        });

        const resultsJson = encodeURIComponent(JSON.stringify(parsedData));
        const remaining = Math.max(0, parsedData.length - displayLimit);
        const remainingText = remaining > 0 ? ` (+${remaining} more)` : '';

        listHtml += `
            <div class="mt-2 pt-1">
                <div class="d-flex align-items-center justify-content-between">
                    <span class="text-success small fw-medium" style="font-size: 0.8rem;"><i class="bi bi-check-all me-1"></i>Found ${parsedData.length} results</span>
                    <button class="btn btn-sm btn-light border btn-xs text-primary shadow-sm" style="font-size: 0.8rem;" onclick="
                        const data = JSON.parse(decodeURIComponent('${resultsJson}'));
                        window.BenchmarkUI.SearchResults.showInModal(data);
                    ">View Full Details${remainingText}</button>
                </div>
            </div>
        </div>`;

        return listHtml;
    },

    _renderStructuredCard: function(toolName, content, isAction) {
        const sectionLabel = isAction ? 'Input Parameters' : 'Output';
        const titleColor = isAction ? 'text-primary' : 'text-success';
        const contentText = typeof content === 'string' ? content : JSON.stringify(content, null, 2);
        const escapeHtml = BenchmarkHelpers.escapeHtml;

        return `
            <div class="card border border-light shadow-sm">
                <div class="card-header bg-light bg-gradient border-bottom py-2 px-3 d-flex align-items-center">
                    <i class="bi bi-terminal-fill text-secondary me-2"></i>
                    <span class="fw-bold font-monospace ${titleColor}">${escapeHtml(toolName)}</span>
                </div>
                <div class="card-body p-3 bg-white">
                    <div class="text-muted small text-uppercase fw-bold mb-2" style="font-size: 0.7rem; letter-spacing: 0.5px;">${sectionLabel}</div>
                    <div class="p-2 bg-light border rounded font-monospace small text-dark" style="white-space: pre-wrap; max-height: 500px; overflow-y: auto;">${escapeHtml(contentText)}</div>
                </div>
            </div>`;
    }
};

// =============================================================================
// Agent Steps
// =============================================================================

window.BenchmarkUI.AgentSteps = {
    _parseContent: function(str) {
        if (typeof str !== 'string') return str;
        try { return JSON.parse(str); } catch (e) { return null; }
    },

    _escapeHtml: function(str) {
        if (typeof str !== 'string') return String(str);
        return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    },

    /**
     * Render a single agent step based on its type
     */
    render: function(step, idx, trialId, finalAnswerText) {
        const role = step.role || 'assistant';
        const type = step.step_type || 'text';
        let content = step.content || '';
        const name = step.name || '';

        if (type === 'thought') return this._renderThought(content, trialId, idx);
        if (type === 'action') return this._renderAction(content);
        if (type === 'observation') return this._renderObservation(content, name, finalAnswerText);
        if (role === 'system') return this._renderSystemPrompt(content);
        if (role === 'user') return this._renderUserInput(content);

        if (typeof content === 'string') {
            content = this._escapeHtml(content).replace(/\n/g, '<br>');
        }
        return BenchmarkUI.MessageBubble.create('assistant', content, '', 'bi-chat-left-dots');
    },

    _renderThought: function(content, trialId, idx) {
        const tId = `thought-${trialId}-${idx}`;
        const thoughtElement = BenchmarkUtils.renderTemplate('tpl-agent-thought', {
            '.collapse-btn': { attrs: { 'data-bs-target': `#${tId}` } },
            '.collapse-target': { attrs: { id: tId } },
            '.thinking-content': { text: content }
        });
        return BenchmarkUI.MessageBubble.create('assistant', thoughtElement.outerHTML, 'bg-transparent border-0 shadow-none p-0', 'bi-robot');
    },

    _renderAction: function(content) {
        // Special case: Search Query text format
        if (typeof content === 'string' && content.trim().startsWith('Search Query:')) {
            const element = BenchmarkUtils.renderTemplate('tpl-agent-action', {
                '.agent-badge-text': { addClass: 'bg-info bg-opacity-10 text-info border-info border-opacity-25' },
                '.badge-icon': { addClass: 'bi-search' },
                '.badge-label': { text: 'Search Query' },
                '.tool-content': { text: content }
            });
            return BenchmarkUI.MessageBubble.create('assistant', element.outerHTML, 'bg-transparent border-0 shadow-none p-0', 'bi-gear');
        }

        // Parse structured tool data
        let toolName = null;
        let toolInput = null;
        try {
            const toolData = (typeof content === 'string') ? JSON.parse(content) : content;
            if (toolData && toolData.name && toolData.input) {
                toolName = toolData.name;
                toolInput = toolData.input;
            }
        } catch (e) { }

        return BenchmarkUI.ToolCards.render('action', toolName, toolInput || content);
    },

    _renderObservation: function(content, name, finalAnswerText) {
        let parsedData = null;
        let isSearch = false;
        let isFinalAnswer = false;
        let displayContent = content;
        let toolName = '';

        // Step 1: Parse content - handle both string and object inputs
        if (typeof content === 'string') {
            parsedData = this._parseContent(content);
        } else if (content && typeof content === 'object') {
            parsedData = content;
        }

        // Step 2: Extract tool name and output from structured JSON {name, output}
        if (parsedData && typeof parsedData === 'object' && !Array.isArray(parsedData)) {
            // Extract tool name from the observation object
            if (parsedData.name) {
                toolName = parsedData.name;
            }
            // Extract output and use it as display content
            if (parsedData.output !== undefined) {
                displayContent = parsedData.output;
                // Try to parse output if it's a string (e.g., JSON array of search results)
                if (typeof displayContent === 'string') {
                    const outputParsed = this._parseContent(displayContent);
                    if (outputParsed) parsedData = outputParsed;
                } else {
                    parsedData = displayContent;
                }
            }
        }

        // Step 3: Fallback to step.name if no tool name extracted
        if (!toolName && name) {
            toolName = name;
        }

        // Step 4: Detect search results
        if (toolName === 'web_search_tool' || (parsedData && Array.isArray(parsedData) && parsedData.length > 0 && parsedData[0].title)) {
            isSearch = true;
        }

        // Handle "Search Results:" prefix format
        if (typeof content === 'string' && content.startsWith('Search Results:')) {
            isSearch = true;
            displayContent = content.replace('Search Results:', '').trim();
            parsedData = this._parseSearchResults(displayContent);
        }

        // Step 5: Detect final answer
        if (toolName === 'answer_question' ||
            (typeof displayContent === 'string' && displayContent.includes('Answer submitted successfully'))) {
            isFinalAnswer = true;
        }

        // Handle Final Answer
        if (isFinalAnswer) {
            const finalAnswer = BenchmarkUtils.renderTemplate('tpl-agent-final-answer', {
                '.response-text': { text: finalAnswerText || '' }
            });
            return BenchmarkUI.MessageBubble.create('assistant', finalAnswer.outerHTML, '', 'bi-chat-left-dots');
        }

        // Step 6: Ensure observation has a meaningful tool name
        const genericNames = ['', 'undefined', 'system', 'assistant', 'user'];
        if (!toolName || genericNames.includes(toolName.toLowerCase())) {
            toolName = isSearch ? 'web_search_tool' : 'Tool Result';
        }

        return BenchmarkUI.ToolCards.render('observation', toolName, displayContent, {
            isSearch: isSearch,
            parsedData: parsedData
        });
    },

    _parseSearchResults: function(displayContent) {
        try {
            const jsonMatch = displayContent.match(/<!-- JSON_DATA_FOR_UI: (.*?) -->/s);
            if (jsonMatch && jsonMatch[1]) return JSON.parse(jsonMatch[1]);

            const extractedJson = JSON.parse(displayContent);
            if (Array.isArray(extractedJson)) return extractedJson;
        } catch (e) {
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
            if (extractedResults.length > 0) return extractedResults;
        }
        return null;
    },

    _renderSystemPrompt: function(content) {
        const systemPrompt = BenchmarkUtils.renderTemplate('tpl-system-prompt', {
            '.system-config-content': { text: content }
        });
        return BenchmarkUI.MessageBubble.create('system', systemPrompt.outerHTML, 'bg-light border-secondary border-opacity-10 shadow-none');
    },

    _renderUserInput: function(content) {
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
                            window.BenchmarkUI.SearchResults.showInModal(data);
                        }
                    }
                });

                let displayContent = this._escapeHtml(content);
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
                    return BenchmarkUI.MessageBubble.create('user', displayContent);
                }
            }
        }
        return BenchmarkUI.MessageBubble.create('user', this._escapeHtml(content).replace(/\n/g, '<br>'));
    }
};

// =============================================================================
// Verdict Cards
// =============================================================================

window.BenchmarkUI.VerdictCards = {
    VERDICT_CONFIG: {
        correct: { color: 'success', icon: 'bi-check-circle-fill' },
        incorrect: { color: 'danger', icon: 'bi-x-circle-fill' }
    },

    /**
     * Render trial verdict cards for LLM and Rule verdicts
     */
    render: function(trial) {
        const isCorrectLLM = trial.is_correct_llm !== undefined ? trial.is_correct_llm : trial.is_correct;
        const isCorrectRule = trial.is_correct_rule;

        if (isCorrectLLM === undefined && isCorrectRule === undefined) return null;

        const container = BenchmarkUtils.renderTemplate('tpl-trial-verdict-container');

        if (isCorrectLLM !== undefined && isCorrectLLM !== null) {
            container.appendChild(this._createVerdictCard(isCorrectLLM, 'LLM'));
        }

        if (isCorrectRule !== undefined && isCorrectRule !== null) {
            container.appendChild(this._createVerdictCard(isCorrectRule, 'Rule'));
        }

        return container;
    },

    _createVerdictCard: function(isCorrect, label) {
        const config = isCorrect ? this.VERDICT_CONFIG.correct : this.VERDICT_CONFIG.incorrect;
        const verdictText = isCorrect ? 'Correct' : 'Incorrect';

        return BenchmarkUtils.renderTemplate('tpl-trial-verdict-card', {
            '.verdict-icon': { addClass: `${config.icon} text-${config.color}` },
            '.verdict-text': { addClass: `text-${config.color}`, text: `Verdict (${label}): ${verdictText}` }
        });
    }
};
