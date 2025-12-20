/**
 * @fileoverview content.js - Main content script for the extension.
 * Manages the lifecycle of page tracking and communication with the service worker.
 */

let lastRightClickedElement;
document.addEventListener('contextmenu', function(event) {
    if (!_content_vars.is_task_active) {
        return;
    }
    lastRightClickedElement = event.composedPath?.()[0] || event.target;
    // This is necessary to bypass website restrictions that prevent the context menu.
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



function addPulseAnimation() {
    const styleId = 'pulsing-dot-animation';
    if (document.getElementById(styleId)) {
        return;
    }
    const style = document.createElement('style');
    style.id = styleId;
    style.innerHTML = `
        @keyframes pulse {
            0% {
                transform: scale(0.95);
                box-shadow: 0 0 0 0 rgba(229, 57, 53, 0.7);
            }
            70% {
                transform: scale(1);
                box-shadow: 0 0 0 10px rgba(229, 57, 53, 0);
            }
            100% {
                transform: scale(0.95);
                box-shadow: 0 0 0 0 rgba(229, 57, 53, 0);
            }
        }
        .recording-indicator-dot {
            width: 8px;
            height: 8px;
            background-color: #e53935;
            border-radius: 50%;
            animation: pulse 2s infinite;
            box-shadow: 0 0 0 0 rgba(229, 57, 53, 1);
        }
    `;
    document.head.appendChild(style);
}

function escapeHTML(str) {
    if (!str) return '';
    return str.replace(/[&<>'"]/g, 
        tag => ({
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            "'": '&#39;',
            '"': '&quot;'
        }[tag]));
}

async function displayQuestionBox(question) {
    if (!question) return;

    addPulseAnimation();

    const safeQuestion = escapeHTML(question);

    const innerHTML = `
        <h5 style="font-size: 1.2em; margin-bottom: 0.5em; margin-top: 0; display: flex; justify-content: space-between; align-items: flex-start;">
            <strong style="color: #333;">Task Question</strong>
            <span style="display: flex; align-items: center; gap: 5px; font-size: 0.8em;">
                <span style="color: #e53935;">Recording</span>
                <span class="recording-indicator-dot"></span>
            </span>
        </h5>
        <p style="font-size: 1.1em; font-weight: 500; margin-bottom: 0; margin-top:0; color:#021e4d"><strong>${safeQuestion}</strong></p>
        <p style="font-size: 0.9em; font-style: italic; margin-top: 10px; color: #555;">Use the right-click menu to mark evidence.</p>
        <div id="evidence-count-container" style="margin-top: 10px; font-size: 0.9em; color: #58595a;">
            Evidence Collected: <span id="evidence-count">0</span>
        </div>
    `;

    const css = `
        line-height: 1.5;
        transition: opacity 0.3s ease-in-out;
    `;

    const options = {
        innerHTML,
        type: 'info',
        duration: 0, // Persists until manually removed
        id: 'task-question-box',
        css,
        hoverable: true, // Explicitly enable hover effect
    };
    await displayMessageBox(options);

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
    const questionBox = document.getElementById('task-question-box');
    if (questionBox) {
        if (typeof hoverableMessageBoxManager !== 'undefined') {
            hoverableMessageBoxManager.remove(questionBox);
        }
        questionBox.remove();
    }
    const loadedBoxes = document.querySelectorAll('.loaded-box');
    loadedBoxes.forEach(box => {
        if (box.id !== 'task-question-box') {
            box.remove();
        }
    });
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

        const checkLoginStatus = () => new Promise((resolve, reject) => {
            chrome.runtime.sendMessage({ type: MSG_TYPE_POPUP, command: "check_logging_status" }, (response) => {
                if (chrome.runtime.lastError) {
                    return reject(chrome.runtime.lastError);
                }
                resolve(response);
            });
        });

        const login_response = await withRetry(checkLoginStatus, 100);

        if (!login_response || !login_response.log_status) {
            printDebug("content", "User is not logged in. Exiting content script.");
            unblockInteractions();
            return;
        }

        await withRetry(updateTaskStatus, 100);

        if (!getTaskStatus()) {
            printDebug("content", "No active task. Exiting content script.");
            unblockInteractions();
            return;
        }

        // Ensure blocking is active
        blockInteractions();

        // // Wait a bit for the page to stabilize (frameworks hydration, etc.)
        await new Promise(resolve => setTimeout(resolve, 500) );

        unblockInteractions();
        viewState.initialize();

        if (!_is_server_page(_content_vars.url_now)) {
            const { has_pending_annotation } = await getSessionDataFromBackground('has_pending_annotation');

            if (has_pending_annotation) {
                displayMessageBox({
                    title: "Recording Paused",
                    message: "You have a pending annotation.\nPlease open the popup to complete it.",
                    type: "warning",
                    id: "server-pending-annotation-message",
                    duration: 3000
                });
                printDebug("content", "Pending annotation message displayed.");
            }
        }

        printDebug("content", "content.js is loaded");
        await setupTaskUI();
    } catch (error) {
        console.error("Error during main initialization:", error);
        unblockInteractions();
    }
}

// --- Event Listeners ---
// if (document.readyState === 'complete') {
//     initialize();
// } else {
//     window.addEventListener("load", initialize);
// }

if (document.readyState == 'interactive' || document.readyState == 'complete') {
    initialize();
} else {
    window.addEventListener("DOMContentLoaded", initialize);
}




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

    if (message.command === 'web_navigation_updated') {
        if (_content_vars.url_now !== message.url) {
            _content_vars.referrer_now = _content_vars.url_now;
            _content_vars.url_now = message.url;
            viewState.flush();
            (async () => {
                await updateTaskStatus();
                if (getTaskStatus()) {
                    setupTaskUI();
                }
            })();
            printDebug("content", "URL changed (web_navigation_updated), re-initializing UI.");
        }
        sendResponse({ success: true });
        return true;
    }

    if (message.command === 'refresh_task_status') {
        printDebug("content", "Received refresh_task_status message.");
        (async () => {
            try {
                await updateTaskStatus();
                if (getTaskStatus()) {
                    setupTaskUI();
                } else {
                    removeExistingBoxes();
                }
            } catch (e) {
                console.error("Error handling refresh_task_status:", e);
            }
        })();
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
        // Handle size
        if (style.size) {
            questionBox.classList.remove('size-small', 'size-medium', 'size-large');
            questionBox.classList.add(`size-${style.size}`);
        }

        // Handle position
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

        if (style.position && positionMap[style.position]) {
            Object.assign(questionBox.style, positionMap[style.position]);
        }
    }
}

// --- Interaction Blocking Logic ---
function blockInteractions() {
    if (document.getElementById('utrt-interaction-blocker')) return;
    
    const blocker = document.createElement('div');
    blocker.id = 'utrt-interaction-blocker';
    blocker.classList.add('rr-block', 'rr-ignore');
    
    // Create style for the spinner and overlay
    const style = document.createElement('style');
    style.textContent = `
        #utrt-interaction-blocker {
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            z-index: 2147483647;
            background: rgba(255, 255, 255, 0.9);
            backdrop-filter: blur(2px);
            cursor: wait;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            color: #2c3e50;
            transition: opacity 0.3s ease;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        .utrt-spinner {
            width: 50px;
            height: 50px;
            border: 4px solid #e0e0e0;
            border-top: 4px solid #3498db;
            border-radius: 50%;
            animation: utrt-spin 1s cubic-bezier(0.68, -0.55, 0.27, 1.55) infinite; /* Bouncy spin */
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        @keyframes utrt-spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .utrt-message {
            font-size: 18px;
            font-weight: 600;
            letter-spacing: 0.5px;
            text-align: center;
            padding: 0 20px;
            animation: utrt-pulse 2s infinite ease-in-out;
        }
        @keyframes utrt-pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.7; }
        }
    `;
    
    blocker.appendChild(style);

    const spinner = document.createElement('div');
    spinner.className = 'utrt-spinner';
    blocker.appendChild(spinner);

    const message = document.createElement('div');
    message.className = 'utrt-message';
    message.textContent = 'Initializing Recorder... Please Wait';
    blocker.appendChild(message);
    
    if (document.body) document.body.appendChild(blocker);
    else if (document.documentElement) document.documentElement.appendChild(blocker);
}

function unblockInteractions() {
    const blocker = document.getElementById('utrt-interaction-blocker');
    if (blocker) blocker.remove();
}

// Immediate check on script load
(async () => {
    try {
        await initializeConfig();
        await updateTaskStatus();
        if (getTaskStatus()) {
            blockInteractions();
        }
    } catch (e) {
        // console.error("Error in immediate task status check:", e);
    }
})();
