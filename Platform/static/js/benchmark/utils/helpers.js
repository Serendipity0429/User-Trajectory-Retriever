/**
 * General utility helper functions
 */

window.BenchmarkHelpers = window.BenchmarkHelpers || {};

/**
 * Generate a UUID (v4)
 * @returns {string} The UUID
 */
window.BenchmarkHelpers.generateUUID = function() {
    if (crypto.randomUUID) {
        return crypto.randomUUID();
    }
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
        var r = Math.random() * 16 | 0, v = c == 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
}

/**
 * Escape HTML entities to prevent XSS
 * @param {string} str - String to escape
 * @returns {string} Escaped string
 */
window.BenchmarkHelpers.escapeHtml = function(str) {
    if (typeof str !== 'string') return String(str);
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#039;');
}

/**
 * Escape HTML and convert newlines to <br> tags
 * @param {string} str - String to escape and format
 * @returns {string} Escaped string with <br> tags
 */
window.BenchmarkHelpers.escapeAndFormatContent = function(str) {
    return this.escapeHtml(str).replace(/\n/g, '<br>');
}

/**
 * Truncate text to a maximum length with ellipsis
 * @param {string} text - Text to truncate
 * @param {number} maxLength - Maximum length (default 120)
 * @returns {string} Truncated text
 */
window.BenchmarkHelpers.truncateText = function(text, maxLength = 120) {
    if (!text || text.length <= maxLength) return text || '';
    return text.substring(0, maxLength) + '...';
}

/**
 * Safely parse JSON with fallback
 * @param {string|object} str - String to parse or object to return
 * @param {*} defaultValue - Default value if parsing fails
 * @returns {*} Parsed object or default value
 */
window.BenchmarkHelpers.safeJsonParse = function(str, defaultValue = null) {
    if (typeof str !== 'string') return str;
    try {
        return JSON.parse(str);
    } catch (e) {
        return defaultValue;
    }
}

/**
 * Clear an element's content safely
 * @param {HTMLElement} element - Element to clear
 */
window.BenchmarkHelpers.clearElement = function(element) {
    if (element) element.innerHTML = '';
}

/**
 * Show a Bootstrap modal by ID
 * @param {string} modalId - The modal element ID
 */
window.BenchmarkHelpers.showModal = function(modalId) {
    const modalEl = document.getElementById(modalId);
    if (modalEl) {
        bootstrap.Modal.getOrCreateInstance(modalEl).show();
    }
}

/**
 * Normalize ground truths to array format
 * @param {Array|string} input - Array or comma-separated string
 * @returns {Array} Normalized array of ground truths
 */
window.BenchmarkHelpers.normalizeGroundTruths = function(input) {
    if (!input) return [];
    return Array.isArray(input) ? input : input.split(',').map(s => s.trim()).filter(s => s);
}

/**
 * Set UI element display states safely
 * @param {object} elements - Map of element references
 * @param {object} states - Map of display values (element key -> 'block'|'none'|'inline-block')
 */
window.BenchmarkHelpers.setUIState = function(elements, states) {
    for (const [key, display] of Object.entries(states)) {
        if (elements[key]) elements[key].style.display = display;
    }
}

/**
 * Store search data and return onclick handler string
 * @param {Array} data - Search results data
 * @returns {string} onclick attribute value
 */
window.BenchmarkHelpers.storeSearchData = function(data) {
    const dataId = 'search-' + Math.random().toString(36).substring(2, 11);
    window._benchmarkSearchData = window._benchmarkSearchData || {};
    window._benchmarkSearchData[dataId] = data;
    return `window.BenchmarkUI.SearchResults.showInModal(window._benchmarkSearchData['${dataId}'])`;
}

/**
 * Create an expandable toggle for show more/less functionality
 * @param {HTMLElement} showBtn - The "show more" button
 * @param {HTMLElement} hideBtn - The "show less" button
 * @param {HTMLElement} container - The container to toggle visibility
 * @param {Function} onExpand - Optional callback when expanded
 * @param {Function} onCollapse - Optional callback when collapsed
 */
window.BenchmarkHelpers.createExpandableToggle = function(showBtn, hideBtn, container, onExpand, onCollapse) {
    container.classList.add('d-none');
    hideBtn.classList.add('d-none');

    showBtn.onclick = function(e) {
        e.stopPropagation();
        container.classList.remove('d-none');
        showBtn.classList.add('d-none');
        hideBtn.classList.remove('d-none');
        if (onExpand) onExpand();
    };

    hideBtn.onclick = function(e) {
        e.stopPropagation();
        container.classList.add('d-none');
        showBtn.classList.remove('d-none');
        hideBtn.classList.add('d-none');
        if (onCollapse) onCollapse();
    };
}

/**
 * Process a streamed JSON response (NDJSON)
 * @param {Response} response - The fetch Response object
 * @param {Function} onData - Callback for each parsed JSON object
 * @param {Function} onComplete - Callback when stream completes
 * @param {Function} onError - Callback on error
 * @param {AbortSignal} abortSignal - Signal to check for abortion
 */
window.BenchmarkHelpers.processStreamedResponse = function(response, onData, onComplete, onError, abortSignal) {
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
}
