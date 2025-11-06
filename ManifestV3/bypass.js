
// Note: The 'contextmenu' event listener has been moved to content.js.
// This was done to resolve a conflict and consolidate the logic for capturing
// the right-clicked element and bypassing website restrictions in one place.
(async function() {
    'use strict';

    const taskStatusResponse = await new Promise((resolve) => {
        chrome.runtime.sendMessage({ command: "get_active_task" }, (response) => {
            if (chrome.runtime.lastError) {
                resolve(null);
                return;
            }
            resolve(response);
        });
    });

    const is_task_active = taskStatusResponse ? taskStatusResponse.is_task_active : false;

    if (!is_task_active) {
        return;
    }

    const allowSelection = (e) => {
        e.stopImmediatePropagation();
        return true;
    };

    document.addEventListener('selectstart', allowSelection, true);
    document.addEventListener('mousedown', allowSelection, true);

    // Function to add the style
    const addStyle = () => {
        // Re-enable CSS user-select
        const style = document.createElement('style');
        style.innerHTML = '*, *::before, *::after { user-select: auto !important; -webkit-user-select: auto !important; }';
        
        // Ensure head exists before appending
        if (document.head) {
            document.head.appendChild(style);
        } else {
            // If head is not available, wait for it
            const observer = new MutationObserver(() => {
                if (document.head) {
                    document.head.appendChild(style);
                    observer.disconnect();
                }
            });
            observer.observe(document.documentElement, { childList: true });
        }
    };

    // Check if the DOM is already loaded
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', addStyle);
    } else {
        addStyle();
    }

})();
