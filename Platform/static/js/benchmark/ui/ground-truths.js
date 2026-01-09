/**
 * Ground Truths UI Component
 * Renders ground truths as expandable lists or inline badges
 */

window.BenchmarkUI.GroundTruths = {
    /**
     * Render ground truths as a list with expand/collapse functionality
     * @param {Array|string} groundTruths - Array or comma-separated string of ground truths
     * @returns {HTMLElement} Container with ground truths
     */
    renderList: function(groundTruths) {
        const container = document.createElement('div');

        const gtArray = BenchmarkHelpers.normalizeGroundTruths(groundTruths);
        if (gtArray.length === 0) {
            container.innerHTML = '<span class="text-muted">N/A</span>';
            return container;
        }

        const gtElement = BenchmarkUtils.renderTemplate('tpl-ground-truths-expandable', {
            '.ground-truth-summary': { text: `${gtArray.length} Ground Truth${gtArray.length > 1 ? 's' : ''}` }
        });

        const ul = gtElement.querySelector('.ground-truths-list');
        gtArray.forEach((gt, idx) => {
            const li = BenchmarkUtils.renderTemplate('tpl-ground-truth-list-item', {
                '.gt-index': { text: `${idx + 1}.` },
                '.gt-text': { text: gt }
            });
            ul.appendChild(li);
        });

        const showBtn = gtElement.querySelector('.show-ground-truths-btn');
        const hideBtn = gtElement.querySelector('.hide-ground-truths-btn');
        const listContainer = gtElement.querySelector('.ground-truths-list-container');

        BenchmarkHelpers.createExpandableToggle(showBtn, hideBtn, listContainer);

        container.appendChild(gtElement);
        return container;
    },

    /**
     * Render ground truths as inline badges
     * @param {Array|string} groundTruths - Array or comma-separated string
     * @returns {HTMLElement} Container with badges
     */
    renderBadges: function(groundTruths) {
        const container = document.createElement('div');
        const gtArray = BenchmarkHelpers.normalizeGroundTruths(groundTruths);
        if (gtArray.length === 0) {
            container.innerHTML = '<span class="text-muted fst-italic">N/A</span>';
            return container;
        }

        gtArray.forEach(gt => {
            const badge = document.createElement('span');
            badge.className = 'badge bg-success text-white fw-medium me-2';
            badge.textContent = gt;
            container.appendChild(badge);
        });

        return container;
    }
};
