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

async function _request(method, url, data = {}, content_type = 'form', response_type = 'json')
{
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
                // If data is empty, send an empty body
                if (!data || Object.keys(data).length === 0) {
                    body = null;
                } else {
                    switch (content_type) {
                        case 'json':
                            headers["Content-Type"] = "application/json";
                            body = JSON.stringify(data);
                            break;
                        case 'text':
                            headers["Content-Type"] = "text/plain";
                            body = typeof data === "string" ? data : String(data);
                            break;
                        case 'form':
                        default:
                            headers["Content-Type"] = "application/x-www-form-urlencoded";
                            body = new URLSearchParams(data);
                            break;
                    }
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

            // Refresh token if unauthorized
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

            switch (response_type) {
                case 'json':
                    try {
                        const json_response = await response.json();
                        return json_response;
                    } catch (e) {
                        throw new Error(`Server error: ${response.status}`);
                    }
                default:
                    if (!response.ok) {
                        throw new Error(`Server error: ${response.status}`);
                    }
                    return response;
            }
        } catch (error) {
            attempt++;
            if (attempt >= MAX_RETRIES) {
                printDebug("utils", `API request failed after ${MAX_RETRIES} attempts: ${url}`, error);
                throw error;
            }
            await new Promise(resolve => setTimeout(resolve, 500 * attempt));
        }
    }
}

async function _get(url, response_type = 'json') {
    return _request('GET', url, {}, 'none', response_type);
}

async function _post(url, data = {}, content_type = 'form', response_type = 'json') {
    return _request('POST', url, data, content_type, response_type);
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

function displayMessageBox(options) {
    const { message, innerHTML, type = 'info', duration = 3000, id = null, css = '' } = options;
    const config = getConfig();
    if (!config || window.location.href.startsWith(config.urls.base)) return;

    const box = document.createElement('div');
    box.className = 'rr-ignore loaded-box rr-block';
    if (id) {
        box.id = id;
    }
    
    const isWarning = type === 'warning';
    const borderColor = isWarning ? '#ffc107' : '#021e4d';
    const backgroundColor = isWarning ? '#fff3cd' : '#f8f9fa';
    const color = isWarning ? '#856404' : '#212529';

    box.style.cssText = `
        position: fixed;
        right: 10px;
        background-color: ${backgroundColor};
        color: ${color};
        padding: 1.0vw;
        border-radius: 0.25vw;
        z-index: 2147483647;
        box-shadow: 0 0.6vw 1.2vw rgba(0,0,0,.15);
        border-left: 5px solid ${borderColor};
        opacity: 0;
        transition: opacity 0.5s ease-in-out;
        font-size: 1.2vw;
        min-width: 15rem;
        font-family: 'Noto Sans SC', sans-serif !important;
        ${css}
    `;

    if (innerHTML) {
        box.innerHTML = innerHTML;
    } else {
        box.innerText = message;
    }

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

    if (duration > 0) {
        setTimeout(() => {
            box.style.opacity = '0';
            setTimeout(() => { box.remove(); }, 500);
        }, duration);
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