// --- Configuration ---
const base_url = config.urls.base;
const token_login_url = config.urls.token_login;
const register_url = config.urls.register;
const feedback_url = config.urls.home;

// --- Global State ---
let active_task_id = -1;

// --- UI LOGIC ---

function showAlert(message, title = "Alert") {
    const modal_container = document.getElementById('modal-container');
    modal_container.innerHTML = `
        <div class="modal-overlay">
            <div class="modal-content">
                <div class="modal-header">
                    <i class="fas fa-exclamation-circle" style="color: #f39c12;"></i>
                    <h3>${title}</h3>
                </div>
                <p>${message}</p>
                <div class="modal-buttons">
                    <button class="ok-btn btn">OK</button>
                </div>
            </div>
        </div>
    `;
    modal_container.querySelector('.ok-btn').addEventListener('click', () => {
        modal_container.innerHTML = '';
    });
}

function showConfirm(message, title = "Confirm") {
    return new Promise(resolve => {
        const modal_container = document.getElementById('modal-container');
        modal_container.innerHTML = `
            <div class="modal-overlay">
                <div class="modal-content">
                    <div class="modal-header">
                        <i class="fas fa-question-circle"></i>
                        <h3>${title}</h3>
                    </div>
                    <p>${message}</p>
                    <div class="modal-buttons">
                        <button class="confirm-btn btn">Yes</button>
                        <button class="cancel-btn btn btn-secondary">No</button>
                    </div>
                </div>
            </div>
        `;
        modal_container.querySelector('.confirm-btn').addEventListener('click', () => {
            modal_container.innerHTML = '';
            resolve(true);
        });
        modal_container.querySelector('.cancel-btn').addEventListener('click', () => {
            modal_container.innerHTML = '';
            resolve(false);
        });
    });
}

function showFailMessage(message_type) {
    for (let i = 1; i <= 3; i++) {
        const failMsg = document.getElementById(`failMsg${i}`);
        if (failMsg) {
            failMsg.style.display = 'none';
        }
    }
    if (message_type >= 1 && message_type <= 3) {
        const failMsg = document.getElementById(`failMsg${message_type}`);
        if (failMsg) {
            failMsg.style.display = 'flex';
        }
    }
}

function switchUiState(show_login) {
    const loggedDiv = document.getElementById('logged');
    const loginDiv = document.getElementById('login');
    if (show_login) {
        loggedDiv.style.display = 'none';
        loginDiv.style.display = 'block';
    } else {
        loginDiv.style.display = 'none';
        loggedDiv.style.display = 'block';
    }
    showFailMessage(0);
}

async function displayActiveTask() {
    active_task_id = await getActiveTask();
    printDebug("popup", "Active task ID:", active_task_id);
    const activeTaskEl = document.getElementById('active_task');
    const startTaskBtn = document.getElementById('bt_start_task');

    if (active_task_id === -1) {
        switchTaskButtonStatus('off');
        activeTaskEl.textContent = "No active task";
        activeTaskEl.style.color = "#000";
    } else if (active_task_id === -2) {
        switchTaskButtonStatus('off');
        startTaskBtn.setAttribute("disabled", "true");
        activeTaskEl.textContent = "Fail to connect to server";
        activeTaskEl.style.color = "#e13636";
    } else {
        switchTaskButtonStatus('on');
        activeTaskEl.textContent = "Active task ID: " + active_task_id;
        activeTaskEl.style.color = "#000";
    }
}

async function showUserTab() {
    const { username } = await _get_local(['username']);
    document.getElementById('username_text_logged').textContent = "User: " + username;
    document.getElementById('bt_end_task').style.display = 'none';
    await displayActiveTask();
    switchUiState(false);
}

function showLoginTab() {
    switchUiState(true);
}

function switchTaskButtonStatus(task_status) {
    const is_active = task_status === 'on';
    const startTaskBtn = document.getElementById('bt_start_task');
    const endTaskBtn = document.getElementById('bt_end_task');
    const cancelTaskBtn = document.getElementById('bt_cancel_task');
    const viewTaskInfoBtn = document.getElementById('bt_view_task_info');

    startTaskBtn.style.display = is_active ? 'none' : 'block';
    endTaskBtn.style.display = is_active ? 'block' : 'none';

    startTaskBtn.disabled = is_active;
    endTaskBtn.disabled = !is_active;
    cancelTaskBtn.disabled = !is_active;
    viewTaskInfoBtn.disabled = !is_active;
}

// --- API CALLS ---

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

async function getActiveTask() {
    try {
        const response = await sendMessageFromPopup({ command: "get_active_task" });
        return response?.task_id ?? -1;
    } catch (error) {
        console.error("Failed to get active task from background script:", error);
        return -2;
    }
}

async function openTaskWindow(path, is_new_window = false) {
    const { access_token } = await _get_local(['access_token']);
    if (!access_token) {
        showAlert("Authentication failed. Please log out and log in again.");
        return;
    }
    const encodedPath = encodeURIComponent(path);
    const url = `${base_url}/task/auth_redirect/?token=${access_token}&next=${encodedPath}`;
    const window_options = 'height=1000,width=1200,top=0,left=0,toolbar=no,menubar=no,scrollbars=no,resizable=no,location=no,status=no';
    window.open(url, is_new_window ? 'newwindow' : '_blank', is_new_window ? window_options : undefined);
}

// --- EVENT HANDLERS ---

function handleRegister() {
    window.open(register_url);
}

async function handleLoginAttempt() {
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;

    if (!username || !password) {
        showAlert("Please enter both username and password.");
        return;
    }

    const credentials = { username, password, ext: true };
    try {
        const login_response = await _post(token_login_url, credentials, true);
        if (login_response?.access && login_response?.refresh) {
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
            const error_code = login_response?.error_code ?? -1;
            const message_map = { 1: 1, 2: 2, default: 3 };
            showFailMessage(message_map[error_code] || message_map.default);
        }
    } catch (error) {
        showFailMessage(3);
    }
}

async function handleFeedback() {
    const confirmed = await showConfirm("You are about to go to the task homepage. If you are in the middle of a task, this might interrupt your workflow. Continue?");
    if (confirmed) {
        window.open(feedback_url);
    }
}

async function handleFeedbackUnlogged() {
    const confirmed = await showConfirm("You are about to go to the task homepage. Continue?");
    if (confirmed) {
        window.open(feedback_url);
    }
}


async function handleLogout() {
    const tabs = await new Promise(resolve => chrome.tabs.query({ active: true, currentWindow: true }, resolve));
    if (tabs[0]) {
        chrome.tabs.sendMessage(tabs[0].id, { type: "msg_from_popup", update_webpage_info: true });
    }
    await _remove_local(['username', 'access_token', 'refresh_token', 'logged_in']);
    await sendMessageFromPopup({ command: "alter_logging_status", log_status: false });
    chrome.action.setBadgeText({ text: '' });
    showLoginTab();
}

async function handleStartTask() {
    document.getElementById('bt_start_task').disabled = true;
    const current_task_id = await getActiveTask();

    if (current_task_id === -2) {
        showAlert("The server is not available. Please try again later.");
    } else if (current_task_id !== -1) {
        showAlert("There is an active task. Please end the task first.");
    } else {
        const is_confirmed = await showConfirm("Do you want to start a task?");
        if (is_confirmed) {
            const timestamp = Date.now();
            openTaskWindow(`/task/pre_task_annotation/${timestamp}/`);
        }
    }
    document.getElementById('bt_start_task').disabled = false;
}

async function handleEndTask() {
    document.getElementById('bt_end_task').disabled = true;
    const current_task_id = await getActiveTask();

    if (current_task_id === -2) {
        showAlert("The server is not available. Please try again later.");
    } else if (current_task_id === -1) {
        showAlert("There is no active task to submit.");
    } else {
        const is_confirmed = await showConfirm("Do you want to submit the answer?");
        if (is_confirmed) {
            const tabs = await new Promise(resolve => chrome.tabs.query({ active: true, currentWindow: true }, resolve));
            if (tabs[0]) {
                chrome.tabs.sendMessage(tabs[0].id, { type: "msg_from_popup", update_webpage_info: true }, () => {
                    const timestamp = Date.now();
                    openTaskWindow(`/task/submit_answer/${current_task_id}/${timestamp}/`);
                });
            }
        }
    }
    document.getElementById('bt_end_task').disabled = false;
}

async function handleCancelTask() {
    const current_task_id = await getActiveTask();
    if (current_task_id !== -1) {
        const is_confirmed = await showConfirm("Do you want to cancel the task?");
        if (is_confirmed) {
            const timestamp = Date.now();
            openTaskWindow(`/task/cancel_task/${current_task_id}/${timestamp}/`, false);
        }
    }
}

async function handleViewTask() {
    const current_task_id = await getActiveTask();
    if (current_task_id !== -1) {
        openTaskWindow(`/task/view_task_info/${current_task_id}/`, true);
    }
}

// --- INITIALIZATION ---
(async function initialize() {
    document.getElementById('bt1').addEventListener('click', handleRegister);
    document.getElementById('bt2').addEventListener('click', handleLoginAttempt);
    document.getElementById('bt4').addEventListener('click', handleFeedbackUnlogged);
    document.getElementById('bt8').addEventListener('click', handleFeedback);
    document.getElementById('bt6').addEventListener('click', handleLogout);
    document.getElementById('bt_start_task').addEventListener('click', handleStartTask);
    document.getElementById('bt_end_task').addEventListener('click', handleEndTask);
    document.getElementById('bt_cancel_task').addEventListener('click', handleCancelTask);
    document.getElementById('bt_view_task_info').addEventListener('click', handleViewTask);

    const { access_token } = await _get_local(['access_token']);
    if (access_token) {
        await showUserTab();
        chrome.action.setBadgeText({ text: 'on' });
        chrome.action.setBadgeBackgroundColor({ color: [202, 181, 225, 255] });
    } else {
        showLoginTab();
        chrome.action.setBadgeText({ text: '' });
    }
})();

chrome.runtime.onMessage.addListener((message) => {
    if (message.command === "force_logout_and_reload") {
        showLoginTab();
    }
});

document.addEventListener('DOMContentLoaded', function () {
    chrome.storage.local.get(['savedUsername', 'savedPassword', 'rememberCredentials', 'tempUsername', 'tempPassword'], function (result) {
        document.getElementById('username').value = result.tempUsername || '';
        document.getElementById('password').value = result.tempPassword || '';

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

    function saveTempCredentials() {
        chrome.storage.local.set({
            tempUsername: usernameInput.value,
            tempPassword: passwordInput.value
        });
    }

    function saveRememberedCredentials() {
        if (rememberCheckbox.checked) {
            chrome.storage.local.set({
                rememberCredentials: true,
                savedUsername: usernameInput.value,
                savedPassword: passwordInput.value
            });
        } else {
            chrome.storage.local.set({
                rememberCredentials: false,
                savedUsername: '',
                savedPassword: ''
            });
        }
    }

    usernameInput.addEventListener('input', saveTempCredentials);
    passwordInput.addEventListener('input', saveTempCredentials);
    rememberCheckbox.addEventListener('change', saveRememberedCredentials);
});