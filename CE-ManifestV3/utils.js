// utils.js
// Store the common configuration variables for the extension and Utility functions for the extension

//NOTICE: Configurations
// Whether the extension is in development mode
// TODO: Change to false before deployment
const is_dev = !('update_url' in chrome.runtime.getManifest());

// Whether the user annotation event on the fly
const is_passive_mode = true;

// URL endpoints for the backend server
const _url_base = is_dev ? "http://127.0.0.1:8000" : "http://101.6.41.59:32904";
const urls = {
    base: _url_base,
    check: `${_url_base}/user/check/`,
    login: `${_url_base}/user/login/`,
    data: `${_url_base}/task/data/`,
    cancel: `${_url_base}/task/cancel_task/`,
    active_task: `${_url_base}/task/active_task/`,
    register: `${_url_base}/user/signup/`,
    home: `${_url_base}/task/home/`,
    initial_page: "https://www.bing.com/",
}

// Version of the extension
const version = chrome.runtime.getManifest().version;

// Comprehensive config object
const config = {
    is_dev: is_dev,
    is_passive_mode: is_passive_mode,
    urls: urls,
    version: version
};


// NOTICE: Utility functions
// Output to console only in development mode
function printDebug(...messages) {
    if (config.is_dev) {
        console.log(...messages);
    }
}

function printDebugOfBackground(...messages) {
    if (config.is_dev) {
        console.log("[Background]", ...messages);
    }
}

function printDebugOfPopup(...messages) {
    if (config.is_dev) {
        console.log("[Popup]", ...messages);
    }
}


// Make POST requests
async function _post(url, data, json_response = true) {
    try {
        // If username and password are not in data, add them from local storage
        if (!data.username || !data.password) {
            const creds = await _get_local(['username', 'password']);
            if (creds.username) data.username = creds.username;
            if (creds.password) data.password = creds.password;
        }
        const response = await fetch(url, {
            method: "POST",
            headers: {
                "Content-Type": "application/x-www-form-urlencoded",
            },
            body: new URLSearchParams(data),
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        if (json_response) {
            return await response.json();
        } else {
            return await response;
        }
    } catch (error) {
        console.error(`API request failed: ${url}`, error);
        return null;
    }
}

// Get data from local storage
async function _get_local(key) {
    return chrome.storage.local.get(key);
}

// Save data to local storage
async function _set_local(kv_pairs) {
    return chrome.storage.local.set(kv_pairs);
}

// Remove data from local storage
async function _remove_local(key) {
    return chrome.storage.local.remove(key);
}

// Clear all data from local storage
async function _clear_local() {
    return chrome.storage.local.clear();
}

// Helper to convert Uint8Array to Base64 string
// Pako.deflate returns a Uint8Array, which needs to be Base64 encoded for sending via fetch/chrome.runtime.sendMessage
function uint8ArrayToBase64(bytes) {
    var binary = '';
    var len = bytes.byteLength;
    for (var i = 0; i < len; i++) {
        binary += String.fromCharCode(bytes[i]);
    }
    return btoa(binary);
}

// Check if a string is a valid JSON string
function isJSONString(str) {
    try {
        JSON.parse(str);
    } catch (e) {
        return false;
    }
    return true;
}

// Get the current time
function _time_now() {
    return (new Date()).getTime();
}

// Display a "content.js loaded" box on the upper right corner for 3 seconds
// should have a class named 'rr-ignore' to avoid being recorded by rrweb
// When DOM loaded
function displayLoadedBox(script_name) {
    var current_url = window.location.href;
    if (current_url.startsWith(config.urls.base))
        return; // Avoid displaying the box on the local server
    const box = document.createElement('div');
    box.className = 'rr-ignore loaded-box';
    box.style.opacity = '0.2';
    box.style.transition = 'opacity 0.5s ease-in-out';

    // Fade in
    setTimeout(() => {
        box.style.opacity = '1';
    }, 10);
    box.style.position = 'fixed';
    box.style.right = '10px';
    box.style.backgroundColor = 'white';
    box.style.color = 'black';
    box.style.padding = '10px';
    box.style.border = '2px solid rgb(151, 67, 219)';
    box.style.zIndex = '1000000';
    box.innerText = `${script_name} loaded!`;

    // Check for existing loaded boxes and position accordingly
    const existingBoxes = document.querySelectorAll('.loaded-box');
    let topPosition = 10;

    existingBoxes.forEach(existingBox => {
        const rect = existingBox.getBoundingClientRect();
        if (rect.bottom > topPosition) {
            topPosition = rect.bottom + 10;
        }
    });

    box.style.top = `${topPosition}px`;

    document.body.appendChild(box);

    setTimeout(() => {
        box.style.opacity = '0';
        setTimeout(() => {
            box.remove();
        }, 500);
    }, 3000);
}

// Check if a url is from the backend
function _is_server_page(url) {
    return url.startsWith(config.urls.base);
}

// Check if a url is from the extension 
function _is_extension_page(url) {
    return url.startsWith(chrome.runtime.getURL(''));
}


// NOTICE: Other resources
const ANNOTATION_MODAL_STYLE = `
        :root { --primary-purple: #6A1B9A; --secondary-purple: #9C27B0; --light-purple: #E1BEE7; }
        .annotation-wrapper { position: fixed; }
        .annotation-modal { background: white; padding: 5%; border-radius: 10px; box-shadow: 0 0 20px rgba(0,0,0,0.2); width: 90%; height: 90%; max-width: 500px; border: 2px solid var(--primary-purple); font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; font-size: 16px; box-sizing: initial; color: #000; }
        .annotation-modal .question-container { margin-bottom: 0; padding-left: 2%; }
        .annotation-modal .question-container:has(textarea) { padding-left: 0; }
        .annotation-modal h2 { color: var(--accent-purple); margin-top: 0; margin-bottom: 5px; display: block; font-size: 20px; font-weight: bold; unicode-bidi: isolate; }
        .annotation-modal h2 div.event-type { color: var(--primary-purple); display: inline; }
        .annotation-modal textarea { width: 96%; padding: 2%; border: 1px solid var(--light-purple); border-radius: 5px; resize: none; min-height: 90px; margin: 10px 0; font-size: 16px; }
        .annotation-modal .checkbox-group { display: flex; align-items: center; gap: 10px; }
        .annotation-modal input[type="checkbox"] { accent-color: var(--secondary-purple); width: 18px; height: 18px; }
        .annotation-modal button { background: var(--secondary-purple); color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; transition: background 0.3s ease; font-size: 16px; }
        .annotation-modal button:hover { background: var(--primary-purple); }
        .annotation-modal .btn-ignore { background: #6c757d; color: white; }
        .annotation-modal .btn-ignore:hover { background: #5a6268; }
        .annotation-modal .form-footer { padding-top: 20px; display: flex; justify-content: space-between; align-items: center; bottom: 0; }
        `;

function GENERATE_ANNOTATION_MODAL_HTML(type) {
    const ANNOTATION_MODAL_HTML = `
    <div class="annotation-wrapper rr-ignore">
        <div class="annotation-modal">
            <div class="questions-container">
                <div class="question-container">
                    <h2>What is the purpose of this <div class="event-type">${type}</div> event?</h2>
                    <textarea id="purpose" placeholder="Describe the event purpose..."></textarea>
                </div>
            </div>
            <div class="question-container">
                <h2>Event Classification</h2>
                <div class="checkbox-group">
                    <input type="checkbox" id="key-event">
                    <label for="key-event">Mark as Key Event</label>
                </div>
            </div>
            <div class="form-footer">
                <button type="button" id="submit-btn">Submit</button>
                <button type="button" id="ignore-btn" class="btn-ignore">Ignore this event</button>
            </div>
        </div>
    </div>
    `;
    return ANNOTATION_MODAL_HTML;
}