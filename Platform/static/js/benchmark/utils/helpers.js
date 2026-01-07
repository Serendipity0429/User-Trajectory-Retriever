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
