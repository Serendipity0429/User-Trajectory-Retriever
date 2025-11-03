
(function() {
    'use strict';

    const allowRightClick = (e) => {
        e.stopImmediatePropagation();
        return true;
    };

    const allowSelection = (e) => {
        e.stopImmediatePropagation();
        return true;
    };

    document.addEventListener('contextmenu', allowRightClick, true);
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
