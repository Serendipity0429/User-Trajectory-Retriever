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
 * Debounce a function
 * @param {Function} func - The function to debounce
 * @param {number} wait - The delay in milliseconds
 * @returns {Function} The debounced function
 */
window.BenchmarkHelpers.debounce = function(func, wait) {
    let timeout;
    return function(...args) {
        const context = this;
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(context, args), wait);
    };
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
