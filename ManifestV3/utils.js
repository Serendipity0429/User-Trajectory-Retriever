// utils.js

// --- Utility Functions ---

function printDebug(source, ...messages) {
    const config = getConfig();
    if (config && config.is_dev) {
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
    const config = getConfig();

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
        const response = await fetch(config.urls.token_refresh, {
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
    const config = getConfig();
    const MAX_RETRIES = config.max_retries || 3;
    let attempt = 0;
    while (attempt < MAX_RETRIES) {
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

            if (access_token && url !== config.urls.token_login) {
                headers["Authorization"] = `Bearer ${access_token}`;
            }

            let response = await fetch(request_url, {
                method: method.toUpperCase(),
                headers,
                body,
            });

            if (response.status === 401 && url !== config.urls.token_login) {
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
                // Try to parse the response as JSON, as it might contain error details
                if (json_response) {
                    try {
                        const error_data = await response.json();
                        return error_data; // Return the JSON error response
                    } catch (e) {
                        // If parsing fails, throw a generic error
                        throw new Error(`Server error: ${response.status}`);
                    }
                }
                throw new Error(`Server error: ${response.status}`);
            }

            if (json_response) {
                return await response.json();
            }
            return response;
        } catch (error) {
            attempt++;
            if (attempt >= MAX_RETRIES) {
                printDebug("utils", `API request failed after ${MAX_RETRIES} attempts: ${url}`, error);
                throw error;
            }
            await new Promise(resolve => setTimeout(resolve, 1000 * attempt));
        }
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
    const config = getConfig();
    if (!config || !url) return false;
    return url.startsWith(config.urls.base);
}

function _is_extension_page(url) {
    return url.startsWith(chrome.runtime.getURL(''));
}

function displayMessageBox(message, type = 'info') {
    const config = getConfig();
    if (!config || window.location.href.startsWith(config.urls.base)) return;

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
    const config = getConfig();
    if (!config || !url) return false;
    return url.startsWith(config.urls.base);
}

function _is_extension_page(url) {
    return url.startsWith(chrome.runtime.getURL(''));
}