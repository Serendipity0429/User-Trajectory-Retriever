/**
 * @fileoverview content.js - Main content script for the extension.
 * Manages the lifecycle of page tracking and communication with the service worker.
 */


let _content_vars = {
    url_now: window.location.href,
    referrer_now: document.referrer,
    is_task_active: false,
};

// Check whether there is an active task
function updateTaskStatus() {
    printDebug("Checking if task is active...");
    return new Promise((resolve, reject) => {
        chrome.runtime.sendMessage({ type: "msg_from_popup", command: "get_active_task" }, function (response) {
            if (chrome.runtime.lastError) {
                console.error("Error checking task status:", chrome.runtime.lastError.message);
                _content_vars.is_task_active = false; // Assume no task if communication fails
                return reject(chrome.runtime.lastError);
            }
            if (response) {
                _content_vars.is_task_active = response.is_task_active;
                printDebug(`Task ID: ${response.task_id} (Active: ${_content_vars.is_task_active})`);
            }
            resolve();
        });
    });
}

function getTaskStatus() {
    return _content_vars.is_task_active;
}


// Initial check when the script loads
updateTaskStatus();

window.addEventListener('popstate', () => {
    if (_content_vars.url_now !== window.location.href) {
        _content_vars.referrer_now = _content_vars.url_now;
        _content_vars.url_now = window.location.href;
        viewState.flush();
        printDebug("URL changed (popstate), re-initializing.");
    }
});

// Main initialization logic
// MV3-FIX: Updated message format to match background.js listener
async function main() {
    // try {
    const login_response = await new Promise((resolve, reject) => {
        chrome.runtime.sendMessage({ type: "msg_from_popup", command: "check_logging_status" }, (response) => {
            if (chrome.runtime.lastError) {
                return reject(chrome.runtime.lastError);
            }
            resolve(response);
        });
    });

    if (login_response && login_response.log_status) {
        printDebug("User is logged in.");

        // Wait for the task status to be updated first.
        await updateTaskStatus();

        // If there is no active task, do not initialize further.
        if (!getTaskStatus()) {
            printDebug("No active task. Exiting content script.");
            return;
        }

        // Monkey-patch history API to detect SPA navigations
        (function (history) {
            const pushState = history.pushState;
            const replaceState = history.replaceState;

            history.pushState = function (...args) {
                if (typeof history.onpushstate == "function") {
                    history.onpushstate({ state: args[0] });
                }
                // NOTICE: Use a timeout to allow the URL to update before we check it
                setTimeout(() => {
                    if (_content_vars.url_now !== window.location.href) {
                        _content_vars.referrer_now = _content_vars.url_now;
                        _content_vars.url_now = window.location.href;
                        viewState.flush();
                        printDebug("URL changed (pushState), re-initializing.");
                    }
                }, 0);
                return pushState.apply(history, args);
            };

            history.replaceState = function (...args) {
                if (typeof history.onreplacestate == "function") {
                    history.onreplacestate({ state: args[0] });
                }
                setTimeout(() => {
                    if (_content_vars.url_now !== window.location.href) {
                        _content_vars.referrer_now = _content_vars.url_now;
                        _content_vars.url_now = window.location.href;
                        viewState.flush();
                        printDebug("URL changed (replaceState), re-initializing.");
                    }
                }, 0);
                return replaceState.apply(history, args);
            };
        })(window.history);


        // Initialize all modules
        viewState.initialize();
        event_tracker.initialize();

        updateTaskStatus();

        if (!_is_server_page(_content_vars.url_now)) {
            printDebug("User is logged in.");
            viewState.initialize();
            rrweb.record({
                emit(event) {
                    unitPage.addRRWebEvent(event);
                },
            });
            printDebug("rrweb recording started.");

            if (_content_vars.is_task_active) {
                displayLoadedBox("Start Recording");
                printDebug("Start Recording");
            }
        }
    }
    // } catch (error) {
    //     console.error("Error during main initialization:", error);
    // }
}

// Start the initialization process once the DOM is ready
document.addEventListener("DOMContentLoaded", main);

chrome.runtime.onMessage.addListener(function (message, sender, sendResponse) {
    if (message.type === "msg_from_popup") {
        if (document.visibilityState === 'hidden') {
            printDebug("Page is hidden, not responding to popup.");
            // Optionally send a response indicating the page is hidden
            sendResponse({ success: false });
        } else {
            if (message.update_webpage_info) {
                printDebug("Received update_webpage_info message from popup.");
                viewState.sent_when_active = true;
                viewState.flush();
            }
            sendResponse({ success: true });
        }
    }
});



// Main body
printDebug("content.js is loaded");