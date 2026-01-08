/**
 * Search Results UI Component
 * Renders search results in lists, modals, and handles empty/error states
 */

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
