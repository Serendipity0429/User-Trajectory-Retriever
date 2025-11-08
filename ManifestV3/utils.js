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
    const MAX_RETRIES = config.max_retries || 3;
    let attempt = 0;

    while (attempt < MAX_RETRIES) {
        const { refresh_token } = await _get_session('refresh_token');
        if (!refresh_token) {
            printDebug("utils", "Refresh token not found. Forcing logout.");
            await _remove_session(['access_token', 'refresh_token', 'username', 'logged_in']);
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
                await _set_session({ 'access_token': new_access_token });
                printDebug("utils", "Token refreshed successfully.");
                processQueue(null, new_access_token);
                isRefreshing = false;
                return new_access_token;
            } else {
                throw new Error(`Failed to refresh token. Status: ${response.status}`);
            }
        } catch (error) {
            console.error(`Error during token refresh (attempt ${attempt + 1}):`, error);
            attempt++;
            if (attempt >= MAX_RETRIES) {
                console.error("Max retries reached. Forcing logout.");
                await _remove_session(['access_token', 'refresh_token', 'username', 'logged_in']);
                chrome.runtime.sendMessage({ command: "alter_logging_status", log_status: false });
                chrome.action.setBadgeText({ text: '' });
                processQueue(new Error("Refresh token is invalid"), null);
                isRefreshing = false;
                return null;
            }
            await new Promise(resolve => setTimeout(resolve, 500)); // Wait before retrying
        }
    }
}

async function _request(method, url, data = {}, content_type = 'form', response_type = 'json', request_timeout = null)
{
    const config = getConfig();
    const MAX_RETRIES = config.max_retries || 3;
    const TIMEOUT = request_timeout || config.request_timeout || 5000; // Default to 5 seconds
    let attempt = 0;
    while (attempt < MAX_RETRIES) {
        try {
            const { access_token } = await _get_session('access_token');
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

            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), TIMEOUT);

            let response = await fetch(request_url, {
                method: method.toUpperCase(),
                headers,
                body,
                signal: controller.signal,
            });

            clearTimeout(timeoutId);

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
                        if (!response.ok) {
                            throw new Error(json_response.error || `Server error: ${response.status}`);
                        }
                        return json_response;
                    } catch (e) {
                        // If parsing fails or an error was thrown, re-throw it.
                        throw e;
                    }
                default:
                    if (!response.ok) {
                        throw new Error(`Server error: ${response.status}`);
                    }
                    return response;
            }
        } catch (error) {
            attempt++;
            if (error.name === 'AbortError') {
                printDebug("utils", `Request timed out after ${TIMEOUT}ms: ${url}`);
            }
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

async function _get_session(key) {
    return chrome.storage.session.get(key);
}

async function _set_session(kv_pairs) {
    return chrome.storage.session.set(kv_pairs);
}

async function _remove_session(key) {
    return chrome.storage.session.remove(key);
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

function getCssSelector(el) {
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

function broadcastToTabs(message) {
    chrome.tabs.query({}, (tabs) => {
        for (let tab of tabs) {
            // Avoid sending messages to extension pages or platform pages
            if (tab.url && !_is_server_page(tab.url) && !_is_extension_page(tab.url)) {
                chrome.tabs.sendMessage(tab.id, message, (response) => {
                    if (chrome.runtime.lastError) {
                        // Suppress errors for tabs that don't have the content script
                    }
                });
            }
        }
    });
}

async function displayMessageBox(options) {
    const { message, innerHTML, title = '', type = 'info', duration = 3000, id = null, css = '' } = options;
    
    if (id && document.getElementById(id)) {
        return; // Don't display if a box with the same ID already exists
    }

    const config = getConfig();
    if (!config || window.location.href.startsWith(config.urls.base)) return;

    const settings = await new Promise((resolve) => {
        chrome.storage.local.get(['messageBoxSize', 'messageBoxPosition'], resolve);
    });

    const boxSize = options.size || settings.messageBoxSize || 'medium';
    const boxPosition = options.position || settings.messageBoxPosition || 'top-right';

    const box = document.createElement('div');
    box.className = 'rr-ignore loaded-box rr-block';
    if (id) {
        box.id = id;
    }
    
    let borderColor, backgroundColor, color;
    switch (type) {
        case 'warning':
            borderColor = '#ffc107';
            backgroundColor = '#fff3cd';
            color = '#856404';
            break;
        case 'error':
            borderColor = '#dc3545';
            backgroundColor = '#f8d7da';
            color = '#721c24';
            break;
        case 'info':
        default:
            borderColor = '#021e4d';
            backgroundColor = '#f8f9fa';
            color = '#212529';
            break;
    }

    const sizeMap = {
        small: { minWidth: '10vw', maxWidth: '20vw', padding: '1.0vw', fontSize: '0.8vw' },
        medium: { minWidth: '15vw', maxWidth: '25vw', padding: '1.2vw', fontSize: '1.2vw' },
        large: { minWidth: '20vw', maxWidth: '30vw', padding: '1.4vw', fontSize: '1.6vw' }
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

    box.style.cssText = `
        position: fixed;
        background-color: ${backgroundColor};
        color: ${color};
        padding: 1.0vw;
        border-radius: 0.25vw;
        z-index: 2147483647;
        box-shadow: 0 0.6vw 1.2vw rgba(0,0,0,.15);
        border-left: 5px solid ${borderColor};
        opacity: 0;
        transition: opacity 0.5s ease-in-out, width 0.3s ease, height 0.3s ease, top 0.3s ease, left 0.3s ease;
        font-family: 'Noto Sans SC', sans-serif !important;
        word-wrap: break-word;
        ${css}
    `;

    if (id === 'task-question-box') {
        const sizeStyles = sizeMap[boxSize] || sizeMap.medium;
        const positionStyles = positionMap[boxPosition] || positionMap['top-right'];
        Object.assign(box.style, sizeStyles, positionStyles);
    } else {
        // Temporary notification box, use stacking logic
        let topPosition = 10;
        document.querySelectorAll('.loaded-box').forEach(existingBox => {
            topPosition = Math.max(topPosition, existingBox.getBoundingClientRect().bottom + 10);
        });
        box.style.top = `${topPosition}px`;
        box.style.right = '10px';
        const sizeStyles = sizeMap[boxSize] || sizeMap['small']; // notifications are always small
        Object.assign(box.style, sizeStyles);
    }

    if (innerHTML) {
        box.innerHTML = innerHTML;
    } else {
        if (title) {
            box.innerHTML = `<strong>${title}</strong><br>${message}`;
        } else {
            box.innerText = message;
        }
    }

    document.body.appendChild(box);

    setTimeout(() => { box.style.opacity = '0.9'; }, 10);

    if (duration > 0) {
        setTimeout(() => {
            box.style.opacity = '0';
            setTimeout(() => { box.remove(); }, 500);
        }, duration);
    }
}

function removeMessageBox(id) {
    if (!id || !document) return; // safety check
    const box = document.getElementById(id);
    if (box) {
        box.style.opacity = '0';
        setTimeout(() => { box.remove(); }, 500);
    }
}

// --- Color Utilities ---

function shadeColor(color, percent) {
    let R = parseInt(color.substring(1, 3), 16);
    let G = parseInt(color.substring(3, 5), 16);
    let B = parseInt(color.substring(5, 7), 16);

    R = parseInt(R * (100 + percent) / 100);
    G = parseInt(G * (100 + percent) / 100);
    B = parseInt(B * (100 + percent) / 100);

    R = (R < 255) ? R : 255;
    G = (G < 255) ? G : 255;
    B = (B < 255) ? B : 255;

    const RR = ((R.toString(16).length === 1) ? "0" + R.toString(16) : R.toString(16));
    const GG = ((G.toString(16).length === 1) ? "0" + G.toString(16) : G.toString(16));
    const BB = ((B.toString(16).length === 1) ? "0" + B.toString(16) : B.toString(16));

    return "#" + RR + GG + BB;
}

function getContrastingTextColor(hexcolor) {
    hexcolor = hexcolor.replace("#", "");
    const r = parseInt(hexcolor.substr(0, 2), 16);
    const g = parseInt(hexcolor.substr(2, 2), 16);
    const b = parseInt(hexcolor.substr(4, 2), 16);
    const yiq = ((r * 299) + (g * 587) + (b * 114)) / 1000;
    return (yiq >= 128) ? '#000000' : '#ffffff';
}

function hexToRgb(hex) {
    hex = hex.replace("#", "");
    const r = parseInt(hex.substr(0, 2), 16);
    const g = parseInt(hex.substr(2, 2), 16);
    const b = parseInt(hex.substr(4, 2), 16);
    return { r, g, b };
}

function colorDistance(hex1, hex2) {
    const rgb1 = hexToRgb(hex1);
    const rgb2 = hexToRgb(hex2);
    const dr = rgb1.r - rgb2.r;
    const dg = rgb1.g - rgb2.g;
    const db = rgb1.b - rgb2.b;
    return Math.sqrt(dr * dr + dg * dg + db * db);
}

function rgbToHex(r, g, b) {
    return "#" + ((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1).toUpperCase();
}