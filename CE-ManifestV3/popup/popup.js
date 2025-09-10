// --- Configuration ---
const base_url = config.urls.base;
const check_url = config.urls.check;
const login_url = config.urls.login;
const register_url = config.urls.register;
const feedback_url = config.urls.home;

// --- Global State ---
let task_sniffer_interval = null;
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


/**
 * Retrieves user credentials from local storage.
 * @returns {Promise<object>} A promise that resolves with user credentials.
 */
async function getUserCredentials() {
    const result = await chrome.storage.local.get(['username', 'password']);
    return {
        username: result.username || null,
        password: result.password || null
    };
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
}

// Sets up the UI for a logged-in user.
async function showUserTab() {
    switchUiState(false);
    const { username } = await getUserCredentials();
    $("#username_text_logged").text("User: " + username);
    $("#bt_end_task").hide();
    await displayActiveTask();
    if (task_sniffer_interval) clearInterval(task_sniffer_interval);
    task_sniffer_interval = setInterval(displayActiveTask, 3000);
}

// Sets up the UI for logging in.
function showLoginTab() {
    switchUiState(true);
}

/**
 * Verifies user credentials against the server.
 * @returns {Promise<number>} Server status code (0 for success).
 */
async function verifyUser() {
    const credentials = await getUserCredentials();
    printDebugOfPopup("Verifying user credentials:", credentials);
    if (!credentials.username || !credentials.password) {
        return -1;
    }
    const verified_status = await _post(check_url, credentials);
    if (verified_status == null)
        return -2;
    return verified_status;
}

// --- EVENT HANDLERS ---

// Opens the registration page in a new tab.
function handleRegister() {
    window.open(register_url);
}

// Handles the user login attempt.
async function handleLoginAttempt() {
    let username = $("#username").val();
    let password = $("#psw").val();

    printDebugOfPopup("Attempting login with:", { username, password });

    if (!username || !password) {
        showAlert("Please enter both username and password.");
        return;
    }

    await chrome.storage.local.set({ username, password });


    const verified_status = await verifyUser();

    if (verified_status === 0) {
        // Correctly call the login_url after successful verification.
        const credentials = { username, password, ext: true };
        const login_result = await _post(login_url, credentials, false);
        if (login_result !== null) {
            await showUserTab();
            await sendMessageFromPopup({ command: "alter_logging_status", log_status: true });
            chrome.action.setBadgeText({ text: 'on' });
            chrome.action.setBadgeBackgroundColor({ color: [202, 181, 225, 255] });
        } else {
            showAlert("Login failed due to server error. Please try again later.");
        }
    } else {
        chrome.action.setBadgeText({ text: '' });
        const message_map = { 1: 1, 2: 2, default: 3 };
        showFailMessage(message_map[verified_status] || message_map.default);
    }
}

// Opens the platform feedback page.
async function handleFeedback() {
    const confirmed = await showConfirm("Tip: If the task is ongoing, please close the relevant pages before annotating!\nIf not, ignore this message.");
    if (confirmed) {
        window.open(feedback_url);
    }
}

// Logs the user out.
async function handleLogout() {
    if (task_sniffer_interval) clearInterval(task_sniffer_interval);
    await chrome.storage.local.remove(['username', 'password', 'logged_in']);
    await sendMessageFromPopup({ command: "alter_logging_status", log_status: false });
    chrome.action.setBadgeText({ text: '' });
    location.reload();
}

// Opens a new window with a specified URL path.
function openTaskWindow(path, is_new_window = false) {
    const url = base_url + path;
    printDebugOfPopup("Opening task window:", url);
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
        chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
            if (tabs[0]) {
                chrome.tabs.sendMessage(tabs[0].id, { type: "msg_from_popup", update_webpage_info: true }, async () => {
                    const timestamp = _time_now();
                    openTaskWindow(`/task/submit_answer/${current_task_id}/${timestamp}/`);
                    const active_task = await getActiveTask();
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
        const credentials = await getUserCredentials();
        const url = `/task/view_task_info/${current_task_id}/?username=${credentials.username}&password=${credentials.password}`;
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
    $("#bt_cancel_task, #bt_view_task_info, #bt_tool_use").attr("disabled", !is_active);
}

// --- INITIALIZATION ---
// Main function to set up the popup.
(async function initialize() {
    showLoginTab();

    // Bind event listeners
    $("#bt1").click(handleRegister);
    $("#bt2").click(handleLoginAttempt);
    $("#bt4, #bt8").click(handleFeedback);
    $("#bt6").click(handleLogout);
    $("#bt_start_task").click(handleStartTask);
    $("#bt_end_task").click(handleEndTask);
    $("#bt_cancel_task").click(handleCancelTask);
    $("#bt_view_task_info").click(handleViewTask);
    $("#bt_tool_use").click(handleToolUse);

    // Check if the user is already logged in.
    const verified_status = await verifyUser();
    if (verified_status === 0) {
        await showUserTab();
        chrome.action.setBadgeText({ text: 'on' });
        chrome.action.setBadgeBackgroundColor({ color: [202, 181, 225, 255] });
    } else {
        chrome.action.setBadgeText({ text: '' });
    }
})();

