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
