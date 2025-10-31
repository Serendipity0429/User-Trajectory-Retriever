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
    const errorMessages = {
        1: 'usernameError',
        2: 'passwordError',
        3: 'requestError',
        4: 'authError',
        5: 'connectionError'
    };

    Object.values(errorMessages).forEach(id => {
        const el = document.getElementById(id);
        if (el) el.style.display = 'none';
    });

    const errorId = errorMessages[message_type];
    if (errorId) {
        const el = document.getElementById(errorId);
        if (el) el.style.display = 'flex';
    }
}

function switchUiState(show_login) {
    let loggedDiv = document.getElementById('logged');
    let loginDiv = document.getElementById('login');
    if (show_login) { // Display login interface
        loggedDiv.style.display = 'none';
        loginDiv.style.display = 'block';
    } else { // Display logged-in interface
        loginDiv.style.display = 'none';
        loggedDiv.style.display = 'block';
    }
    showFailMessage(0);
}

function displayActiveTask(task_id, task_info) {
    active_task_id = task_id;
    printDebug("popup", "Active task ID:", active_task_id);
    const activeTaskEl = document.getElementById('active_task');
    const startTaskBtn = document.getElementById('startTaskBtn');
    const taskTrialEl = document.getElementById('task_trial');
    const config = getConfig();

    if (active_task_id === -1) {
        switchTaskButtonStatus('off');
        activeTaskEl.textContent = "No active task";
        activeTaskEl.style.color = "";
        taskTrialEl.textContent = "0";
    } else if (active_task_id === -2) {
        switchTaskButtonStatus('off');
        startTaskBtn.setAttribute("disabled", "true");
        activeTaskEl.textContent = "Connection Error";
        activeTaskEl.style.color = "#e13636";
        taskTrialEl.textContent = "0";
    } else {
        if (task_info) {
            taskTrialEl.textContent = task_info.trial_num;
            switchTaskButtonStatus('on', task_info.trial_num);
        } else {
            taskTrialEl.textContent = "N/A";
            switchTaskButtonStatus('on', 0);
        }
        activeTaskEl.textContent = active_task_id;
        activeTaskEl.style.color = "";
    }
}

async function showUserTab(task_id, task_info) {
    const { username } = await _get_local(['username']);
    document.getElementById('username_text_logged').textContent = "User: " + username;
    document.getElementById('submitAnswerBtn').style.display = 'none';
    printDebug("popup", "Switched to user tab for user:", username);    
    displayActiveTask(task_id, task_info);
    switchUiState(false);
}

function showLoginTab() {
    switchUiState(true);
    const loginBtn = document.getElementById('loginBtn');
    if (loginBtn) {
        loginBtn.disabled = false;
        loginBtn.innerHTML = '<i class="fas fa-sign-in-alt"></i> Login';
    }
    const usernameInput = document.getElementById('username');
    if (usernameInput) {
        setTimeout(() => usernameInput.focus(), 100);
    }
}

function switchTaskButtonStatus(task_status, trial_num = 0) {
    const is_active = task_status === 'on';
    const startTaskBtn = document.getElementById('startTaskBtn');
    const endTaskBtn = document.getElementById('submitAnswerBtn');
    const cancelTaskBtn = document.getElementById('cancelAnnotationBtn');
    const config = getConfig();

    startTaskBtn.style.display = is_active ? 'none' : 'block';
    endTaskBtn.style.display = is_active ? 'block' : 'none';
    cancelTaskBtn.style.display = config.is_dev || trial_num > config.cancel_trial_threshold ? 'block' : 'none';

    startTaskBtn.disabled = is_active;
    endTaskBtn.disabled = !is_active;
    cancelTaskBtn.disabled = !is_active;
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

async function getTaskInfo(task_id) {
    try {
        const response = await sendMessageFromPopup({ command: "get_task_info", task_id: task_id });
        return response;
    } catch (error) {
        console.error("Failed to get task info from background script:", error);
        return null;
    }
}

async function getJustifications(task_id) {
    try {
        const response = await sendMessageFromPopup({ command: "get_justifications", task_id: task_id });
        return response;
    } catch (error) {
        console.error("Failed to get justifications from background script:", error);
        return null;
    }
}

async function openTaskWindow(path, is_new_window = false) {
    const { access_token } = await _get_local(['access_token']);
    if (!access_token) {
        showAlert("Authentication failed. Please log out and log in again.");
        return;
    }
    const config = getConfig();
    const encodedPath = encodeURIComponent(path);
    const url = `${config.urls.base}/task/auth_redirect/?token=${access_token}&next=${encodedPath}`;
    const window_options = 'height=1000,width=1200,top=0,left=0,toolbar=no,menubar=no,scrollbars=no,resizable=no,location=no,status=no';
    window.open(url, is_new_window ? 'newwindow' : '_blank', is_new_window ? window_options : undefined);
}

// --- EVENT HANDLERS ---

function handleRegister() {
    const config = getConfig();
    window.open(config.urls.register);
}

async function handleLoginAttempt() {
    const loginBtn = document.getElementById('loginBtn');
    loginBtn.disabled = true;
    loginBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Logging in...';

    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;

    if (!username || !password) {
        showAlert("Please enter both username and password.");
        loginBtn.disabled = false;
        loginBtn.innerHTML = '<i class="fas fa-sign-in-alt"></i> Login';
        return;
    }

    const credentials = { username, password, ext: true };
    try {
        const config = getConfig();
        const login_response = await _post(config.urls.token_login, credentials, 'form');
        if (login_response?.access && login_response?.refresh) {
            await _set_local({
                'username': username,
                'access_token': login_response.access,
                'refresh_token': login_response.refresh,
                'logged_in': true
            });
            await sendMessageFromPopup({ command: "alter_logging_status", log_status: true });
            const response = await sendMessageFromPopup({ command: "get_popup_data" });
            await showUserTab(response.task_id, response.task_info);
            chrome.action.setBadgeText({ text: 'off' });
            chrome.action.setBadgeTextColor({ color: '#ffffff' });
            chrome.action.setBadgeBackgroundColor({ color: '#660874' });
        } else {
            chrome.action.setBadgeText({ text: '' });
            const error_code = login_response?.error_code ?? -1;
            const message_map = { 1: 1, 2: 2, 4: 4, default: 4 };
            showFailMessage(message_map[error_code] || message_map.default);
            loginBtn.disabled = false;
            loginBtn.innerHTML = '<i class="fas fa-sign-in-alt"></i> Login';
        }
    } catch (error) {
        if (error.message === "Authentication failed.") {
            showFailMessage(4);
        } else {
            showFailMessage(5);
        }
        loginBtn.disabled = false;
        loginBtn.innerHTML = '<i class="fas fa-sign-in-alt"></i> Login';
    }
}

async function handleFeedback() {
    const confirmed = await showConfirm("You are about to go to the task homepage. If you are in the middle of a task, this might interrupt your workflow. Continue?");
    if (confirmed) {
        const config = getConfig();
        window.open(config.urls.home);
    }
}

async function handleFeedbackUnlogged() {
    const confirmed = await showConfirm("You are about to go to the task homepage. Continue?");
    if (confirmed) {
        const config = getConfig();
        window.open(config.urls.home);
    }
}


async function handleLogout() {
    const tabs = await new Promise(resolve => chrome.tabs.query({ active: true, currentWindow: true }, resolve));
    if (tabs[0] && tabs[0].id) {
        chrome.tabs.sendMessage(tabs[0].id, { type: "msg_from_popup", update_webpage_info: true }, (response) => {
            if (chrome.runtime.lastError) {
                printDebug("popup", "Could not send message to active tab. It might not have a content script. Error: ", chrome.runtime.lastError.message);
            }
        });
    }
    await _remove_local(['username', 'access_token', 'refresh_token', 'logged_in']);
    await sendMessageFromPopup({ command: "alter_logging_status", log_status: false });
    chrome.action.setBadgeText({ text: '' });
    showLoginTab();
}

async function handleStartTask() {
    document.getElementById('startTaskBtn').disabled = true;
    const current_task_id = await getActiveTask();

    if (current_task_id === -2) {
        
    } else if (current_task_id !== -1) {
        showAlert("There is an active task. Please end the task first.");
    } else {
        const is_confirmed = await showConfirm("Do you want to start a task?");
        if (is_confirmed) {
            const timestamp = Date.now();
            openTaskWindow(`/task/pre_task_annotation/${timestamp}/`);
        }
    }
    document.getElementById('startTaskBtn').disabled = false;
}

async function handleEndTask() {
    document.getElementById('submitAnswerBtn').disabled = true;
    const current_task_id = await getActiveTask();

    if (current_task_id === -2) {
        
    } else if (current_task_id === -1) {
        showAlert("There is no active task to submit.");
    } else {
        const justifications = await getJustifications(current_task_id);
        if (justifications && justifications.justifications.length > 0) {
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
        } else {
            showAlert("You must collect at least one piece of evidence before submitting your answer.");
        }
    }
    document.getElementById('submitAnswerBtn').disabled = false;
}

async function handleCancelTask() {
    const current_task_id = await getActiveTask();
    if (current_task_id === -2) {
        return;
    }
    if (current_task_id !== -1) {
        const is_confirmed = await showConfirm("Do you want to cancel the task?");
        if (is_confirmed) {
            const timestamp = Date.now();
            openTaskWindow(`/task/cancel_annotation/${current_task_id}/${timestamp}/`, false);
        }
    }
}

// --- INITIALIZATION ---
(async function initialize() {
    await initializeConfig(); // Wait for config to be loaded

    // --- Control Panel Logic ---
    const controlPanelBtn = document.getElementById('control-panel-btn');
    const controlPanel = document.getElementById('control-panel');
    const saveSettingsBtn = document.getElementById('save-settings-btn');
    const cancelSettingsBtn = document.getElementById('cancel-settings-btn');
    const loginContent = document.getElementById('login');
    const loggedInContent = document.getElementById('logged');
    const localServerAddress = document.getElementById('local-server-address');
    const remoteServerAddress = document.getElementById('remote-server-address');
    const restoreDefaultsBtn = document.getElementById('restore-defaults-btn');
    let originalSettings = {};

    async function saveSettings() {
        const serverType = document.querySelector('input[name="server-type"]:checked').value;
        const localAddress = localServerAddress.value;
        const remoteAddress = remoteServerAddress.value;
        
        await new Promise((resolve) => {
            chrome.storage.local.set({
                serverType: serverType,
                localServerAddress: localAddress,
                remoteServerAddress: remoteAddress
            }, resolve);
        });
    }

    async function loadSettings() {
        const result = await new Promise((resolve) => {
            chrome.storage.local.get(['serverType', 'localServerAddress', 'remoteServerAddress'], resolve);
        });

        originalSettings = {
            serverType: result.serverType || 'local',
            localServerAddress: result.localServerAddress || '',
            remoteServerAddress: result.remoteServerAddress || ''
        };

        document.getElementById('server-type-' + originalSettings.serverType).checked = true;
        localServerAddress.value = originalSettings.localServerAddress;
        remoteServerAddress.value = originalSettings.remoteServerAddress;
    }

    async function openControlPanel() {
        await loadSettings();
        loginContent.style.display = 'none';
        loggedInContent.style.display = 'none';
        controlPanel.style.display = 'block';
    }

    async function closeControlPanel() {
        controlPanel.style.display = 'none';
        const { logged_in } = await _get_local(['logged_in']);
        if (logged_in) {
            loggedInContent.style.display = 'block';
        } else {
            loginContent.style.display = 'block';
        }
    }

    saveSettingsBtn.addEventListener('click', async () => {
        const currentSettings = {
            serverType: document.querySelector('input[name="server-type"]:checked').value,
            localServerAddress: localServerAddress.value,
            remoteServerAddress: remoteServerAddress.value
        };

        const hasChanged = JSON.stringify(currentSettings) !== JSON.stringify(originalSettings);

        if (hasChanged) {
            const confirmed = await showConfirm("You have unsaved changes. Do you want to save them?");
            if (confirmed) {
                await saveSettings();
                originalSettings = { ...currentSettings }; // Update original settings to reflect saved state
                const infoMsgContainer = document.getElementById('info-msg-container');
                const infoMsgText = document.getElementById('info-msg-text');
                infoMsgText.textContent = 'Saved!';
                infoMsgContainer.style.display = 'flex';
                setTimeout(() => {
                    infoMsgContainer.style.display = 'none';
                }, 2000);
            }
        } else {
            const infoMsgContainer = document.getElementById('info-msg-container');
            const infoMsgText = document.getElementById('info-msg-text');
            infoMsgText.textContent = 'No changes to save.';
            infoMsgContainer.style.display = 'flex';
            setTimeout(() => {
                infoMsgContainer.style.display = 'none';
            }, 2000);
        }
    });

    restoreDefaultsBtn.addEventListener('click', async () => {
        const defaultConfig = {
            serverType: 'local',
            localServerAddress: 'http://127.0.0.1:8000',
            remoteServerAddress: 'http://101.6.41.59:32904',
        };

        document.getElementById('server-type-' + defaultConfig.serverType).checked = true;
        localServerAddress.value = defaultConfig.localServerAddress;
        remoteServerAddress.value = defaultConfig.remoteServerAddress;

        await saveSettings();

        const infoMsgContainer = document.getElementById('info-msg-container');
        const infoMsgText = document.getElementById('info-msg-text');
        infoMsgText.textContent = "Defaults Restored!";
        infoMsgContainer.style.display = 'flex';
        setTimeout(() => {
            infoMsgContainer.style.display = 'none';
        }, 2000);
    });

    async function handleCloseControlPanel() {
        const currentSettings = {
            serverType: document.querySelector('input[name="server-type"]:checked').value,
            localServerAddress: localServerAddress.value,
            remoteServerAddress: remoteServerAddress.value
        };

        const hasChanged = JSON.stringify(currentSettings) !== JSON.stringify(originalSettings);

        if (hasChanged) {
            const confirmed = await showConfirm("You have unsaved changes. Do you want to discard them?");
            if (confirmed) {
                await closeControlPanel();
            }
        } else {
            await closeControlPanel();
        }
    }

    controlPanelBtn.addEventListener('click', async () => {
        if (controlPanel.style.display === 'block') { // If control panel is open
            await handleCloseControlPanel();
        } else { // If control panel is closed
            await openControlPanel();
        }
    });

    cancelSettingsBtn.addEventListener('click', handleCloseControlPanel);


    // --- Original Initialization Logic ---
    document.getElementById('signupBtn').addEventListener('click', handleRegister);
    document.getElementById('loginBtn').addEventListener('click', handleLoginAttempt);
    document.getElementById('homeBtnLoggedOut').addEventListener('click', handleFeedbackUnlogged);
    document.getElementById('homeBtnLoggedIn').addEventListener('click', handleFeedback);
    document.getElementById('logoutBtn').addEventListener('click', handleLogout);
    document.getElementById('startTaskBtn').addEventListener('click', handleStartTask);
    document.getElementById('submitAnswerBtn').addEventListener('click', handleEndTask);
    document.getElementById('cancelAnnotationBtn').addEventListener('click', handleCancelTask);
    document.getElementById('pendingAnnotationBtn').addEventListener('click', () => {
        sendMessageFromPopup({ command: "get_popup_data" }).then(response => {
            if (response.pending_url) {
                openTaskWindow(response.pending_url);
            }
        });
    });

    const response = await sendMessageFromPopup({ command: "get_popup_data" });
    if (response.log_status) {
        await showUserTab(response.task_id, response.task_info);
        const pendingBtn = document.getElementById('pendingAnnotationBtn');
        const submitBtn = document.getElementById('submitAnswerBtn');
        const cancelBtn = document.getElementById('cancelAnnotationBtn');
        const startTaskBtn = document.getElementById('startTaskBtn');

        if (response.pending_url) {
            showAlert("You have a pending annotation.", "Pending Annotation");
            pendingBtn.style.display = 'block';
            submitBtn.style.display = 'none';
            cancelBtn.style.display = 'none';
            startTaskBtn.style.display = 'none';
        } else {
            pendingBtn.style.display = 'none';
        }
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

    const togglePassword = document.querySelector('#togglePassword');
    const password = document.querySelector('#password');

    togglePassword.addEventListener('click', function (e) {
        // toggle the type attribute
        const type = password.getAttribute('type') === 'password' ? 'text' : 'password';
        password.setAttribute('type', type);
        // toggle the eye / eye slash icon
        this.classList.toggle('fa-eye');
        this.classList.toggle('fa-eye-slash');
    });

    const loginBtn = document.getElementById('loginBtn');

    usernameInput.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            passwordInput.focus();
        }
    });

    passwordInput.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            loginBtn.click();
        }
    });
});