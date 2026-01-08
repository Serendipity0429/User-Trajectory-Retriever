/**
 * Core Module - Template rendering utility
 * Provides the base BenchmarkUtils namespace with template rendering
 *
 * Dependencies (loaded via separate script tags):
 * - config/urls.js, config/state.js, config/pipeline-config.js
 * - utils/helpers.js, utils/api.js, utils/export.js, utils/settings.js
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
     * Create a styled metric card (legacy, uses Bootstrap color names).
     * @param {object} config - { value, label, description, color }
     * @returns {HTMLElement} The metric card element
     */
    createMetricCard: function(config) {
        const col = document.createElement('div');
        col.className = 'col-lg-3 col-md-6';
        col.innerHTML = `
            <div class="metric-card border-top-${config.color}">
                <div class="card-body">
                    <div class="metric-label">${config.label}</div>
                    <div class="metric-value text-${config.color}-emphasis">${config.value}</div>
                    <div class="small text-muted">${config.description}</div>
                </div>
            </div>`;
        return col;
    },

    /**
     * Create a styled metric card with dynamic colors from API.
     * Uses inline styles for consistent color rendering based on metric name hash.
     * @param {object} metric - Metric object from API with { formatted, label, description, color }
     * @returns {HTMLElement} The metric card element
     */
    createMetricCardWithColor: function(metric) {
        const col = document.createElement('div');
        col.className = 'col-lg-3 col-md-6';

        const color = metric.color || { border: '#6c757d', text: '#495057', bg: '#f8f9fa' };

        col.innerHTML = `
            <div class="metric-card" style="border-top: 4px solid ${color.border}; background: ${color.bg};">
                <div class="card-body">
                    <div class="metric-label" style="color: ${color.text};">${metric.label}</div>
                    <div class="metric-value" style="color: ${color.text};">${metric.formatted}</div>
                    <div class="small text-muted">${metric.description}</div>
                </div>
            </div>`;
        return col;
    }
};
