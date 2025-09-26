/**
 * @fileoverview content.js - Main content script for the extension.
 * Manages the lifecycle of page tracking and communication with the service worker.
 */

const MSG_TYPE_POPUP = "msg_from_popup";

let _content_vars = {
    url_now: window.location.href,
    referrer_now: document.referrer,
    is_task_active: false,
};

function updateTaskStatus() {
    printDebug("content", "Checking if task is active...");
    return new Promise((resolve, reject) => {
        chrome.runtime.sendMessage({ type: MSG_TYPE_POPUP, command: "get_active_task" }, function (response) {
            if (chrome.runtime.lastError) {
                console.error("Error checking task status:", chrome.runtime.lastError.message);
                _content_vars.is_task_active = false;
                return reject(chrome.runtime.lastError);
            }
            if (response) {
                _content_vars.is_task_active = response.is_task_active;
                printDebug("content", `Task ID: ${response.task_id} (Active: ${_content_vars.is_task_active})`);
            }
            resolve();
        });
    });
}

function getTaskStatus() {
    return _content_vars.is_task_active;
}

async function initialize() {
    try {
        const login_response = await new Promise((resolve, reject) => {
            chrome.runtime.sendMessage({ type: MSG_TYPE_POPUP, command: "check_logging_status" }, (response) => {
                if (chrome.runtime.lastError) {
                    return reject(chrome.runtime.lastError);
                }
                resolve(response);
            });
        });

        if (!login_response || !login_response.log_status) {
            printDebug("content", "User is not logged in. Exiting content script.");
            return;
        }

        await updateTaskStatus();

        if (!getTaskStatus()) {
            printDebug("content", "No active task. Exiting content script.");
            return;
        }

        // Monkey-patch history API for SPA navigation tracking
        (function (history) {
            const { pushState, replaceState } = history;

            history.pushState = function (...args) {
                pushState.apply(history, args);
                setTimeout(() => {
                    if (_content_vars.url_now !== window.location.href) {
                        _content_vars.referrer_now = _content_vars.url_now;
                        _content_vars.url_now = window.location.href;
                        viewState.flush();
                        printDebug("content", "URL changed (pushState), re-initializing.");
                    }
                }, 0);
            };

            history.replaceState = function (...args) {
                replaceState.apply(history, args);
                setTimeout(() => {
                    if (_content_vars.url_now !== window.location.href) {
                        _content_vars.referrer_now = _content_vars.url_now;
                        _content_vars.url_now = window.location.href;
                        viewState.flush();
                        printDebug("content", "URL changed (replaceState), re-initializing.");
                    }
                }, 0);
            };
        })(window.history);

        viewState.initialize();
        event_tracker.initialize();

        if (!_is_server_page(_content_vars.url_now)) {
            rrweb.record({
                emit(event) {
                    unitPage.addRRWebEvent(event);
                },
            });
            printDebug("content", "rrweb recording started.");
            displayLoadedBox("Start Recording");
        }

    } catch (error) {
        console.error("Error during main initialization:", error);
    }
}

// --- Event Listeners ---

document.addEventListener("DOMContentLoaded", initialize);

window.addEventListener('popstate', () => {
    if (_content_vars.url_now !== window.location.href) {
        _content_vars.referrer_now = _content_vars.url_now;
        _content_vars.url_now = window.location.href;
        viewState.flush();
        printDebug("content", "URL changed (popstate), re-initializing.");
    }
});

chrome.runtime.onMessage.addListener(function (message, sender, sendResponse) {
    if (message.type === MSG_TYPE_POPUP) {
        if (document.visibilityState === 'hidden') {
            printDebug("content", "Page is hidden, not responding to popup.");
            sendResponse({ success: false });
        } else {
            if (message.update_webpage_info) {
                printDebug("content", "Received update_webpage_info message from popup.");
                viewState.sent_when_active = true;
                viewState.flush();
            }
            sendResponse({ success: true });
        }
    }
});

printDebug("content", "content.js is loaded");