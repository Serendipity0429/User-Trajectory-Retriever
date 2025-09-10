// background.js
// This script runs in the background and handles communication between content scripts and the server

// Import necessary scripts
// Import third-party libraries
// import './scripts/pako.min.js'; // For data compression 

// Import config variables and utility functions
importScripts('./utils.js');

const url_base = config.urls.base;
const url_check = config.urls.check;
const url_data = config.urls.data;
const url_active_task = config.urls.active_task;

/* NOTICE: username and password are stored in local storage since the service worker's state is not persistent. */
// Variables that stored in local storage
// username, password, logged_in

// Runtime global variables in background
let current_task = -1;


// NOTICE: Manifest V3 does not support synchronous AJAX requests. All network calls must be asynchronous.
// We should replace $.ajax with the modern Fetch API, which is also a more secure approach.

// Key for storing current task ID
const TASK_STORAGE_KEY = 'current_task_id';
async function getCurrentTask() {
    const result = await _get_local(TASK_STORAGE_KEY);
    return result[TASK_STORAGE_KEY] || -1;
}
// Set current task ID in local storage
async function setCurrentTask(task_id) {
    return await _set_local({ [TASK_STORAGE_KEY]: task_id });
}

// Get username, password, and isLoggedIn status
async function getUserInfo() {
    const { username, password, logged_in } = await _get_local(['username', 'password', 'logged_in']);

    printDebugOfBackground(`User Info - Username: ${username}, Password: ${password ? password : 'Not Set'}, Logged In: ${logged_in}`);

    return { username, password, logged_in };
}

// Verify user logging status
async function verifyUser() {
    printDebugOfBackground("Verifying user...");
    const { username, password, logged_in } = await getUserInfo();
    if (!username || !password) {
        return -1;
    }

    try {
        const response = await _post(url_check, { username, password });

        const status = response.status !== undefined ? response.status : response;

        // NOTICE: 0: Success, 1: Incorrect Password, 2: User Not Found
        printDebugOfBackground(`Server response: ${status}`);
        return status;
    } catch (error) {
        console.error("Error verifying user:", error);
        return -1; // Network or other error
    }
}

// Check whether the user has an active task and retrieve its ID
async function checkActiveTaskID() {
    printDebugOfBackground("Checking active task ID...");
    const { username, password, logged_in } = await getUserInfo();
    if (!username || !password || !logged_in) {
        await setCurrentTask(-1); // Reset current task if not logged in
        return -1;
    }

    try {
        const old_task_id = await getCurrentTask();
        const data = await _post(url_active_task, { username, password });
        const new_task_id = (data !== null && data !== undefined && !isNaN(data)) ? parseInt(data, 10) : -1;

        // Check if the task state has changed
        const is_task_started = old_task_id === -1 && new_task_id > -1;
        const is_task_finished = old_task_id > -1 && new_task_id === -1;
        if (is_task_started || is_task_finished) { // task started or finished
            printDebugOfBackground(`Task state changed. Old Task ID: ${old_task_id}, New Task ID: ${new_task_id}`);
            closeAllIrrelevantTabs();
        }
        await setCurrentTask(new_task_id);
        return new_task_id;
    } catch (error) {
        console.error("Error checking active task ID:", error);
        // Don't clear task ID on temporary server failure, just return error code
        return -2;
    }
}

// Close all tabs that is not from the base URL
function closeAllIrrelevantTabs() {
    printDebugOfBackground("Closing all irrelevant tabs...");
    chrome.tabs.query({ active: true, currentWindow: true }, (activeTabs) => {
        const activeTabId = activeTabs.length > 0 ? activeTabs[0].id : null;
        chrome.tabs.query({}, (tabs) => {
            // Log all tabs for debugging
            printDebugOfBackground("All open tabs:", tabs);
            const irrelevant_tab_ids = tabs
                .filter(tab => tab.url && tab.id !== activeTabId && !_is_server_page(tab.url) && !_is_extension_page(tab.url))
                .map(tab => tab.id);
            const home_tab_ids = tabs
                .filter(tab => tab.url && _is_server_page(tab.url))
                .map(tab => tab.id); // Not including extension pages

            if (home_tab_ids.length === 0) {
                chrome.tabs.create({ url: config.urls.initial_page, active: false });
            }

            if (irrelevant_tab_ids.length > 0) {
                chrome.tabs.remove(irrelevant_tab_ids);
            }

        });
    });
}


// Send information to base url
async function sendInfo(message) {
    printDebugOfBackground("Sending info...");
    const verified = await verifyUser();
    if (verified !== 0) return;

    // Use Fetch API
    try {
        await _post(url_data, { message });
    } catch (error) {
        console.error("Error sending info:", error);
    }
}

// Flush the local storage
async function flush() {
    try {
        const items = await _get_local(null); // Get all items from storage
        const promises = []; // Array to hold promises for sending messages
        const keys_to_remove = [];

        for (const key in items) {
            if (key.match(/^\d+$/)) {
                // NOTICE: sendInfo is async, so this function won't wait for it to finish
                promises.push(sendInfo(items[key]));
                keys_to_remove.push(key);
            }
        }

        if (keys_to_remove.length > 0) {
            await Promise.all(promises); // Wait for all messages to be sent
            await _remove_local(keys_to_remove); // Remove all sent items from storage
            printDebugOfBackground(`Flushed ${keys_to_remove.length} items from local storage.`);
        }
    }
    catch (error) {
        console.error("Error flushing local storage:", error);
    }
}


// Clear expired items from local storage
async function clearLocalStorage() {
    const items = await _get_local(null); // Get all items from storage
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

// Event listeners in the service worker must be top-level.
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    // Handling synchronous responses is more complex in Manifest V3.
    // We use sendResponse but must return true to indicate we will send a response asynchronously.
    printDebugOfBackground(`Received message typed ${message.type || 'unknown source'}:`, message);
    let response;
    (async () => {
        switch (message.command) {
            case "check_logging_status":
                printDebugOfBackground("Checking logging status...");
                const verified = await verifyUser();
                if (verified === 0) {
                    chrome.action.setBadgeText({ text: 'on' });
                    chrome.action.setBadgeBackgroundColor({ color: [202, 181, 225, 255] });
                    response = { log_status: true };
                } else {
                    chrome.action.setBadgeText({ text: '' });
                    response = { log_status: false };
                }
                sendResponse(response);
                break;
            case "alter_logging_status":
                printDebugOfBackground("Altering logging status...");
                if (message.log_status !== undefined) {
                    await _set_local({ logged_in: message.log_status });
                    if (message.log_status) {
                        closeAllIrrelevantTabs(); // Close irrelevant tabs when logging in
                    }
                    sendResponse("Logging status updated");
                } else {
                    sendResponse({ error: "Invalid logging status" });
                }
                break;
            case "inject_script":
                pringDebug("Injecting script...");
                if (!message.script || !sender.tab || !sender.tab.id) {
                    sendResponse({ success: false, error: "No script specified" });
                    return false;
                }
                // Inject the script into the active tab
                chrome.scripting.executeScript({
                    target: { tabId: sender.tab.id },
                    files: [message.script]
                });
                sendResponse({ success: true });
                break;
            case "send_message":
                printDebugOfBackground("Sending message...");
                printDebugOfBackground("Original message:", message);

                // Check if there is a need to send the message
                if (getCurrentTask() === -1 || !message.send_flag) {
                    sendResponse({ success: false, error: "No active task or send_flag is false" });
                    return;
                }

                const { username, password, logged_in } = await getUserInfo();
                message.username = username;
                message.password = password;
                let msg_json = JSON.stringify(message);
                // Encode the JSON string to a Uint8Array
                const data_to_compress = new TextEncoder().encode(msg_json);
                // Create a compression stream for 'deflate' compression
                const cs = new CompressionStream('deflate');
                const writer = cs.writable.getWriter();
                writer.write(data_to_compress);
                writer.close();
                // Read the compressed data from the stream
                const compressed_data = await new Response(cs.readable).arrayBuffer();
                const compressed_uint8 = new Uint8Array(compressed_data);
                // Convert the Uint8Array to a base64 string
                let compressed_base64 = uint8ArrayToBase64(compressed_uint8);
                sendInfo(compressed_base64);
                sendResponse({ success: true });
                break;
            case "get_active_task":
                printDebugOfBackground("Getting active task...");
                const task_id = await checkActiveTaskID();
                const is_task_active = task_id !== -1;
                printDebugOfBackground(`Active task ID: ${task_id}`);
                sendResponse({ is_task_active: is_task_active, task_id: task_id });
                break;
        }
    })();
    // Return true to indicate that the response will be sent asynchronously.
    // This is required for all async operations within the listener.
    return true;
})


chrome.runtime.onStartup.addListener(async () => {
    try {
        // Initial flush and setup
        await flush();
        // Set up an alarm for clearing local storage every minute
        chrome.alarms.create('clear_local_storage', { periodInMinutes: 1 });
    } catch (error) {
        console.error("Error during onStartup:", error);
    }
});

// Listen for alarms
chrome.alarms.onAlarm.addListener(async (alarm) => {
    if (alarm.name === 'clear_local_storage') {
        await clearLocalStorage();
    }
});