// background.js
// This script runs in the background and handles communication between content scripts and the server

// Import config variables and utility functions
importScripts('./utils.js', './config.js');

// --- Constants ---
const TASK_STORAGE_KEY = 'current_task_id';
const TASK_INFO_KEY = 'current_task_info';

const ALARM_CLEAR_STORAGE = 'clear_local_storage';
const ALARM_CHECK_TASK = 'check_active_task';
const ALARM_UPDATE_EVIDENCE_COUNT = 'update_evidence_count';

const MSG_CHECK_LOGGING_STATUS = 'check_logging_status';
const MSG_ALTER_LOGGING_STATUS = 'alter_logging_status';
const MSG_INJECT_SCRIPT = 'inject_script';
const MSG_SEND_MESSAGE = 'send_message';
const MSG_GET_ACTIVE_TASK = 'get_active_task';
const MSG_GET_TASK_INFO = 'get_task_info';
const MSG_GET_JUSTIFICATIONS = 'get_justifications';
const MSG_GET_POPUP_DATA = 'get_popup_data';

let isConnected = true;

(async () => {
    await initializeConfig();

})();

// --- State Management ---

async function getCurrentTask() {
    const result = await _get_session(TASK_STORAGE_KEY);
    return result[TASK_STORAGE_KEY] || -1;
}

async function setCurrentTask(task_id) {
    if (task_id === -1) {
        await _remove_session(TASK_INFO_KEY);
    }
    return await _set_session({ [TASK_STORAGE_KEY]: task_id });
}

// SECURITY: Avoid storing passwords in local storage.
// The 'password' field has been removed.
async function getUserInfo() {
    const { username, access_token, refresh_token, logged_in } = await _get_session(['username', 'access_token', 'refresh_token', 'logged_in']);
    printDebug("background", `User Info - Username: ${username}, Access Token: ${access_token ? 'Set' : 'Not Set'}, Refresh Token: ${refresh_token ? 'Set' : 'Not Set'}, Logged In: ${logged_in}`);
    return { username, access_token, refresh_token, logged_in };
}


// --- Core Logic ---

async function makeApiRequest(requestFunc) {
    try {
        const response = await requestFunc();
        if (!isConnected) {
            isConnected = true;
            broadcastToTabs({ command: 'remove_message_box', id: 'connection-error-message' });
            broadcastToTabs({
                command: 'display_message',
                options: { message: 'Connection restored.', type: 'warning', duration: 3000 }
            });
            // Reset badge on successful connection
            const { logged_in } = await getUserInfo();
            if (logged_in) {
                const task_id = await getCurrentTask();
                if (task_id > -1) {
                    chrome.action.setBadgeText({ text: 'on' });
                } else {
                    chrome.action.setBadgeText({ text: 'off' });
                }
                chrome.action.setBadgeBackgroundColor({ color: '#660874' });
            }
        }
        return response;
    } catch (error) {
        const { logged_in } = await getUserInfo();
        if (isConnected && logged_in) {
            isConnected = false;
            broadcastToTabs({
                command: 'display_message',
                options: {
                    id: 'connection-error-message',
                    title: 'Connection Error',
                    message: 'Please check your internet connection and the server status.',
                    type: 'error',
                    duration: 0
                }
            });
        }
        if (error.message.startsWith("Server error:") || error instanceof TypeError) {
            chrome.action.setBadgeText({ text: 'err' });
            chrome.action.setBadgeTextColor({ color: '#ffffff' });
            chrome.action.setBadgeBackgroundColor({ color: '#eb1313ff' });
        }
        console.error("API Request Failed:", error.message);
        throw error;
    }
}

async function getTaskInfo(task_id) {
    if (task_id === -1) return;
    try {
        const config = getConfig();
        const response = await makeApiRequest(() => _get(`${config.urls.get_task_info}?task_id=${task_id}`));
        if (response && response.question) {
            await _set_session({ [TASK_INFO_KEY]: response });
        }
    } catch (error) {
        console.error("Error getting task info:", error.message);
    }
}

async function hasPendingAnnotation() {
    try {
        const config = getConfig();
        const pending_response = await makeApiRequest(() => _get(config.urls.check_pending_annotations));
        return pending_response && pending_response.pending;
    }
    catch (error) {
        console.error("Error checking pending annotations:", error.message);
        return false;
    }
}

async function checkActiveTaskID() {
    printDebug("background", "Checking active task ID...");
    const { logged_in } = await _get_session('logged_in');
    if (!logged_in) {
        await setCurrentTask(-1);
        return -1;
    }

    try {
        const old_task_id = await getCurrentTask();
        const config = getConfig();
        
        const response = await makeApiRequest(() => _post(config.urls.active_task));
        
        const data = response.task_id;
        const new_task_id = (data !== null && data !== undefined && !isNaN(data)) ? parseInt(data, 10) : -1;

        const is_task_started = old_task_id === -1 && new_task_id > -1;
        const is_task_finished = old_task_id > -1 && new_task_id === -1;

        if (new_task_id > -1) {
            chrome.action.setBadgeText({ text: 'on' });
            chrome.action.setBadgeTextColor({ color: '#ffffff' });
            chrome.action.setBadgeBackgroundColor({ color: '#660874' });
        } else {
            chrome.action.setBadgeText({ text: 'off' });
            chrome.action.setBadgeTextColor({ color: '#ffffff' });
            chrome.action.setBadgeBackgroundColor({ color: '#660874' });
        }

        if (is_task_started) {
            getTaskInfo(new_task_id);
        }

        if (is_task_started || is_task_finished) {
            printDebug("background", `Task state changed. Old: ${old_task_id}, New: ${new_task_id}`);
            if (!await hasPendingAnnotation()) {
                closeAllIrrelevantTabs();
            }
        }
        await setCurrentTask(new_task_id);
        return new_task_id;
    } catch (error) {
        console.error("Error checking active task ID:", error.message);
        if (error.message === "Authentication failed.") {
            await setCurrentTask(-1); // Clear current task on auth error
            // Force logout if authentication fails
            await _remove_session(['access_token', 'refresh_token', 'username', 'logged_in']);
            chrome.runtime.sendMessage({ command: "alter_logging_status", log_status: false });
            chrome.action.setBadgeText({ text: '' });
        }
        return -2; // Indicate server failure
    }
}

function closeAllIrrelevantTabs() {
    const config = getConfig();
    printDebug("background", "Closing all irrelevant tabs...");
    chrome.tabs.query({}, (tabs) => {
        printDebug("background", "All open tabs:", tabs);
        const irrelevant_tab_ids = tabs
            .filter(tab => tab.url && !_is_server_page(tab.url) && !_is_extension_page(tab.url))
            .map(tab => tab.id);

        chrome.tabs.create({ url: config.urls.initial_page, active: false });

        if (irrelevant_tab_ids.length > 0) {
            chrome.tabs.remove(irrelevant_tab_ids);
        }
    });
}

async function sendInfo(message) {
    printDebug("background", "Sending info...");
    const { logged_in } = await getUserInfo();
    if (!logged_in) {
        printDebug("background", "User not logged in. Aborting sendInfo.");
        return;
    }

    try {
        const config = getConfig();
        await makeApiRequest(() => _post(config.urls.data, { message }));
        printDebug("background", "Info sent successfully.");
    } catch (error) {
        console.error("Error sending info:", error.message);
    }
}

async function flush() {
    try {
        const items = await _get_local(null);
        const promises = [];
        const keys_to_remove = [];

        for (const key in items) {
            if (key.match(/^\d+$/)) {
                promises.push(sendInfo(items[key]));
                keys_to_remove.push(key);
            }
        }

        if (keys_to_remove.length > 0) {
            await Promise.all(promises);
            await _remove_local(keys_to_remove);
            printDebug("background", `Flushed ${keys_to_remove.length} items from local storage.`);
        }
    }
    catch (error) {
        console.error("Error flushing local storage:", error);
    }
}

async function clearLocalStorage() {
    const items = await _get_local(null);
    const keys_to_remove = [];

    for (const key in items) {
        if (isJSONString(items[key])) {
            const values = JSON.parse(items[key]);
            if (values.expiry < _time_now()) {
                keys_to_remove.push(key);
            }
        }
    }
    if (keys_to_remove.length > 0) {
        await _remove_local(keys_to_remove);
    }
}


// --- Context Menu ---

function createContextMenu() {
    chrome.contextMenus.create({
        id: "add-as-evidence-text",
        title: "Mark Evidence (Text)",
        contexts: ["selection"]
    });
    chrome.contextMenus.create({
        id: "add-as-evidence-image",
        title: "Mark Evidence (Image)",
        contexts: ["image"]
    });
    chrome.contextMenus.create({
        id: "add-as-evidence-other",
        title: "Mark Evidence (Other)",
        contexts: ["video", "audio", "page"]
    });
}

// --- Event Listeners ---

chrome.runtime.onInstalled.addListener(() => {
    createContextMenu();
    chrome.alarms.create(ALARM_CLEAR_STORAGE, { periodInMinutes: 1 });
    chrome.alarms.create(ALARM_CHECK_TASK, { delayInMinutes: 1, periodInMinutes: 5 });
    chrome.alarms.create(ALARM_UPDATE_EVIDENCE_COUNT, { delayInMinutes: 0.2, periodInMinutes: 0.2 });
    _set_session({ is_recording_paused: false });
});

function getSelectionDetails() {
    const selection = window.getSelection();
    if (selection.rangeCount > 0) {
        const range = selection.getRangeAt(0);
        const text = selection.toString();
        let container = range.commonAncestorContainer;
        if (container.nodeType !== Node.ELEMENT_NODE) {
            container = container.parentElement;
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
                        selector += ":nth-of-type("+nth+")";
                }
                path.unshift(selector);
                el = el.parentNode;
            }
            return path.join(" > ");
        }

        const selector = getCssSelector(container);
        return { text, selector };
    }
    return null;
}

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
    if (_is_server_page(tab.url) || _is_extension_page(tab.url)) {
        return;
    }

    const task_id = await getCurrentTask();
    if (task_id === -1) {
        chrome.notifications.create({
            type: 'basic',
            iconUrl: 'popup/THUIR48.png',
            title: 'Action Failed',
            message: 'No active task found.'
        });
        return;
    }

    if (info.menuItemId === "add-as-evidence-text" && info.selectionText) {
        printDebug("background", "Marking textual evidence...");
        chrome.scripting.executeScript({
            target: { tabId: tab.id },
            function: getSelectionDetails,
        }, async (injectionResults) => {
            if (chrome.runtime.lastError || !injectionResults || !injectionResults.length) {
                console.error("Script injection failed:", chrome.runtime.lastError.message);
                return;
            }
            
            const [details] = injectionResults;
            if (details.result) {
                try {
                    const config = getConfig();
                    await makeApiRequest(() => _post(config.urls.add_justification, {
                        task_id: task_id,
                        url: tab.url,
                        page_title: tab.title,
                        text: details.result.text,
                        dom_position: details.result.selector,
                        evidence_type: 'text_selection'
                    }, 'json', 'json')); // content_type = 'json', response_type = 'json'

                    const justificationsResponse = await makeApiRequest(() => _get(`${config.urls.get_justifications}/${task_id}/`));
                    const newCount = justificationsResponse?.justifications?.length ?? 0;

                    // Notify the content script to show a confirmation
                    chrome.tabs.sendMessage(tab.id, { command: "evidence-added-successfully", newCount: newCount });

                    chrome.tabs.query({ url: `${config.urls.base}/task/submit_answer/*` }, (tabs) => {
                        if (tabs.length > 0) {
                            chrome.tabs.sendMessage(tabs[0].id, { command: "refresh_justifications" });
                        }
                    });
                } catch (error) {
                    console.error("Error adding justification:", error.message);
                }
            }
        });
    } else if (["add-as-evidence-image", "add-as-evidence-other"].includes(info.menuItemId)) {
        printDebug("background", "Marking image / other evidence...");
        chrome.tabs.sendMessage(tab.id, { command: 'get-element-details' }, { frameId: info.frameId }, async (details) => {
            if (chrome.runtime.lastError) {
                console.error("Error sending message:", chrome.runtime.lastError.message);
                return;
            }
            printDebug("background", "Evidence details:", details);

            if (details) {
                try {
                    const config = getConfig();
                    await makeApiRequest(() => _post(config.urls.add_justification, {
                        task_id: task_id,
                        url: tab.url,
                        page_title: tab.title,
                        dom_position: details.selector,
                        evidence_type: 'element',
                        element_details: {
                            tagName: details.tagName,
                            attributes: details.attributes
                        }
                    }, 'json', 'json')); // content_type = json, response_type = json

                    const justificationsResponse = await makeApiRequest(() => _get(`${config.urls.get_justifications}/${task_id}/`));
                    const newCount = justificationsResponse?.justifications?.length ?? 0;

                    // Notify the content script to show a confirmation
                    chrome.tabs.sendMessage(tab.id, { command: "evidence-added-successfully", newCount: newCount });

                    chrome.tabs.query({ url: `${config.urls.base}/task/submit_answer/*` }, (tabs) => {
                        if (tabs.length > 0) {
                            chrome.tabs.sendMessage(tabs[0].id, { command: "refresh_justifications" });
                        }
                    });
                } catch (error) {
                    console.error("Error adding element evidence:", error.message);
                }
            }
        });
    }
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    printDebug("background", `Received message: ${message.command || 'unknown'}:`, message);
    (async () => {
        let response;
        const config = getConfig();
        switch (message.command) {
            case MSG_GET_POPUP_DATA:
                const { logged_in } = await _get_session(['logged_in']);
                if (!logged_in) {
                    sendResponse({ log_status: false });
                    return;
                }
            
                const task_id = await checkActiveTaskID();
                let task_info = null;
                if (task_id > 0) {
                    task_info = await _get_session(TASK_INFO_KEY);
                    if (!task_info) {
                        await getTaskInfo(task_id);
                        task_info = await _get_session(TASK_INFO_KEY);
                    }
                }
            
                let pending_url = "";
                try {
                    const pending_response = await _get(config.urls.check_pending_annotations);
                    if (pending_response && pending_response.pending) {
                        await _set_session({ is_recording_paused: true });
                        pending_url = pending_response.url;
                    } else {
                        await _set_session({ is_recording_paused: false });
                        broadcastToTabs({ command: 'remove_message_box', id: 'server-pending-annotation-message' });
                    }
                } catch (error) {
                    console.error("Error checking pending annotations:", error);
                    await _set_session({ is_recording_paused: false });
                    broadcastToTabs({ command: 'remove_message_box', id: 'server-pending-annotation-message' });
                }
            
                sendResponse({
                    log_status: true,
                    task_id: task_id,
                    task_info: task_info ? task_info[TASK_INFO_KEY] : null,
                    pending_url: pending_url
                });
                checkActiveTaskID();
                break;

            case MSG_CHECK_LOGGING_STATUS:
                const { logged_in: is_logged_in } = await _get_session(['logged_in']);
                response = { log_status: is_logged_in };
                sendResponse(response);
                break;

            case MSG_ALTER_LOGGING_STATUS:
                if (message.log_status !== undefined) {
                    await _set_session({ logged_in: message.log_status });
                    sendResponse("Logging status updated");
                }
                else {
                    sendResponse({ error: "Invalid logging status" });
                }
                break;

            case MSG_INJECT_SCRIPT:
                if (!message.script || !sender.tab || !sender.tab.id) {
                    sendResponse({ success: false, error: "No script specified" });
                    return;
                }
                chrome.scripting.executeScript({
                    target: { tabId: sender.tab.id },
                    files: [message.script]
                });
                sendResponse({ success: true });
                break;

            case MSG_SEND_MESSAGE:
                const current_task_id = await getCurrentTask();
                if (current_task_id === -1 || message.send_flag === false) {
                    sendResponse({ success: false, error: "No active task or send_flag is false" });
                    return;
                }

                const { username } = await _get_session(['username']);

                const msg_json = JSON.stringify(message);
                const data_to_compress = new TextEncoder().encode(msg_json);
                const cs = new CompressionStream('deflate');
                const writer = cs.writable.getWriter();
                writer.write(data_to_compress);
                writer.close();
                const compressed_data = await new Response(cs.readable).arrayBuffer();
                const compressed_uint8 = new Uint8Array(compressed_data);
                const compressed_base64 = uint8ArrayToBase64(compressed_uint8);
                sendInfo(compressed_base64);
                sendResponse({ success: true });
                break;

            case MSG_GET_ACTIVE_TASK:
                const active_task_id = await checkActiveTaskID();
                const is_task_active = active_task_id > 0;
                printDebug("background", `Active task ID: ${active_task_id}`);
                sendResponse({ is_task_active: is_task_active, task_id: active_task_id });
                break;
            
            case MSG_GET_TASK_INFO:
                let { [TASK_INFO_KEY]: task_info_data } = await _get_session(TASK_INFO_KEY);
                if (!task_info_data) {
                    const task_id_info = await getCurrentTask();
                    if (task_id_info !== -1) {
                        try {
                            const response_task_info = await _get(`${config.urls.get_task_info}?task_id=${task_id_info}`);
                            if (response_task_info) {
                                await _set_session({ [TASK_INFO_KEY]: response_task_info });
                                task_info_data = response_task_info;
                            }
                        } catch (error) {
                            console.error("Error getting task info on demand:", error);
                        }
                    }
                }
                sendResponse(task_info_data);
                break;
            
            case MSG_GET_JUSTIFICATIONS:
                const task_id_justifications = message.task_id;
                if (task_id_justifications !== -1) {
                    try {
                        const response_justifications = await _get(`${config.urls.get_justifications}/${task_id_justifications}/`);
                        sendResponse(response_justifications);
                    } catch (error) {
                        console.error("Error getting justifications:", error);
                        sendResponse(null);
                    }
                }
                else {
                    sendResponse(null);
                }
                break;
            
            case 'get_session_data':
                if (message.key) {
                    const result = await _get_session(message.key);
                    sendResponse(result);
                } else {
                    sendResponse({});
                }
                break;

        }
    })();
    return true; // Required for async sendResponse
});

chrome.runtime.onStartup.addListener(async () => {
    printDebug("background", "Extension started up.");
    try {
        await flush();
        chrome.alarms.create(ALARM_CLEAR_STORAGE, { periodInMinutes: 1 });
        chrome.alarms.create(ALARM_CHECK_TASK, { delayInMinutes: 1, periodInMinutes: 5 });
        chrome.alarms.create(ALARM_UPDATE_EVIDENCE_COUNT, { delayInMinutes: 0.2, periodInMinutes: 0.2 });
    } catch (error) {
        console.error("Error during onStartup:", error);
    }
});

chrome.alarms.onAlarm.addListener(async (alarm) => {
    const config = getConfig();
    switch (alarm.name) {
        case ALARM_CLEAR_STORAGE:
            printDebug("background", "Clearing expired items from local storage...");
            await clearLocalStorage();
            break;
        case ALARM_CHECK_TASK:
            printDebug("background", "Checking active task ID from alarm...");
            await checkActiveTaskID();
            break;
        case ALARM_UPDATE_EVIDENCE_COUNT:
            printDebug("background", "Updating evidence count from alarm...");
            const task_id = await getCurrentTask();
            if (task_id !== -1) {
                try {
                    const response = await makeApiRequest(() => _get(`${config.urls.get_justifications}/${task_id}/`));
                    if (response && response.justifications) {
                        const newCount = response.justifications.length;
                        chrome.tabs.query({}, (tabs) => {
                            tabs.forEach(tab => {
                                chrome.tabs.sendMessage(tab.id, { command: "update_evidence_count", count: newCount }, (response) => {
                                    if (chrome.runtime.lastError) {
                                        // Suppress the error message for tabs without the content script
                                    }
                                });
                            });
                        });
                    }
                } catch (error) {
                    console.error("Error getting justifications for count:", error.message);
                }
            }
            break;
    }
});

chrome.tabs.onRemoved.addListener((tabId, removeInfo) => {
    printDebug("background", `Tab ${tabId} was closed. Forcing a check for active task status.`);
    checkActiveTaskID();
});
