/**
 * Core Module - Template rendering utility
 * Provides the base BenchmarkUtils namespace with template rendering
 *
 * Dependencies (loaded via separate script tags):
 * - config/urls.js, config/state.js, config/pipeline-config.js
 * - utils/helpers.js, utils/api.js, utils/settings.js
 * - utils/batch_selection.js, utils/session_ui.js, utils/pipeline_runner.js
 */

window.BenchmarkUtils = {
    /**
     * Renders a template by ID with data mapping.
     * @param {string} templateId - The ID of the <template> element.
     * @param {object} dataMap - Key-value pairs for template population.
     * @returns {HTMLElement} - The rendered DOM element.
     */
    renderTemplate: function(templateId, dataMap = {}) {
        const template = document.getElementById(templateId);
        if (!template) {
            console.error(`Template not found: ${templateId}`);
            return document.createElement('div');
        }

        const clone = template.content.cloneNode(true);

        for (const [selector, actions] of Object.entries(dataMap)) {
            let elements = [];
            if (selector === 'root') {
                elements = Array.from(clone.children);
            } else {
                elements = clone.querySelectorAll(selector);
            }

            elements.forEach(el => {
                if (!el) return;

                if (actions.text !== undefined) el.textContent = actions.text;
                if (actions.html !== undefined) el.innerHTML = actions.html;
                if (actions.src !== undefined) el.src = actions.src;
                if (actions.href !== undefined) el.href = actions.href;

                if (actions.class !== undefined) el.className = actions.class;
                if (actions.addClass !== undefined) el.classList.add(...actions.addClass.split(' ').filter(c => c));
                if (actions.removeClass !== undefined) el.classList.remove(...actions.removeClass.split(' ').filter(c => c));

                if (actions.style !== undefined) Object.assign(el.style, actions.style);

                if (actions.attrs) {
                    for (const [attr, val] of Object.entries(actions.attrs)) {
                        if (val === null) el.removeAttribute(attr);
                        else el.setAttribute(attr, val);
                    }
                }

                if (typeof actions.onclick === 'function') {
                    el.onclick = actions.onclick;
                }
            });
        }

        return clone.children.length === 1 ? clone.firstElementChild : clone;
    },

    /**
     * Create a styled metric card.
     * Supports both Bootstrap color classes (legacy) and dynamic colors from API.
     *
     * @param {object} config - Metric configuration
     * @param {string} config.value|config.formatted - The value to display
     * @param {string} config.label - The metric label
     * @param {string} config.description - The metric description
     * @param {string|object} config.color - Either a Bootstrap color name (string) or
     *                                       an object { border, text, bg } for dynamic colors
     * @returns {HTMLElement} The metric card element
     */
    createMetricCard: function(config) {
        const col = document.createElement('div');
        col.className = 'col-lg-3 col-md-6';

        const value = config.formatted || config.value;
        const color = config.color;

        // Check if color is a dynamic object or Bootstrap class name
        if (color && typeof color === 'object') {
            // Dynamic colors from API
            const colorObj = { border: '#6c757d', text: '#495057', bg: '#f8f9fa', ...color };
            col.innerHTML = `
                <div class="metric-card" style="border-top: 4px solid ${colorObj.border}; background: ${colorObj.bg};">
                    <div class="card-body">
                        <div class="metric-label" style="color: ${colorObj.text};">${config.label}</div>
                        <div class="metric-value" style="color: ${colorObj.text};">${value}</div>
                        <div class="small text-muted">${config.description}</div>
                    </div>
                </div>`;
        } else {
            // Bootstrap color class (legacy)
            const colorClass = color || 'secondary';
            col.innerHTML = `
                <div class="metric-card border-top-${colorClass}">
                    <div class="card-body">
                        <div class="metric-label">${config.label}</div>
                        <div class="metric-value text-${colorClass}-emphasis">${value}</div>
                        <div class="small text-muted">${config.description}</div>
                    </div>
                </div>`;
        }
        return col;
    }
};
