/**
 * Simple UI component creator functions
 */

window.BenchmarkComponents = {
    /**
     * Create a status badge element
     * @param {string} text - Badge text
     * @param {boolean} isCorrect - Whether the status is correct/successful
     * @param {boolean} showNAForNull - Show "N/A" for null values
     * @returns {HTMLSpanElement} Badge element
     */
    createBadge: function(text, isCorrect, showNAForNull = false) {
        const span = document.createElement('span');
        span.className = 'badge';
        if (isCorrect === null && showNAForNull) {
            span.classList.add('bg-secondary');
            span.textContent = 'N/A';
        } else if (isCorrect) {
            span.classList.add('bg-success');
            span.textContent = text || 'Correct';
        } else {
            span.classList.add('bg-danger');
            span.textContent = text || 'Incorrect';
        }
        return span;
    }
};
