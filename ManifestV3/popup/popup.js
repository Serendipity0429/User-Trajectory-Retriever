// --- Configuration ---
const base_url = config.urls.base;
const check_url = config.urls.check;
const token_login_url = config.urls.token_login;
const register_url = config.urls.register;
const feedback_url = config.urls.home;

// --- Global State ---
let active_task_id = -1;

// --- Manifest V3 COMPATIBILITY HELPERS ---

async function sendMessageFromPopup(message) {
    return new Promise((resolve, reject) => {
        if (!message.type) {
            message.type = "msg_from_popup";
        }
        chrome.runtime.sendMessage(message, (response) => {
            if (chrome.runtime.lastError) {
                reject(chrome.runtime.lastError);
            } else {
                resolve(response);
            }
        });
    });
}

/**
 * Creates a custom modal to replace the native `alert()` function.
 * @param {string} message The message to display.
 */
function showAlert(message) {
    const loggedDiv = document.getElementById('logged');
    const originalDisplay = loggedDiv.style.display;
    loggedDiv.style.display = 'none';
    const modal_container = document.getElementById('modal-container');
    modal_container.innerHTML = `
        <div class="modal-overlay">
            <div class="modal-content">
                <p>${message}</p>
                <div class="modal-buttons">
                    <button class="ok-btn">OK</button>
                </div>
            </div>
        </div>
    `;
    modal_container.querySelector('.ok-btn').addEventListener('click', () => {
        modal_container.innerHTML = '';
        loggedDiv.style.display = originalDisplay;
    });
}

/**
 * Creates a custom modal to replace the native `confirm()` function.
 * @param {string} message The confirmation message.
 * @returns {Promise<boolean>} A promise that resolves to true if confirmed, false otherwise.
 */
function showConfirm(message) {
    return new Promise(resolve => {
        const loggedDiv = document.getElementById('logged');
        const originalDisplay = loggedDiv.style.display;
        loggedDiv.style.display = 'none';

        const modal_container = document.getElementById('modal-container');
        modal_container.innerHTML = `
            <div class="modal-overlay">
            <div class="modal-content">
                <p>${message}</p>
                <div class="modal-buttons">
                <button class="confirm-btn">Yes</button>
                <button class="cancel-btn" style="margin-top: 10px;">No</button>
                </div>
            </div>
            </div>
        `;
        modal_container.querySelector('.confirm-btn').addEventListener('click', () => {
            modal_container.innerHTML = '';
            loggedDiv.style.display = originalDisplay;
            resolve(true);
        });
        modal_container.querySelector('.cancel-btn').addEventListener('click', () => {
            modal_container.innerHTML = '';
            loggedDiv.style.display = originalDisplay;
            resolve(false);
        });
    });
}



// --- UI LOGIC ---

// Hides or shows specific failure messages in the login form.
function showFailMessage(message_type) {
    $("#failMsg1, #failMsg2, #failMsg3").hide();
    if (message_type >= 1 && message_type <= 3) {
        $(`#failMsg${message_type}`).show();
    }
}

// Switches between the login view and the logged-in view.
function switchUiState(show_login) {
    if (show_login) {
        $("#logged").hide();
        $("#login").show();
    } else {
        $("#login").hide();
        $("#logged").show();
    }
    showFailMessage(0); // Hide all error messages on UI switch.
}

/**
 * Gets the active task by sending a message to the background script.
 * @returns {Promise<number>} The active task ID, or -1 for no task, -2 for error.
 */
async function getActiveTask() {
    try {
        const response = await sendMessageFromPopup({ command: "get_active_task" });
        if (response && response.task_id !== undefined) {
            return response.task_id;
        }
        return -1;
    } catch (error) {
        console.error("Failed to get active task from background script:", error);
        return -2;
    }
}

// Updates the UI to display the current active task status.
async function displayActiveTask() {
    active_task_id = await getActiveTask();
    printDebugOfPopup("Active task ID:", active_task_id);
    if (active_task_id === -1) {
        switchTaskButtonStatus('off');
        $("#active_task").text("No active task").css("color", "#000");
    } else if (active_task_id === -2) {
        switchTaskButtonStatus('off');
        $("#bt_start_task").attr("disabled", true);
        $("#active_task").text("Fail to connect to server").css("color", "#e13636");
    } else {
        switchTaskButtonStatus('on');
        $("#active_task").text("Active task ID: " + active_task_id).css("color", "#000");
    }
    switchUiState(false);
}

// Sets up the UI for a logged-in user.
async function showUserTab() {
    const { username } = await _get_local(['username']);
    $("#username_text_logged").text("User: " + username);
    $("#bt_end_task").hide();
    await displayActiveTask();
}

// Sets up the UI for logging in.
function showLoginTab() {
    switchUiState(true);
}

// --- EVENT HANDLERS ---

// Opens the registration page in a new tab.
function handleRegister() {
    window.open(register_url);
}

async function handleLoginAttempt() {
    let username = $("#username").val();
    let password = $("#password").val();

    if (!username || !password) {
        showAlert("Please enter both username and password.");
        return;
    }

    const credentials = { username: username, password: password, ext: true };
    const login_response = await _post(token_login_url, credentials, true);

    if (login_response && login_response.access) {
        await _set_local({
            'username': username,
            'access_token': login_response.access,
            'refresh_token': login_response.refresh
        });

        await sendMessageFromPopup({ command: "alter_logging_status", log_status: true });
        await showUserTab();
        chrome.action.setBadgeText({ text: 'on' });
        chrome.action.setBadgeBackgroundColor({ color: [202, 181, 225, 255] });
    } else {
        chrome.action.setBadgeText({ text: '' });
        const error_code = login_response ? login_response.error_code : -1;
        const message_map = { 1: 1, 2: 2, default: 3 };
        showFailMessage(message_map[error_code] || message_map.default);
    }
}

// Opens the platform feedback page.
async function handleFeedback() {
    const message = "You are about to go to the task homepage. If you are in the middle of a task, this might interrupt your workflow. Continue?";
    const confirmed = await showConfirm(message);
    if (confirmed) {
        window.open(feedback_url);
    }
}

// Logs the user out.
async function handleLogout() {
    chrome.tabs.query({ active: true, currentWindow: true }, async (tabs) => {
        if (tabs[0]) {
            chrome.tabs.sendMessage(tabs[0].id, { type: "msg_from_popup", update_webpage_info: true });
        }
        await _remove_local(['username', 'access_token', 'refresh_token', 'logged_in']);
        await sendMessageFromPopup({ command: "alter_logging_status", log_status: false });
        chrome.action.setBadgeText({ text: '' });
        location.reload();
    });
}

// // Opens a new window with a specified URL path.
// function openTaskWindow(path, is_new_window = false) {
//     const url = base_url + path;
//     printDebugOfPopup("Opening task window:", url);
//     const window_options = 'height=1000,width=1200,top=0,left=0,toolbar=no,menubar=no,scrollbars=no,resizable=no,location=no,status=no';
//     window.open(url, is_new_window ? 'newwindow' : '_blank', is_new_window ? window_options : undefined);
// }

/**
 * Opens a new window/tab after authenticating the user via a redirect endpoint.
 * This function retrieves the JWT access token and passes it to a server endpoint
 * that validates the token, establishes a session, and redirects to the final destination.
 * * @param {string} path The server path to redirect to after authentication (e.g., '/task/home/').
 * @param {boolean} [is_new_window=false] Whether to open in a new, styled window or a new tab.
 */
async function openTaskWindow(path, is_new_window = false) {
    // 1. Retrieve the access token from storage.
    const { access_token } = await _get_local(['access_token']);

    // 2. Handle the case where the user is not logged in.
    if (!access_token) {
        showAlert("Authentication failed. Please log out and log in again.");
        return;
    }

    // 3. Construct the URL for the authentication bridge endpoint.
    // The target path is encoded to ensure it's safely passed as a query parameter.
    // NOTE: '/user/auth_redirect/' is a new endpoint you'll need to create on your Django backend.
    const encodedPath = encodeURIComponent(path);
    const url = `${base_url}/task/auth_redirect/?token=${access_token}&next=${encodedPath}`;

    printDebugOfPopup("Opening authenticated window via redirect:", url);

    // 4. Open the new window or tab.
    const window_options = 'height=1000,width=1200,top=0,left=0,toolbar=no,menubar=no,scrollbars=no,resizable=no,location=no,status=no';
    window.open(url, is_new_window ? 'newwindow' : '_blank', is_new_window ? window_options : undefined);
}

// Starts a new task.
async function handleStartTask() {
    $("#bt_start_task").attr("disabled", true);
    let current_task_id = await getActiveTask();

    if (current_task_id === -2) {
        showAlert("The server is not available. Please try again later.");
        switchTaskButtonStatus('off');
        return;
    }
    if (current_task_id !== -1) {
        showAlert("There is an active task. Please end the task first.");
        switchTaskButtonStatus('on');
        return;
    }

    const is_confirmed = await showConfirm("Do you want to start a task?");
    if (is_confirmed) {
        const timestamp = _time_now();
        openTaskWindow(`/task/pre_task_annotation/${timestamp}/`);
    } else {
        switchTaskButtonStatus('off');
    }
}

// Ends the current task.
async function handleEndTask() {
    $("#bt_end_task").attr("disabled", true);
    let current_task_id = await getActiveTask();

    if (current_task_id === -2) {
        showAlert("The server is not available. Please try again later.");
        switchTaskButtonStatus('on');
        return;
    }
    if (current_task_id === -1) {
        showAlert("There is no active task to submit.");
        switchTaskButtonStatus('off');
        return;
    }

    const is_confirmed = await showConfirm("Do you want to submit the answer?");
    if (is_confirmed) {
        const active_task = await getActiveTask();
        chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
            if (tabs[0]) {
                chrome.tabs.sendMessage(tabs[0].id, { type: "msg_from_popup", update_webpage_info: true }, () => {
                    const timestamp = _time_now();
                    openTaskWindow(`/task/submit_answer/${current_task_id}/${timestamp}/`);
                    if (active_task < 0) switchTaskButtonStatus('off');
                });
            }
        });
    } else {
        switchTaskButtonStatus('on');
    }
}

// Cancels the current task.
async function handleCancelTask() {
    let current_task_id = await getActiveTask();
    const is_confirmed = await showConfirm("Do you want to cancel the task?");
    if (is_confirmed && current_task_id !== -1) {
        const timestamp = _time_now();
        openTaskWindow(`/task/cancel_task/${current_task_id}/${timestamp}/`, false);
    }
}

// Views details of the current task.
async function handleViewTask() {
    let current_task_id = await getActiveTask();
    if (current_task_id !== -1) {
        const url = `/task/view_task_info/${current_task_id}/`
        openTaskWindow(url, true);
    }
}

// Opens the tool usage page.
function handleToolUse() {
    openTaskWindow('/task/show_tool_use_page/', true);
}

// Manages the enabled/disabled state of task-related buttons.
function switchTaskButtonStatus(task_status) {
    const is_active = task_status === 'on';

    if (is_active) {
        // Task is active: show "Submit Answer" and hide "Start Task"
        $("#bt_start_task").hide();
        $("#bt_end_task").show();
    } else {
        // No active task: show "Start Task" and hide "Submit Answer"
        $("#bt_start_task").show();
        $("#bt_end_task").hide();
    }

    // Set the disabled states for all buttons
    $("#bt_start_task").attr("disabled", is_active);
    $("#bt_end_task").attr("disabled", !is_active);
    $("#bt_cancel_task").attr("disabled", !is_active);
    $("#bt_view_task_info").attr("disabled", !is_active);
    // $("#bt_tool_use").attr("disabled", !is_active); 
}

// --- INITIALIZATION ---
// Main function to set up the popup.
(async function initialize() {
    // Bind event listeners
    $("#bt1").click(handleRegister);
    $("#bt2").click(handleLoginAttempt);
    $("#bt4, #bt8").click(handleFeedback);
    $("#bt6").click(handleLogout);
    $("#bt_start_task").click(handleStartTask);
    $("#bt_end_task").click(handleEndTask);
    $("#bt_cancel_task").click(handleCancelTask);
    $("#bt_view_task_info").click(handleViewTask);
    // $("#bt_tool_use").click(handleToolUse);

    // Check if the user is already logged in.
    const { access_token } = await _get_local(['access_token']);
    if (access_token) {
        await showUserTab();
        await displayActiveTask();
        chrome.action.setBadgeText({ text: 'on' });
        chrome.action.setBadgeBackgroundColor({ color: [202, 181, 225, 255] });
    } else {
        showLoginTab();
        chrome.action.setBadgeText({ text: '' });
    }
})();

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.command === "force_logout_and_reload") {
        location.reload();
    }
});


// Load saved credentials when popup opens
document.addEventListener('DOMContentLoaded', function () {
    chrome.storage.local.get(['savedUsername', 'savedPassword', 'rememberCredentials', 'tempUsername', 'tempPassword'], function (result) {
        // Populate fields with temporary credentials if available
        document.getElementById('username').value = result.tempUsername || '';
        document.getElementById('password').value = result.tempPassword || '';

        // If "Remember Me" was checked, restore saved credentials
        if (result.rememberCredentials) {
            document.getElementById('remember').checked = true;
            if (!result.tempUsername && result.savedUsername) {
                document.getElementById('username').value = result.savedUsername;
            }
            if (!result.tempPassword && result.savedPassword) {
                document.getElementById('password').value = result.savedPassword;
            }
        }
    });

    const usernameInput = document.getElementById('username');
    const passwordInput = document.getElementById('password');
    const rememberCheckbox = document.getElementById('remember');

    // Save temporary credentials on input change
    function saveTempCredentials() {
        chrome.storage.local.set({
            tempUsername: usernameInput.value,
            tempPassword: passwordInput.value
        });
    }

    // Save / clear saved credentials based on checkbox state
    function saveRememberedCredentials() {
        if (rememberCheckbox.checked) {
            chrome.storage.local.set({
                rememberCredentials: true
            });
        } else {
            chrome.storage.local.set({
                rememberCredentials: false
            });
        }
    }

    usernameInput.addEventListener('input', saveTempCredentials);
    passwordInput.addEventListener('input', saveTempCredentials);
    rememberCheckbox.addEventListener('change', saveRememberedCredentials);
});