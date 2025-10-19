// background.js
// This script runs in the background and handles communication between content scripts and the server

// Import config variables and utility functions
importScripts('./utils.js');

// --- Constants ---
const URL_CHECK = config.urls.check;
const URL_DATA = config.urls.data;
const URL_ACTIVE_TASK = config.urls.active_task;
const URL_STOP_ANNOTATION = config.urls.stop_annotation;

const TASK_STORAGE_KEY = 'current_task_id';

const ALARM_CLEAR_STORAGE = 'clear_local_storage';
const ALARM_CHECK_TASK = 'check_active_task';

const MSG_CHECK_LOGGING_STATUS = 'check_logging_status';
const MSG_ALTER_LOGGING_STATUS = 'alter_logging_status';
const MSG_INJECT_SCRIPT = 'inject_script';
const MSG_SEND_MESSAGE = 'send_message';
const MSG_GET_ACTIVE_TASK = 'get_active_task';


// --- State Management ---

async function getCurrentTask() {
    const result = await _get_local(TASK_STORAGE_KEY);
    return result[TASK_STORAGE_KEY] || -1;
}

async function setCurrentTask(task_id) {
    return await _set_local({ [TASK_STORAGE_KEY]: task_id });
}

// SECURITY: Avoid storing passwords in local storage.
// The 'password' field has been removed.
async function getUserInfo() {
    const { username, access_token, refresh_token, logged_in } = await _get_local(['username', 'access_token', 'refresh_token', 'logged_in']);
    printDebug("background", `User Info - Username: ${username}, Access Token: ${access_token ? 'Set' : 'Not Set'}, Refresh Token: ${refresh_token ? 'Set' : 'Not Set'}, Logged In: ${logged_in}`);
    return { username, access_token, refresh_token, logged_in };
}


// --- Core Logic ---

async function checkActiveTaskID() {
    printDebug("background", "Checking active task ID...");
    const { logged_in } = await _get_local('logged_in');
    if (!logged_in) {
        await setCurrentTask(-1);
        return -1;
    }

    try {
        printDebug("background", "Fetching active task ID from server...");
        const old_task_id = await getCurrentTask();
        
        // Use a more robust API call with retry logic
        const response = await _post(URL_ACTIVE_TASK, {}, false); // json_response = false to handle text
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.text();
        const new_task_id = (data !== null && data !== undefined && !isNaN(data)) ? parseInt(data, 10) : -1;

        const is_task_started = old_task_id === -1 && new_task_id > -1;
        const is_task_finished = old_task_id > -1 && new_task_id === -1;

        if (is_task_started || is_task_finished) {
            printDebug("background", `Task state changed. Old: ${old_task_id}, New: ${new_task_id}`);
            closeAllIrrelevantTabs();
        }
        await setCurrentTask(new_task_id);
        return new_task_id;
    } catch (error) {
        console.error("Error checking active task ID:", error);
        if (error.message === "Authentication failed.") {
            // Force logout if authentication fails
            await _remove_local(['access_token', 'refresh_token', 'username', 'logged_in']);
            chrome.runtime.sendMessage({ command: "alter_logging_status", log_status: false });
            chrome.action.setBadgeText({ text: '' });
        } else if (error.message.startsWith("Server error:")) {
            // Indicate server error on the badge
            chrome.action.setBadgeText({ text: 'err' });
            chrome.action.setBadgeTextColor({ color: [255, 255, 255, 255] });
            chrome.action.setBadgeBackgroundColor({ color: [255, 0, 0, 255] });
        }
        return -2; // Indicate server failure
    }
}

function closeAllIrrelevantTabs() {
    printDebug("background", "Closing all irrelevant tabs...");
    chrome.tabs.query({}, (tabs) => {
        printDebug("background", "All open tabs:", tabs);
        const irrelevant_tab_ids = tabs
            .filter(tab => tab.url && !_is_server_page(tab.url) && !_is_extension_page(tab.url))
            .map(tab => tab.id);
        const home_tab_ids = tabs
            .filter(tab => tab.url && _is_server_page(tab.url))
            .map(tab => tab.id);

        if (home_tab_ids.length === 0) {
            chrome.tabs.create({ url: config.urls.initial_page, active: false });
        }

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
        // TODO: Implement a retry mechanism for failed requests.
        await _post(URL_DATA, { message }, true); // raw_data = true
        printDebug("background", "Info sent successfully.");
    } catch (error) {
        console.error("Error sending info:", error);
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
            // TODO: Implement more robust error handling for failed sends.
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


// --- Event Listeners ---

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    printDebug("background", `Received message: ${message.command || 'unknown'}:`, message);
    (async () => {
        let response;
        switch (message.command) {
            case MSG_CHECK_LOGGING_STATUS:
                const { logged_in } = await _get_local(['logged_in']);
                if (logged_in) {
                    const task_id = await getCurrentTask();
                    if (task_id != -1) {
                        chrome.action.setBadgeText({ text: 'on' });
                        chrome.action.setBadgeBackgroundColor({ color: [202, 181, 225, 255] });
                    } else {
                        chrome.action.setBadgeText({ text: 'off' });
                        chrome.action.setBadgeBackgroundColor({ color: [202, 181, 225, 255] });
                    }
                    response = { log_status: true };
                } else {
                    chrome.action.setBadgeText({ text: '' });
                    response = { log_status: false };
                }
                sendResponse(response);
                break;

            case MSG_ALTER_LOGGING_STATUS:
                if (message.log_status !== undefined) {
                    await _set_local({ logged_in: message.log_status });
                    sendResponse("Logging status updated");
                } else {
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

                const { username } = await _get_local(['username']);

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
                const task_id = await checkActiveTaskID();
                const is_task_active = task_id !== -1;
                printDebug("background", `Active task ID: ${task_id}`);
                sendResponse({ is_task_active: is_task_active, task_id: task_id });
                break;
        }
    })();
    return true; // Required for async sendResponse
});

chrome.runtime.onStartup.addListener(async () => {
    console.log("Extension starting up...");
    try {
        await flush();
        chrome.alarms.create(ALARM_CLEAR_STORAGE, { periodInMinutes: 1 });
        chrome.alarms.create(ALARM_CHECK_TASK, { delayInMinutes: 1, periodInMinutes: 5 });
    } catch (error) {
        console.error("Error during onStartup:", error);
    }
});

chrome.alarms.onAlarm.addListener(async (alarm) => {
    switch (alarm.name) {
        case ALARM_CLEAR_STORAGE:
            printDebug("background", "Clearing expired items from local storage...");
            await clearLocalStorage();
            break;
        case ALARM_CHECK_TASK:
            printDebug("background", "Checking active task ID from alarm...");
            await checkActiveTaskID();
            break;
    }
});

chrome.tabs.onRemoved.addListener((tabId, removeInfo) => {
    printDebug("background", `Tab ${tabId} was closed. Forcing a check for active task status.`);
    checkActiveTaskID();
});