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
    },

    /**
     * Create an icon element
     * @param {string} className - Bootstrap icon class name
     * @returns {HTMLElement} Icon element
     */
    createIcon: function(className) {
        const i = document.createElement('i');
        i.className = className;
        return i;
    },

    /**
     * Create a text element
     * @param {string} tagName - HTML tag name
     * @param {string} className - CSS class name
     * @param {string} textContent - Text content
     * @param {string} title - Optional title attribute
     * @returns {HTMLElement} Text element
     */
    createTextElement: function(tagName, className, textContent, title = '') {
        const element = document.createElement(tagName);
        element.className = className;
        element.textContent = textContent;
        if (title) {
            element.title = title;
        }
        return element;
    },

    /**
     * Create a link element
     * @param {string} href - Link URL
     * @param {string} className - CSS class name
     * @param {string} textContent - Link text
     * @param {string} target - Link target (default: '_self')
     * @returns {HTMLAnchorElement} Link element
     */
    createLink: function(href, className, textContent, target = '_self') {
        const link = document.createElement('a');
        link.href = href;
        link.className = className;
        link.textContent = textContent;
        link.target = target;
        return link;
    }
};
