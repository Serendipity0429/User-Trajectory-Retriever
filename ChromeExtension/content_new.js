let currentUrl = window.location.href;
let currentReferrer = document.referrer;
let currentSerpLink = "";
let isTaskActive = false;

// Check for active task
function checkIsTaskActive() {
    chrome.runtime.sendMessage({task_active: "request"}, response => {
        isTaskActive = response.task_active;
        console.log("Task is active: " + isTaskActive);
    });
}

// Store link information
function storeLink() {
    const serpMatch = currentReferrer.match(/www\.(baidu|sogou|so)\.com\/(s|web)/);

    if (serpMatch) {
        currentSerpLink = currentUrl;
        chrome.runtime.sendMessage({
            link_store: "request",
            url: currentUrl,
            serp_link: currentSerpLink
        });
    } else {
        chrome.runtime.sendMessage({ref_request: currentReferrer}, response => {
            currentSerpLink = response;
            if (currentSerpLink) {
                chrome.runtime.sendMessage({
                    link_store: "request",
                    url: currentUrl,
                    serp_link: currentSerpLink
                });
            }
        });
    }
}

// Initialize page tracking
function initializeTracking() {
    viewState.initialize();
    rrweb.record({
        emit(event) {
            mPage.addRRWebEvent(event);
        }
    });

    // Watch for URL changes
    new MutationObserver(mutations => {
        if (currentUrl !== window.location.href) {
            viewState.sendMessage();
            currentReferrer = currentUrl;
            currentUrl = window.location.href;
            storeLink();
            viewState.initialize();
            mPage.rrweb_events = []; // Clear rrweb events
            rrweb.record.takeFullSnapshot();
        } else {
            viewState.update();
        }
    }).observe(document.body, {childList: true, subtree: true, attributes: true});
}

// Main initialization
checkIsTaskActive();
chrome.runtime.sendMessage({log_status: "request"}, response => {
    if (currentUrl.substring(0, 22) !== "http://127.0.0.1:8000/" && response.log_status) {
        storeLink();
        initializeTracking();
    }
});

// Handle messages from popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.type === "msg_from_popup" && request.update_webpage_info) {
        viewState.sendMessage();
    }
});