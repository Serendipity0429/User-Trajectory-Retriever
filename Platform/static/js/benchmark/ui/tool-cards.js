/**
 * Tool Cards UI Component
 * Renders tool action and observation cards with structured display
 */

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

        return `
            <div class="card border border-light shadow-sm">
                <div class="card-header bg-light bg-gradient border-bottom py-2 px-3 d-flex align-items-center">
                    <i class="bi bi-terminal-fill text-secondary me-2"></i>
                    <span class="fw-bold font-monospace ${titleColor}">${BenchmarkHelpers.escapeHtml(toolName)}</span>
                </div>
                <div class="card-body p-3 bg-white">
                    ${bodyContent}
                </div>
            </div>`;
    },

    _renderSearchResultsCard: function(parsedData) {
        const displayLimit = 5;
        const visibleItems = parsedData.slice(0, displayLimit);

        let listHtml = '<div class="list-group list-group-flush">';

        visibleItems.forEach((item, idx) => {
            let snippet = item.snippet || '';
            if (snippet.length > 120) snippet = snippet.substring(0, 120) + '...';

            const safeTitle = BenchmarkHelpers.escapeHtml(item.title || 'No Title');
            const safeSnippet = BenchmarkHelpers.escapeHtml(snippet);
            const safeLink = BenchmarkHelpers.escapeHtml(item.link || item.url || '#');

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

        return `
            <div class="card border border-light shadow-sm">
                <div class="card-header bg-light bg-gradient border-bottom py-2 px-3 d-flex align-items-center">
                    <i class="bi bi-terminal-fill text-secondary me-2"></i>
                    <span class="fw-bold font-monospace ${titleColor}">${BenchmarkHelpers.escapeHtml(toolName)}</span>
                </div>
                <div class="card-body p-3 bg-white">
                    <div class="text-muted small text-uppercase fw-bold mb-2" style="font-size: 0.7rem; letter-spacing: 0.5px;">${sectionLabel}</div>
                    <div class="p-2 bg-light border rounded font-monospace small text-dark" style="white-space: pre-wrap; max-height: 500px; overflow-y: auto;">${BenchmarkHelpers.escapeHtml(contentText)}</div>
                </div>
            </div>`;
    }
};
