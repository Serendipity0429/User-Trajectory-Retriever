/**
 * @fileoverview content.js - Main content script for the extension.
 * Manages the lifecycle of page tracking and communication with the service worker.
 */

let lastRightClickedElement;
document.addEventListener('contextmenu', function(event) {
    lastRightClickedElement = event.composedPath?.()[0] || event.target;
    // This is necessary to bypass website restrictions that prevent the context menu.
    // It consolidates the logic that was previously conflicting in bypass.js.
    event.stopImmediatePropagation();
}, true);

async function getElementDetails() {
    let targetElement = lastRightClickedElement;
    if (!targetElement) return null;

    // If the clicked element is not an image, try to find an image within it
    if (targetElement.tagName.toUpperCase() !== 'IMG') {
        const img = targetElement.querySelector('img');
        if (img) {
            targetElement = img;
        }
    }

    const getCssSelector = (el) => {
        if (!(el instanceof Element)) return;
        const path = [];
        while (el.nodeType === Node.ELEMENT_NODE) {
            let selector = el.nodeName.toLowerCase();
            if (el.id) {
                selector += '#' + el.id;
                path.unshift(selector);
                break;
            } else {
                let sib = el, nth = 1;
                while (sib = sib.previousElementSibling) {
                    if (sib.nodeName.toLowerCase() == selector)
                       nth++;
                }
                if (nth != 1)
                    selector += ":nth-of-type(" + nth + ")";
            }
            path.unshift(selector);
            el = el.parentNode;
        }
        return path.join(" > ");
    }

    const selector = getCssSelector(targetElement);
    const tagName = targetElement.tagName;
    const attributes = {};
    for (const attr of targetElement.attributes) {
        attributes[attr.name] = attr.value;
    }

    if (tagName.toUpperCase() === 'IMG' && attributes.src) {
        const srcUrl = new URL(attributes.src, window.location.href).href;
        attributes.src = srcUrl;
        try {
            const response = await fetch(srcUrl);
            const blob = await response.blob();
            const dataUrl = await new Promise(resolve => {
                const reader = new FileReader();
                reader.onloadend = () => resolve(reader.result);
                reader.readAsDataURL(blob);
            });
            attributes.imageData = dataUrl; // Add base64 image data
        } catch (e) {
            console.error("Could not fetch image for evidence:", e);
        }
    }

    return { selector, tagName, attributes };
}

const MSG_TYPE_POPUP = "msg_from_popup";

let _content_vars = {
    url_now: window.location.href,
    referrer_now: document.referrer,
    is_task_active: false,
};

let questionBoxMousemoveListener = null;

async function displayQuestionBox(question) {
    if (!question) return;

    const innerHTML = `
        <h5 style="font-size: 1.2em; margin-bottom: 0.5em; margin-top: 0;"><strong>Task Question</strong></h5>
        <p style="font-size: 1.0em; margin-bottom: 0; margin-top:0;">${question}</p>
        <div id="evidence-count-container" style="margin-top: 10px; font-size: 0.9em; color: #58595a;">
            Evidence Collected: <span id="evidence-count">0</span>
        </div>
    `;

    const css = `
        max-width: 25vw;
        min-height: 5rem;
        line-height: 1.5;
        transition: opacity 0.3s ease-in-out;
    `;

    const options = {
        innerHTML,
        type: 'info',
        duration: 0, // Persists until manually removed
        id: 'task-question-box',
        css,
    };
    await displayMessageBox(options);

    const box = document.getElementById('task-question-box');
    if (box) {
        box.style.pointerEvents = 'none';
        box.style.opacity = '0.9';
        
        questionBoxMousemoveListener = (e) => {
            const rect = box.getBoundingClientRect();
            if (e.clientX >= rect.left && e.clientX <= rect.right && e.clientY >= rect.top && e.clientY <= rect.bottom) {
                box.style.opacity = '0';
            } else {
                box.style.opacity = '0.9';
            }
        };
        document.addEventListener('mousemove', questionBoxMousemoveListener);
    }

    updateEvidenceCount();
}

async function updateEvidenceCount() {
    const task_id = await new Promise((resolve) => {
        chrome.runtime.sendMessage({ type: MSG_TYPE_POPUP, command: "get_active_task" }, (response) => {
            resolve(response ? response.task_id : -1);
        });
    });

    if (task_id !== -1) {
        chrome.runtime.sendMessage({ command: "get_justifications", task_id: task_id }, (response) => {
            const countEl = document.getElementById('evidence-count');
            if (countEl && response && response.justifications) {
                countEl.textContent = response.justifications.length;
            }
        });
    }
}

async function getTaskInfo() {
    return new Promise((resolve, reject) => {
        chrome.runtime.sendMessage({ type: MSG_TYPE_POPUP, command: "get_task_info" }, async function (response) {
            if (chrome.runtime.lastError) {
                console.error("Error getting task info:", chrome.runtime.lastError.message);
                return reject(chrome.runtime.lastError);
            }
            if (response && response.question) {
                await displayQuestionBox(response.question);
            }
            resolve();
        });
    });
}

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

function removeExistingBoxes() {
    if (questionBoxMousemoveListener) {
        document.removeEventListener('mousemove', questionBoxMousemoveListener);
        questionBoxMousemoveListener = null;
    }
    const questionBox = document.getElementById('task-question-box');
    if (questionBox) {
        questionBox.remove();
    }
    const loadedBoxes = document.querySelectorAll('.loaded-box');
    loadedBoxes.forEach(box => box.remove());
}

async function setupTaskUI() {
    removeExistingBoxes();
    await getTaskInfo();
    if (!_is_server_page(_content_vars.url_now)) {
        displayMessageBox({ message: "You can start your task now!" });
    }
}

async function getSessionDataFromBackground(key) {
    return new Promise((resolve) => {
        chrome.runtime.sendMessage({ command: 'get_session_data', key }, (response) => {
            resolve(response || {});
        });
    });
}

async function initialize() {
    if (window.self !== window.top) {
        // Not in the top frame, don't run initialization
        return;
    }
    try {
        await initializeConfig(); // Ensure config is loaded before proceeding

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
                setTimeout(async () => {
                    if (_content_vars.url_now !== window.location.href) {
                        _content_vars.referrer_now = _content_vars.url_now;
                        _content_vars.url_now = window.location.href;
                        viewState.flush();
                        await updateTaskStatus();
                        if (getTaskStatus()) {
                            setupTaskUI();
                        }
                        printDebug("content", "URL changed (pushState), re-initializing UI.");
                    }
                }, 0);
            };

            history.replaceState = function (...args) {
                replaceState.apply(history, args);
                setTimeout(async () => {
                    if (_content_vars.url_now !== window.location.href) {
                        _content_vars.referrer_now = _content_vars.url_now;
                        _content_vars.url_now = window.location.href;
                        viewState.flush();
                        await updateTaskStatus();
                        if (getTaskStatus()) {
                            setupTaskUI();
                        }
                        printDebug("content", "URL changed (replaceState), re-initializing UI.");
                    }
                }, 0);
            };
        })(window.history);

        viewState.initialize();

        if (!_is_server_page(_content_vars.url_now)) {
            const { is_recording_paused } = await getSessionDataFromBackground('is_recording_paused');

            if (is_recording_paused) {
                displayMessageBox({
                    title: "Recording Paused",
                    message: "You have a pending annotation.\nPlease open the popup to complete it.",
                    type: "warning",
                    id: "server-pending-annotation-message",
                    duration: 3000
                });
                printDebug("content", "Pending annotation message displayed.");
            }

            rrweb.record({
                emit(event) {
                    unitPage.addRRWebEvent(event);
                },
                recordCrossOriginIframes: true, // NOTICE: enable cross-origin iframe recording, which is under experimental stage
                recordCanvas: true, // NOTICE: enable canvas recording, which is under experimental stage
                // inlineImages: true, // NOTICE: enable image inlining to capture images as base64
                collectFonts: true, // NOTICE: enable font collection to capture custom fonts
            });
            printDebug("content", "rrweb recording started.");
        }
            
        printDebug("content", "content.js is loaded");
        await setupTaskUI();
        } catch (error) {
        console.error("Error during main initialization:", error);
    }
}

// --- Event Listeners ---

document.addEventListener("DOMContentLoaded", initialize);

window.addEventListener('popstate', async () => {
    await initializeConfig(); // Ensure config is loaded
    if (_content_vars.url_now !== window.location.href) {
        _content_vars.referrer_now = _content_vars.url_now;
        _content_vars.url_now = window.location.href;
        viewState.flush();
        await updateTaskStatus();
        if (getTaskStatus()) {
            setupTaskUI();
        }
        printDebug("content", "URL changed (popstate), re-initializing UI.");
    }
});

window.addEventListener('message', (event) => {
    // Check if the message is from an iframe and is an rrweb event
    if (event.source !== window && event.data && event.data.type) {
        unitPage.addRRWebEvent(event.data);
    }
});

chrome.runtime.onMessage.addListener(function (message, sender, sendResponse) {
    // Handle messages from the background script
    if (message.command === 'get-element-details') {
        (async () => {
            const details = await getElementDetails();
            sendResponse(details);
        })();
        return true; // Keep channel open for async response
    }

    if (message.command === 'remove_message_box') {
        removeMessageBox(message.id);
        sendResponse({success: true});
        return true;
    }

    if (message.command === 'display_message') {
        displayMessageBox(message.options);
        sendResponse({success: true});
        return true;
    }

    if (message.command === 'evidence-added-successfully') {
        displayMessageBox({ message: "Evidence added successfully!" });
        const countEl = document.getElementById('evidence-count');
        if (countEl && typeof message.newCount !== 'undefined') {
            countEl.textContent = message.newCount;
        }
        sendResponse({success: true});
        return true;
    }

    if (message.command === 'refresh_justifications') {
        window.postMessage({ type: 'refresh_justifications' }, '*');
        sendResponse({success: true});
        return true;
    }

    if (message.command === 'update_evidence_count') {
        const countEl = document.getElementById('evidence-count');
        if (countEl && typeof message.count !== 'undefined') {
            countEl.textContent = message.count;
        }
        sendResponse({success: true});
        return true;
    }

    // Handle messages from the popup
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

    if (message.type === 'update_message_box_style') {
        applyMessageBoxStyle(message.style);
        sendResponse({success: true});
        return true;
    }
});

function applyMessageBoxStyle(style) {
    const questionBox = document.getElementById('task-question-box');
    if (questionBox) {
        const sizeMap = {
            small: { width: '15vw', minHeight: '10vh', fontSize: '0.8vw', maxWidth: 'none' },
            medium: { width: '22.5vw', minHeight: '15vh', fontSize: '1.2vw', maxWidth: 'none' },
            large: { width: '30vw', minHeight: '20vh', fontSize: '1.6vw', maxWidth: 'none' }
        };

        const positionMap = {
            'top-left': { top: '10px', left: '10px', right: 'auto', bottom: 'auto', transform: 'none' },
            'top-center': { top: '10px', left: '50%', right: 'auto', bottom: 'auto', transform: 'translateX(-50%)' },
            'top-right': { top: '10px', right: '10px', left: 'auto', bottom: 'auto', transform: 'none' },
            'middle-left': { top: '50%', left: '10px', right: 'auto', bottom: 'auto', transform: 'translateY(-50%)' },
            'middle-center': { top: '50%', left: '50%', right: 'auto', bottom: 'auto', transform: 'translate(-50%, -50%)' },
            'middle-right': { top: '50%', right: '10px', left: 'auto', bottom: 'auto', transform: 'translateY(-50%)' },
            'bottom-left': { bottom: '10px', left: '10px', top: 'auto', right: 'auto', transform: 'none' },
            'bottom-center': { bottom: '10px', left: '50%', top: 'auto', right: 'auto', transform: 'translateX(-50%)' },
            'bottom-right': { bottom: '10px', right: '10px', top: 'auto', left: 'auto', transform: 'none' }
        };

        if (style.size && sizeMap[style.size]) {
            Object.assign(questionBox.style, sizeMap[style.size]);
        }

        if (style.position && positionMap[style.position]) {
            Object.assign(questionBox.style, positionMap[style.position]);
        }
    }
}
