// close_helper.js
window.addEventListener('message', (event) => {
    // We only accept messages from ourselves
    if (event.source !== window) {
        return;
    }

    if (event.data.type && (event.data.type === 'UTR_RESET_STATES_REQUEST')) {
        console.log('Content script received close request, relaying to background script.');
        chrome.runtime.sendMessage({command: "close_or_redirect", new_page: event.data.new_page});
    }
}, false);
