/**
 * Benchmark Utilities - Main Module
 * Core template rendering utility
 *
 * Dependencies (loaded via separate script tags):
 * - config/urls.js, config/state.js
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
     * Create a styled metric card.
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
    }
};
