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
        const card = BenchmarkUtils.renderTemplate('tpl-tool-card-wrapper', {
            '.tool-name': { text: toolName, addClass: titleColor },
            '.tool-body': { html: bodyContent }
        });
        return card.outerHTML;
    },

    _renderSearchResultsCard: function(parsedData) {
        const displayLimit = 5;
        const visibleItems = parsedData.slice(0, displayLimit);

        const listContainer = document.createElement('div');
        listContainer.className = 'list-group list-group-flush';

        visibleItems.forEach((item, idx) => {
            let snippet = item.snippet || '';
            if (snippet.length > 120) snippet = snippet.substring(0, 120) + '...';

            const itemEl = BenchmarkUtils.renderTemplate('tpl-tool-search-result-item', {
                '.result-index': { text: idx + 1 },
                '.result-title': { text: item.title || 'No Title' },
                '.result-link': { attrs: { href: item.link || item.url || '#' } },
                '.result-snippet': { text: snippet }
            });
            listContainer.appendChild(itemEl);
        });

        const remaining = Math.max(0, parsedData.length - displayLimit);
        const remainingText = remaining > 0 ? ` (+${remaining} more)` : '';
        const dataId = 'search-data-' + Math.random().toString(36).substr(2, 9);

        // Store data globally for onclick access
        window._benchmarkSearchData = window._benchmarkSearchData || {};
        window._benchmarkSearchData[dataId] = parsedData;

        const footer = BenchmarkUtils.renderTemplate('tpl-tool-search-results-footer', {
            '.results-count': { html: `<i class="bi bi-check-all me-1"></i>Found ${parsedData.length} results` },
            '.view-full-btn': {
                text: `View Full Details${remainingText}`,
                attrs: { onclick: `window.BenchmarkUI.SearchResults.showInModal(window._benchmarkSearchData['${dataId}'])` }
            }
        });

        listContainer.appendChild(footer);
        return listContainer.outerHTML;
    },

    _renderStructuredCard: function(toolName, content, isAction) {
        const sectionLabel = isAction ? 'Input Parameters' : 'Output';
        const contentText = typeof content === 'string' ? content : JSON.stringify(content, null, 2);

        const structured = BenchmarkUtils.renderTemplate('tpl-tool-structured-content', {
            '.section-label': { text: sectionLabel },
            '.content-text': { text: contentText }
        });

        return this._wrapInCard(toolName, structured.outerHTML, isAction);
    }
};
