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

        if (!groundTruths) {
            container.innerHTML = '<span class="text-muted">N/A</span>';
            return container;
        }

        const gtArray = Array.isArray(groundTruths) ? groundTruths : groundTruths.split(',').map(s => s.trim()).filter(s => s);

        if (gtArray.length === 0) {
            container.innerHTML = '<span class="text-muted">N/A</span>';
            return container;
        }

        // Build ground truths element directly (no template dependency)
        const gtElement = document.createElement('div');
        gtElement.innerHTML = `
            <div class="d-flex align-items-center">
                <span class="badge bg-success bg-opacity-10 text-success border border-success border-opacity-25 ground-truth-summary">${gtArray.length} Ground Truth${gtArray.length > 1 ? 's' : ''}</span>
                <button class="btn btn-link btn-sm p-0 ms-2 text-decoration-none show-ground-truths-btn" type="button">
                    <i class="bi bi-chevron-down small"></i>
                </button>
                <button class="btn btn-link btn-sm p-0 ms-2 text-decoration-none hide-ground-truths-btn" type="button">
                    <i class="bi bi-chevron-up small"></i>
                </button>
            </div>
            <div class="ground-truths-list-container mt-2" style="max-height: 120px; overflow-y: auto;">
                <ul class="list-group list-group-flush ground-truths-list"></ul>
            </div>`;

        const ul = gtElement.querySelector('.ground-truths-list');
        gtArray.forEach((gt, idx) => {
            const li = document.createElement('li');
            li.className = 'px-0 py-0 my-1 border-0 small text-dark';
            li.innerHTML = `<i class="bi bi-check2 text-success me-2"></i><span class="fw-medium">${idx + 1}.</span> ${BenchmarkHelpers.escapeHtml(gt)}`;
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

        if (!groundTruths) {
            container.innerHTML = '<span class="text-muted fst-italic">N/A</span>';
            return container;
        }

        const gtArray = Array.isArray(groundTruths) ? groundTruths : groundTruths.split(',').map(s => s.trim()).filter(s => s);

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
