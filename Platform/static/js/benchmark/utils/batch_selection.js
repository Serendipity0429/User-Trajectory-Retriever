/**
 * Batch selection utilities for list items with checkboxes
 * Handles select all, individual selection, and batch delete operations
 */

window.BenchmarkBatchSelection = window.BenchmarkBatchSelection || {};

/**
 * Sets up batch selection logic for a list of items with checkboxes.
 * Supports separate "Select All" checkboxes for pipeline runs and single sessions.
 * @param {string} listContainerId - ID of the container holding all selectable items.
 * @param {string} selectAllCheckboxId - ID of the global 'Select All' checkbox (legacy, optional).
 * @param {string} itemCheckboxClass - Class name for individual item checkboxes.
 * @param {string} deleteButtonId - ID of the button that performs batch deletion.
 * @param {function} deleteActionCallback - Function to call when the delete button is clicked. Receives an array of selected item IDs and selected group IDs.
 * @param {string} [itemGroupIdClass] - Optional: Class name for item group checkboxes (e.g., for multi-turn sessions).
 */
window.BenchmarkBatchSelection.setup = function(listContainerId, selectAllCheckboxId, itemCheckboxClass, deleteButtonId, deleteActionCallback, itemGroupIdClass = null) {
    const listContainer = document.getElementById(listContainerId);
    const deleteSelectedBtn = document.getElementById(deleteButtonId);

    if (!listContainer || !deleteSelectedBtn) return;

    // Selectors for both legacy and new structure
    const getSelectAllCheckbox = () => document.getElementById(selectAllCheckboxId);
    const getSelectAllPipelineRuns = () => document.getElementById('select-all-pipeline-runs');
    const getSelectAllSingleSessions = () => document.getElementById('select-all-single-sessions');

    const getCheckboxes = () => listContainer.querySelectorAll(`.${itemCheckboxClass}`);
    const getGroupCheckboxes = () => itemGroupIdClass ? listContainer.querySelectorAll(`.${itemGroupIdClass}`) : [];

    // Get checkboxes within specific sections
    const getSingleSessionCheckboxes = () => {
        const container = listContainer.querySelector('.single-sessions-container');
        return container ? container.querySelectorAll(`.${itemCheckboxClass}`) : [];
    };

    const getPipelineGroupCheckboxes = () => {
        const container = listContainer.querySelector('.pipeline-runs-container');
        return container && itemGroupIdClass ? container.querySelectorAll(`.${itemGroupIdClass}`) : getGroupCheckboxes();
    };

    const toggleDeleteButton = () => {
        const anyItemChecked = Array.from(getCheckboxes()).some(cb => cb.checked);
        const anyGroupChecked = Array.from(getGroupCheckboxes()).some(cb => cb.checked);
        const anyChecked = anyItemChecked || anyGroupChecked;
        deleteSelectedBtn.style.display = anyChecked ? 'inline-block' : 'none';

        // Update legacy select all checkbox state
        const selectAllCheckbox = getSelectAllCheckbox();
        if (selectAllCheckbox) {
            const allCheckboxes = Array.from(getCheckboxes()).concat(Array.from(getGroupCheckboxes()));
            const allChecked = allCheckboxes.length > 0 && allCheckboxes.every(cb => cb.checked);
            selectAllCheckbox.checked = anyChecked && allChecked;
        }

        // Update pipeline runs select all checkbox state
        const selectAllPipelineRuns = getSelectAllPipelineRuns();
        if (selectAllPipelineRuns) {
            const pipelineCheckboxes = Array.from(getPipelineGroupCheckboxes());
            const allPipelineChecked = pipelineCheckboxes.length > 0 && pipelineCheckboxes.every(cb => cb.checked);
            const anyPipelineChecked = pipelineCheckboxes.some(cb => cb.checked);
            selectAllPipelineRuns.checked = allPipelineChecked;
            selectAllPipelineRuns.indeterminate = anyPipelineChecked && !allPipelineChecked;
        }

        // Update single sessions select all checkbox state
        const selectAllSingleSessions = getSelectAllSingleSessions();
        if (selectAllSingleSessions) {
            const sessionCheckboxes = Array.from(getSingleSessionCheckboxes());
            const allSessionsChecked = sessionCheckboxes.length > 0 && sessionCheckboxes.every(cb => cb.checked);
            const anySessionsChecked = sessionCheckboxes.some(cb => cb.checked);
            selectAllSingleSessions.checked = allSessionsChecked;
            selectAllSingleSessions.indeterminate = anySessionsChecked && !allSessionsChecked;
        }
    };

    // Legacy select all handler (selects everything)
    const selectAllHandler = (e) => {
        const isChecked = e.target.checked;
        getCheckboxes().forEach(checkbox => checkbox.checked = isChecked);
        getGroupCheckboxes().forEach(checkbox => checkbox.checked = isChecked);
        toggleDeleteButton();
    };

    // Pipeline runs select all handler
    const selectAllPipelineRunsHandler = (e) => {
        const isChecked = e.target.checked;
        getPipelineGroupCheckboxes().forEach(checkbox => checkbox.checked = isChecked);
        toggleDeleteButton();
    };

    // Single sessions select all handler
    const selectAllSingleSessionsHandler = (e) => {
        const isChecked = e.target.checked;
        getSingleSessionCheckboxes().forEach(checkbox => checkbox.checked = isChecked);
        toggleDeleteButton();
    };

    // Setup legacy select all checkbox
    let currentSelectAllCheckbox = getSelectAllCheckbox();
    if (currentSelectAllCheckbox) {
        currentSelectAllCheckbox.addEventListener('change', selectAllHandler);
    }

    // Setup pipeline runs select all checkbox
    let currentSelectAllPipelineRuns = getSelectAllPipelineRuns();
    if (currentSelectAllPipelineRuns) {
        currentSelectAllPipelineRuns.addEventListener('change', selectAllPipelineRunsHandler);
    }

    // Setup single sessions select all checkbox
    let currentSelectAllSingleSessions = getSelectAllSingleSessions();
    if (currentSelectAllSingleSessions) {
        currentSelectAllSingleSessions.addEventListener('change', selectAllSingleSessionsHandler);
    }

    listContainer.addEventListener('change', function(e) {
        if (e.target.classList.contains(itemCheckboxClass) || (itemGroupIdClass && e.target.classList.contains(itemGroupIdClass))) {
            toggleDeleteButton();
        }
    });

    deleteSelectedBtn.addEventListener('click', function() {
        const selectedItemIds = Array.from(getCheckboxes())
            .filter(cb => cb.checked)
            .map(cb => cb.dataset.runId || cb.dataset.sessionId);

        const selectedGroupIds = Array.from(getGroupCheckboxes())
            .filter(cb => cb.checked)
            .map(cb => cb.dataset.groupId);

        if (selectedItemIds.length === 0 && selectedGroupIds.length === 0) {
            return;
        }

        deleteActionCallback(selectedItemIds, selectedGroupIds);
    });

    toggleDeleteButton();

    const observer = new MutationObserver(() => {
        const allCheckboxes = Array.from(getCheckboxes()).concat(Array.from(getGroupCheckboxes()));

        // Check if legacy Select All checkbox has appeared or changed
        const newSelectAllCheckbox = getSelectAllCheckbox();
        if (newSelectAllCheckbox && newSelectAllCheckbox !== currentSelectAllCheckbox) {
            newSelectAllCheckbox.addEventListener('change', selectAllHandler);
            currentSelectAllCheckbox = newSelectAllCheckbox;
        }

        // Check if Pipeline Runs Select All checkbox has appeared or changed
        const newSelectAllPipelineRuns = getSelectAllPipelineRuns();
        if (newSelectAllPipelineRuns && newSelectAllPipelineRuns !== currentSelectAllPipelineRuns) {
            newSelectAllPipelineRuns.addEventListener('change', selectAllPipelineRunsHandler);
            currentSelectAllPipelineRuns = newSelectAllPipelineRuns;
        }

        // Check if Single Sessions Select All checkbox has appeared or changed
        const newSelectAllSingleSessions = getSelectAllSingleSessions();
        if (newSelectAllSingleSessions && newSelectAllSingleSessions !== currentSelectAllSingleSessions) {
            newSelectAllSingleSessions.addEventListener('change', selectAllSingleSessionsHandler);
            currentSelectAllSingleSessions = newSelectAllSingleSessions;
        }

        // Legacy container visibility handling
        if (currentSelectAllCheckbox) {
            const selectAllContainer = currentSelectAllCheckbox.closest('.list-group-item.bg-light');
            if (allCheckboxes.length > 0) {
                if (selectAllContainer) selectAllContainer.style.display = 'flex';
            } else {
                if (selectAllContainer) selectAllContainer.style.display = 'none';
            }
        }
        toggleDeleteButton();
    });
    observer.observe(listContainer, { childList: true, subtree: true });
};
