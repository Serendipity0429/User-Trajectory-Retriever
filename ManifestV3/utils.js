// utils.js

// --- Configuration ---
const IS_DEV = !('update_url' in chrome.runtime.getManifest());
const URL_BASE = IS_DEV ? "http://127.0.0.1:8000" : "http://101.6.41.59:32904";
const IS_PASSIVE_MODE = true;
const CANCEL_TRIAL_THRESHOLD = 10; // number of trials before the user is allowed to cancel annotation

const URLS = {
    base: URL_BASE,
    check: `${URL_BASE}/user/check/`,
    login: `${URL_BASE}/user/login/`,
    token_login: `${URL_BASE}/user/token_login/`,
    token_refresh: `${URL_BASE}/user/token/refresh/`,
    data: `${URL_BASE}/task/data/`,
    cancel: `${URL_BASE}/task/cancel_annotation/`,
    active_task: `${URL_BASE}/task/active_task/`,
    get_task_info: `${URL_BASE}/task/get_task_info/`,
    register: `${URL_BASE}/user/signup/`,
    home: `${URL_BASE}/task/home/`,
    stop_annotation: `${URL_BASE}/task/stop_annotation/`,
    add_justification: `${URL_BASE}/task/justification/add/`,
    get_justifications: `${URL_BASE}/task/justification/get`,
    check_pending_annotations: `${URL_BASE}/user/check_pending_annotations/`,
    initial_page: "https://www.bing.com/",
};

const config = {
    is_dev: IS_DEV,
    is_passive_mode: IS_PASSIVE_MODE,
    urls: URLS,
    version: chrome.runtime.getManifest().version,
    cancel_trial_threshold: CANCEL_TRIAL_THRESHOLD,
};


// --- Utility Functions ---

function printDebug(source, ...messages) {
    if (config.is_dev) {
        console.log(`[${source}]`, ...messages);
    }
}

let isRefreshing = false;
let failedQueue = [];

const processQueue = (error, token = null) => {
    failedQueue.forEach(prom => {
        if (error) {
            prom.reject(error);
        } else {
            prom.resolve(token);
        }
    });
    failedQueue = [];
};

async function refreshToken() {
    if (isRefreshing) {
        return new Promise((resolve, reject) => {
            failedQueue.push({ resolve, reject });
        });
    }

    isRefreshing = true;

    const { refresh_token } = await _get_local('refresh_token');
    if (!refresh_token) {
        printDebug("utils", "Refresh token not found. Forcing logout.");
        // Force logout if refresh token is missing
        await _remove_local(['access_token', 'refresh_token', 'username', 'logged_in']);
        chrome.runtime.sendMessage({ command: "alter_logging_status", log_status: false });
        chrome.action.setBadgeText({ text: '' });
        
        isRefreshing = false;
        processQueue(new Error("No refresh token available"), null);
        return null;
    }

    try {
        const response = await fetch(URLS.token_refresh, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: new URLSearchParams({ 'refresh': refresh_token }),
        });

        if (response.ok) {
            const data = await response.json();
            const new_access_token = data.access;
            await _set_local({ 'access_token': new_access_token });
            printDebug("utils", "Token refreshed successfully.");
            processQueue(null, new_access_token);
            return new_access_token;
        } else {
            console.error("Failed to refresh token. Status:", response.status);
            await _remove_local(['access_token', 'refresh_token', 'username', 'logged_in']);
            chrome.runtime.sendMessage({ command: "alter_logging_status", log_status: false });
            chrome.action.setBadgeText({ text: '' });
            processQueue(new Error("Refresh token is invalid"), null);
            return null;
        }
    } catch (error) {
        console.error("Error during token refresh:", error);
        processQueue(error, null);
        return null;
    } finally {
        isRefreshing = false;
    }
}

async function _request(method, url, data = {}, json_response = true, raw_data = false, send_as_json = false) {
    try {
        const { access_token } = await _get_local('access_token');
        let headers = {};
        let body;
        let request_url = url;

        if (method.toUpperCase() === 'POST') {
            if (send_as_json) {
                headers["Content-Type"] = "application/json";
                body = JSON.stringify(data);
            } else if (!raw_data) {
                headers["Content-Type"] = "application/x-www-form-urlencoded";
                body = new URLSearchParams(data);
            } else {
                headers["Content-Type"] = "text/plain";
                body = typeof data === "string" ? data : String(data);
            }
        }

        if (access_token && url !== URLS.token_login) {
            headers["Authorization"] = `Bearer ${access_token}`;
        }

        let response = await fetch(request_url, {
            method: method.toUpperCase(),
            headers,
            body,
        });

        if (response.status === 401) {
            const new_token = await refreshToken();
            if (new_token) {
                headers["Authorization"] = `Bearer ${new_token}`;
                response = await fetch(request_url, {
                    method: method.toUpperCase(),
                    headers,
                    body,
                });
            } else {
                throw new Error("Authentication failed.");
            }
        }

        if (!response.ok) {
            throw new Error(`Server error: ${response.status}`);
        }

        if (json_response) {
            return await response.json();
        }
        return response;
    } catch (error) {
        printDebug("utils", `API request failed: ${url}`, error);
        throw error; // Re-throw the error to be handled by the caller
    }
}

async function _get(url, json_response = true) {
    return _request('GET', url, {}, json_response);
}

async function _post(url, data = {}, json_response = true, raw_data = false, send_as_json = false) {
    return _request('POST', url, data, json_response, raw_data, send_as_json);
}

// --- Storage --- 

// SECURITY WARNING: chrome.storage.local is not encrypted and can be accessed by other extensions or malicious scripts.
// Do not store sensitive data here. Use chrome.storage.session for in-memory storage if possible.
async function _get_local(key) {
    return chrome.storage.local.get(key);
}

async function _set_local(kv_pairs) {
    return chrome.storage.local.set(kv_pairs);
}

async function _remove_local(key) {
    return chrome.storage.local.remove(key);
}


// --- UI --- 

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

function displayMessageBox(message, type = 'info') {
    if (window.location.href.startsWith(config.urls.base)) return;

    const box = document.createElement('div');
    box.className = 'rr-ignore loaded-box rr-block';
    
    const isWarning = type === 'warning';
    const borderColor = isWarning ? '#ffc107' : '#021e4d';
    const backgroundColor = isWarning ? '#fff3cd' : '#f8f9fa';
    const color = isWarning ? '#856404' : '#212529';

    box.style.cssText = `
        position: fixed;
        right: 10px;
        background-color: ${backgroundColor};
        color: ${color};
        padding: 1rem;
        border-radius: .25rem;
        z-index: 2147483647;
        box-shadow: 0 .5rem 1rem rgba(0,0,0,.15);
        border-left: 5px solid ${borderColor};
        opacity: 0;
        transition: opacity 0.5s ease-in-out;
        font-size: 1rem;
        font-family: 'Noto Sans SC', sans-serif;
    `;
    box.innerText = message;

    let topPosition = 10;
    const questionBox = document.getElementById('task-question-box');
    if (questionBox) {
        topPosition = questionBox.getBoundingClientRect().bottom + 10;
    }

    const existingBoxes = document.querySelectorAll('.loaded-box');
    existingBoxes.forEach(existingBox => {
        topPosition = Math.max(topPosition, existingBox.getBoundingClientRect().bottom + 10);
    });
    box.style.top = `${topPosition}px`;

    document.body.appendChild(box);

    setTimeout(() => { box.style.opacity = '1'; }, 10);

    if (!isWarning) {
        setTimeout(() => {
            box.style.opacity = '0';
            setTimeout(() => { box.remove(); }, 500);
        }, 3000);
    }
}


// --- Helpers ---

function uint8ArrayToBase64(bytes) {
  // Using a smaller chunk size is generally safer and performs well.
  // 32768 is a common choice.
  const CHUNK_SIZE = 0x8000;
  let binary = '';
  const len = bytes.length;

  for (let i = 0; i < len; i += CHUNK_SIZE) {
    // Get a chunk of the Uint8Array
    const chunk = bytes.subarray(i, i + CHUNK_SIZE);

    // This is the most efficient way to convert a small chunk to a binary string
    binary += String.fromCharCode.apply(null, chunk);
  }

  // The final binary string is then encoded to Base64
  return btoa(binary);
}

function isJSONString(str) {
    try {
        JSON.parse(str);
        return true;
    } catch (e) {
        return false;
    }
}

function _time_now() {
    return Date.now();
}

function _is_server_page(url) {
    return url.startsWith(config.urls.base);
}

function _is_extension_page(url) {
    return url.startsWith(chrome.runtime.getURL(''));
}

printDebug("utils.js is loaded");