/**
 * Batch selection utilities for list items with checkboxes
 * Handles select all, individual selection, and batch delete operations
 */

window.BenchmarkBatchSelection = window.BenchmarkBatchSelection || {};

/**
 * Sets up batch selection logic for a list of items with checkboxes.
 * @param {string} listContainerId - ID of the container holding all selectable items.
 * @param {string} selectAllCheckboxId - ID of the 'Select All' checkbox.
 * @param {string} itemCheckboxClass - Class name for individual item checkboxes.
 * @param {string} deleteButtonId - ID of the button that performs batch deletion.
 * @param {function} deleteActionCallback - Function to call when the delete button is clicked. Receives an array of selected item IDs and selected group IDs.
 * @param {string} [itemGroupIdClass] - Optional: Class name for item group checkboxes (e.g., for multi-turn sessions).
 */
window.BenchmarkBatchSelection.setup = function(listContainerId, selectAllCheckboxId, itemCheckboxClass, deleteButtonId, deleteActionCallback, itemGroupIdClass = null) {
    const listContainer = document.getElementById(listContainerId);
    const deleteSelectedBtn = document.getElementById(deleteButtonId);

    if (!listContainer || !deleteSelectedBtn) return;

    const getSelectAllCheckbox = () => document.getElementById(selectAllCheckboxId);
    const getCheckboxes = () => listContainer.querySelectorAll(`.${itemCheckboxClass}`);
    const getGroupCheckboxes = () => itemGroupIdClass ? listContainer.querySelectorAll(`.${itemGroupIdClass}`) : [];

    const toggleDeleteButton = () => {
        const anyItemChecked = Array.from(getCheckboxes()).some(cb => cb.checked);
        const anyGroupChecked = Array.from(getGroupCheckboxes()).some(cb => cb.checked);
        const anyChecked = anyItemChecked || anyGroupChecked;
        deleteSelectedBtn.style.display = anyChecked ? 'inline-block' : 'none';

        const selectAllCheckbox = getSelectAllCheckbox();
        if (selectAllCheckbox) {
            const allCheckboxes = Array.from(getCheckboxes()).concat(Array.from(getGroupCheckboxes()));
            const allChecked = allCheckboxes.length > 0 && allCheckboxes.every(cb => cb.checked);
            selectAllCheckbox.checked = anyChecked && allChecked;
        }
    };

    const selectAllHandler = (e) => {
        const isChecked = e.target.checked;
        getCheckboxes().forEach(checkbox => checkbox.checked = isChecked);
        getGroupCheckboxes().forEach(checkbox => checkbox.checked = isChecked);
        toggleDeleteButton();
    };

    let currentSelectAllCheckbox = getSelectAllCheckbox();
    if (currentSelectAllCheckbox) {
        currentSelectAllCheckbox.addEventListener('change', selectAllHandler);
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

        // Check if Select All checkbox has appeared or changed
        const newSelectAllCheckbox = getSelectAllCheckbox();
        if (newSelectAllCheckbox && newSelectAllCheckbox !== currentSelectAllCheckbox) {
            newSelectAllCheckbox.addEventListener('change', selectAllHandler);
            currentSelectAllCheckbox = newSelectAllCheckbox;
        }

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

/**
 * Load saved runs and populate the list.
 * @param {string} listUrl - URL to list runs.
 * @param {function} loadRunCallback - Function to call when a run is clicked.
 * @param {function} deleteRunCallback - Function to call when delete is clicked.
 * @param {string} listId - ID of the list element.
 * @param {string} noRunsId - ID of the no runs message element.
 * @param {boolean} enableSelection - Whether to render checkboxes for batch selection.
 * @param {function} onSelectionChange - Callback when selection changes (checkbox clicked).
 */
window.BenchmarkBatchSelection.loadSavedRuns = function(listUrl, loadRunCallback, deleteRunCallback, listId = 'saved-runs-list', noRunsId = 'no-runs-message', enableSelection = false, onSelectionChange = null) {
    const savedRunsList = document.getElementById(listId);
    const noRunsMessage = document.getElementById(noRunsId);
    savedRunsList.innerHTML = '';

    fetch(listUrl)
        .then(response => response.json())
        .then(data => {
            if (data.runs && data.runs.length > 0) {
                noRunsMessage.style.display = 'none';
                savedRunsList.style.display = 'block';

                // Add Select All Container if enabled
                if (enableSelection) {
                    const selectAllContainer = document.createElement('div');
                    selectAllContainer.className = 'list-group-item bg-light d-flex align-items-center';
                    selectAllContainer.innerHTML = `
                        <input class="form-check-input me-3" type="checkbox" id="select-all-checkbox">
                        <label class="form-check-label fw-bold" for="select-all-checkbox">Select All</label>
                    `;
                    savedRunsList.appendChild(selectAllContainer);
                }

                data.runs.forEach(run => {
                    const runItem = document.createElement('div');
                    runItem.className = 'list-group-item list-group-item-action d-flex align-items-center';

                    // Checkbox (if enabled)
                    if (enableSelection) {
                        const checkbox = document.createElement('input');
                        checkbox.type = 'checkbox';
                        checkbox.className = 'form-check-input me-3 run-checkbox';
                        checkbox.value = run.id;
                        checkbox.dataset.runId = run.id;
                        checkbox.onclick = (e) => {
                            e.stopPropagation();
                            if (onSelectionChange) onSelectionChange();
                        };
                        runItem.appendChild(checkbox);
                    }

                    const runNameContainer = document.createElement('div');
                    runNameContainer.style.cursor = 'pointer';
                    runNameContainer.className = 'flex-grow-1';
                    runNameContainer.onclick = () => loadRunCallback(run.id);

                    const runName = document.createElement('span');
                    runName.textContent = run.name;
                    runNameContainer.appendChild(runName);

                    const deleteBtn = document.createElement('button');
                    deleteBtn.className = 'btn btn-sm btn-outline-danger ms-2';
                    deleteBtn.innerHTML = '<i class="bi bi-trash"></i>';
                    deleteBtn.title = 'Delete run';
                    deleteBtn.onclick = (e) => {
                        e.stopPropagation();
                        deleteRunCallback(run.id);
                    };

                    runItem.appendChild(runNameContainer);
                    runItem.appendChild(deleteBtn);
                    savedRunsList.appendChild(runItem);
                });
            } else {
                noRunsMessage.style.display = 'block';
                savedRunsList.style.display = 'none';
            }
        });
};

/**
 * Delete a run.
 * @param {string} url - URL to delete the run.
 * @param {string} csrfToken - CSRF token.
 */
window.BenchmarkBatchSelection.deleteRun = function(url, csrfToken) {
    if (!confirm('Are you sure you want to delete this run? This action cannot be undone.')) {
        return;
    }

    fetch(url, {
        method: 'DELETE',
        headers: { 'X-CSRFToken': csrfToken }
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'ok') {
            window.location.reload();
        } else {
            alert('Error deleting run: ' + (data.message || 'Unknown error'));
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('An network error occurred while deleting the run.');
    });
};
