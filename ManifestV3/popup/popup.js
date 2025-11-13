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

function showFailMessage(message_type, customMessage = '') {
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
        if (el) {
            if (customMessage && (errorId === 'requestError' || errorId === 'connectionError' || errorId === 'authError')) {
                el.querySelector('span').textContent = customMessage;
            }
            el.style.display = 'flex';
        }
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
    const { username, update_required, update_info } = await _get_session(['username', 'update_required', 'update_info']);
    document.getElementById('username_text_logged').textContent = "User: " + username;
    
    const startTaskBtn = document.getElementById('startTaskBtn');
    const submitAnswerBtn = document.getElementById('submitAnswerBtn');
    const cancelBtn = document.getElementById('cancelAnnotationBtn');
    const updateBtn = document.getElementById('updateBtn');

    if (update_required) {
        const activeTaskEl = document.getElementById('active_task');
        activeTaskEl.textContent = "Update Required";
        activeTaskEl.style.color = "#e13636";
        document.getElementById('task_trial').textContent = "N/A";
        
        startTaskBtn.style.display = 'none';
        submitAnswerBtn.style.display = 'none';
        cancelBtn.style.display = 'none';
        updateBtn.style.display = 'block';

        updateBtn.onclick = () => {
            window.open(update_info.update_link);
        };

        showAlert(`A new version (${update_info.latest_version}) is available. Please update to continue. <a href="${update_info.update_link}" target="_blank">Update Now</a>.`, "Update Required");
    } else {
        displayActiveTask(task_id, task_info);
        updateBtn.style.display = 'none';
    }
    
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

function updateServerStatusIcon(serverType) {
    const icon = document.getElementById('server-status-icon');
    if (!icon) return;

    if (serverType === 'local') {
        icon.className = 'fas fa-server';
        icon.title = 'Local Mode';
    } else {
        icon.className = 'fas fa-globe';
        icon.title = 'Remote Mode';
    }
}

function applyColors(mainColor, isDarkMode) {
    const originalRed = '#ad0b2a';
    const elegantBlue = '#005f73';
    let dangerColor;

    // If the main color is too close to red, switch to the elegant blue.
    if (colorDistance(mainColor, originalRed) < 100) {
        dangerColor = elegantBlue;
    } else {
        dangerColor = originalRed;
    }
    
    const dangerTextColor = getContrastingTextColor(dangerColor);

    const colors = {
        '--primary-color': mainColor,
        '--primary-color-hover': shadeColor(mainColor, -10), // 10% darker
        '--primary-color-active': shadeColor(mainColor, -20), // 20% darker
        '--danger-color': dangerColor,
        '--danger-color-hover': shadeColor(dangerColor, -10),
        '--danger-text-color': dangerTextColor,
        '--secondary-color': isDarkMode ? '#3A3A3A' : '#f4f4f4',
        '--light-gray': isDarkMode ? '#2f2f2f' : '#f8f9fa',
        '--dark-gray': isDarkMode ? '#ecf0f1' : '#34495e',
        '--white': isDarkMode ? '#3A3A3A' : '#ffffff',
    };

    const root = document.documentElement;
    for (const [key, value] of Object.entries(colors)) {
        root.style.setProperty(key, value);
    }
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
    const { access_token } = await _get_session(['access_token']);
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

async function handleLoginAttempt(force = false) {
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
    if (force) {
        credentials.force = true;
    }
    
    try {
        const config = getConfig();
        const login_response = await _post(config.urls.token_login, credentials, 'form');

        if (login_response?.status === 'already_logged_in') {
            const confirmed = await showConfirm(`You are already logged in on another device (from ${login_response.last_login_from}). Do you want to log out the other device and log in here?`);
            if (confirmed) {
                await handleLoginAttempt(true); // Force login
            } else {
                loginBtn.disabled = false;
                loginBtn.innerHTML = '<i class="fas fa-sign-in-alt"></i> Login';
            }
            return;
        }

        if (login_response?.access && login_response?.refresh) {
            await _set_session({
                'username': username,
                'access_token': login_response.access,
                'refresh_token': login_response.refresh,
                'extension_session_token': login_response.extension_session_token,
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
            showFailMessage(message_map[error_code] || message_map.default, login_response?.error);
            loginBtn.disabled = false;
            loginBtn.innerHTML = '<i class="fas fa-sign-in-alt"></i> Login';
        }
    } catch (error) {
        if (error.message === "Authentication failed.") {
            showFailMessage(4);
        } else {
            showFailMessage(5, error.message);
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
    if (active_task_id !== -1) {
        const confirmed = await showConfirm("Are you sure to log out? If you are in the middle of a task, this might interrupt your workflow and make the data invalid.");
        if (!confirmed) {
            return;
        }
    }
    const tabs = await new Promise(resolve => chrome.tabs.query({ active: true, currentWindow: true }, resolve));
    if (tabs[0] && tabs[0].id) {
        chrome.tabs.sendMessage(tabs[0].id, { type: "msg_from_popup", update_webpage_info: true }, (response) => {
            if (chrome.runtime.lastError) {
                printDebug("popup", "Could not send message to active tab. It might not have a content script. Error: ", chrome.runtime.lastError.message);
            }
        });
    }
    await _remove_session(['username', 'access_token', 'refresh_token', 'logged_in', 'extension_session_token']);
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
            openTaskWindow(`/task/pre_task_annotation/`);
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
                        openTaskWindow(`/task/submit_answer/${current_task_id}/`);
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
            openTaskWindow(`/task/cancel_annotation/${current_task_id}/`, false);
        }
    }
}

async function testConnection(serverType) {
    const address = serverType === 'local' 
        ? document.getElementById('local-server-address').value
        : document.getElementById('remote-server-address').value;

    if (!address) {
        showAlert(`Please enter a ${serverType} server address.`);
        return;
    }

    const btn = document.getElementById(`test-${serverType}-server-btn`);
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';

    try {
        const response = await _get(`${address}/user/health_check/`, 'json');
        // Assuming a successful health check returns a JSON response.
        // The _get function will throw an error for non-ok responses that aren't JSON.
        showAlert(`Successfully connected to the ${serverType} server!`, "Connection Successful");
    } catch (error) {
        if (error.name === 'AbortError') {
            showAlert(`Connection to the ${serverType} server timed out. Please check the server address and your network connection.`, "Connection Timed Out");
        } else {
            showAlert(`An error occurred while trying to connect to the ${serverType} server. Please check the address and your network connection.`, "Connection Error");
        }
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-plug"></i>';
    }
}

// --- INITIALIZATION ---
(async function initialize() {
    await initializeConfig(); // Wait for config to be loaded

    // --- Control Panel Logic ---
    const controlPanelOpenBtn = document.getElementById('control-panel-open-btn');
    const controlPanelCloseBtn = document.getElementById('control-panel-close-btn');
    const controlPanel = document.getElementById('control-panel');
    const saveSettingsBtn = document.getElementById('save-settings-btn');
    const cancelSettingsBtn = document.getElementById('cancel-settings-btn');
    const loginContent = document.getElementById('login');
    const loggedInContent = document.getElementById('logged');
    const header = document.querySelector('.header');
    const localServerAddress = document.getElementById('local-server-address');
    const remoteServerAddress = document.getElementById('remote-server-address');
    const restoreDefaultsBtn = document.getElementById('restore-defaults-btn');
    const positionGrid = document.querySelector('.position-grid');
    const serverChoiceBtns = document.querySelectorAll('.server-choice-btn');
    const scaleSelector = document.getElementById('popup-scale-selector');
    const menuItems = document.querySelectorAll('.menu-item');
    const settingsPanes = document.querySelectorAll('.settings-pane');
    const colorThemeSelector = document.getElementById('color-theme-selector');
    const customColorPicker = document.getElementById('custom-color-picker');
    const themeToggle = document.getElementById('theme-toggle');
    const testLocalServerBtn = document.getElementById('test-local-server-btn');
    const testRemoteServerBtn = document.getElementById('test-remote-server-btn');
    let originalSettings = {};

    const themes = {
        'tsinghua-purple': '#671372',
        'klein-blue': '#002FA7',
        'renmin-red': '#ad0b2a',
        'prussian-blue': '#003153',
        'forest-green': '#1d3124',
        'dark-gray': '#2f2f2f',
        'dark-brown': '#5d3000'
    };
    const darkThemes = {
        'tsinghua-purple': '#d7bde2', // Lighter Purple
        'klein-blue': '#a9cce3',    // Lighter Blue
        'renmin-red': '#f5b7b1',    // Lighter Red
        'prussian-blue': '#aed6f1', // Even Lighter Blue
        'forest-green': '#a9dfbf', // Lighter Green
        'dark-gray': '#e5e7e9',   // Lighter Gray
        'dark-brown': '#f8c471'    // Lighter Orange/Brown
    };

    await loadSettings();


    testLocalServerBtn.addEventListener('click', () => testConnection('local'));
    testRemoteServerBtn.addEventListener('click', () => testConnection('remote'));

    function applyCurrentTheme() {
        const isDarkMode = themeToggle.checked;
        document.body.classList.toggle('dark-mode', isDarkMode);
        updatePaletteSwatches(isDarkMode);

        const activeColorOption = colorThemeSelector.querySelector('.color-option.active');
        const theme = activeColorOption ? activeColorOption.dataset.color : 'custom';
        const customColor = customColorPicker.value;
        applyTheme(theme, customColor);
    }

    themeToggle.addEventListener('change', () => {
        applyCurrentTheme();
    });

    scaleSelector.addEventListener('click', (event) => {
        if (event.target.classList.contains('scale-option')) {
            scaleSelector.querySelectorAll('.scale-option').forEach(option => option.classList.remove('active'));
            event.target.classList.add('active');
            const scaleValue = event.target.dataset.scale;
            document.body.style.zoom = scaleValue;
        }
    });

    colorThemeSelector.addEventListener('click', (event) => {
        if (event.target.classList.contains('color-option')) {
            colorThemeSelector.querySelectorAll('.color-option').forEach(option => option.classList.remove('active'));
            event.target.classList.add('active');
            const theme = event.target.dataset.color;
            applyTheme(theme);
        }
    });

    customColorPicker.addEventListener('input', (event) => {
        const color = event.target.value;
        const isDarkMode = themeToggle.checked;
        const finalColor = isDarkMode ? shadeColor(color, 50) : color; // Increased lightness
        applyColors(finalColor, isDarkMode);
        colorThemeSelector.querySelectorAll('.color-option').forEach(option => option.classList.remove('active'));
    });

    function updatePaletteSwatches(isDarkMode) {
        const palette = isDarkMode ? darkThemes : themes;
        colorThemeSelector.querySelectorAll('.color-option').forEach(option => {
            const colorName = option.dataset.color;
            if (palette[colorName]) {
                option.style.backgroundColor = palette[colorName];
            }
        });
    }

    function applyTheme(theme, customColor) {
        const isDarkMode = themeToggle.checked;
        const selectedThemes = isDarkMode ? darkThemes : themes;
        const color = selectedThemes[theme] || (isDarkMode ? shadeColor(customColor, 50) : customColor) || selectedThemes['tsinghua-purple'];
        
        applyColors(color, isDarkMode);
    }

    menuItems.forEach(item => {
        item.addEventListener('click', () => {
            menuItems.forEach(i => i.classList.remove('active'));
            item.classList.add('active');
            const targetId = item.dataset.target;
            settingsPanes.forEach(pane => {
                pane.classList.toggle('active', pane.id === targetId);
            });
        });
    });

    serverChoiceBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            serverChoiceBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
        });
    });

    async function saveSettings() {
        const activeColorOption = colorThemeSelector.querySelector('.color-option.active');
        const colorTheme = activeColorOption ? activeColorOption.dataset.color : 'custom';
        const customColor = customColorPicker.value;

        await new Promise((resolve) => {
            chrome.storage.local.set({
                serverType: document.querySelector('.server-choice-btn.active').dataset.serverType,
                localServerAddress: localServerAddress.value,
                remoteServerAddress: remoteServerAddress.value,
                messageBoxSize: document.querySelector('.size-btn.active').dataset.size,
                messageBoxPosition: positionGrid.querySelector('.grid-cell.selected').dataset.position,
                popupScale: parseFloat(scaleSelector.querySelector('.scale-option.active').dataset.scale),
                colorTheme,
                customColor,
                darkMode: themeToggle.checked
            }, resolve);
        });
    }

    function applySettingsToPanel(settings) {
        document.querySelectorAll('.server-choice-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.serverType === settings.serverType);
        });
        localServerAddress.value = settings.localServerAddress;
        remoteServerAddress.value = settings.remoteServerAddress;
        
        document.querySelectorAll('.size-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.size === settings.messageBoxSize);
        });
        
        positionGrid.querySelectorAll('.grid-cell').forEach(cell => {
            cell.classList.toggle('selected', cell.dataset.position === settings.messageBoxPosition);
        });

        scaleSelector.querySelectorAll('.scale-option').forEach(option => {
            option.classList.toggle('active', parseFloat(option.dataset.scale) === settings.popupScale);
        });
        document.body.style.zoom = settings.popupScale;

        colorThemeSelector.querySelectorAll('.color-option').forEach(option => {
            option.classList.toggle('active', option.dataset.color === settings.colorTheme);
        });
        
        customColorPicker.value = settings.customColor;
        
        themeToggle.checked = settings.darkMode;
        applyCurrentTheme();
        updatePaletteSwatches(settings.darkMode);
        updateServerStatusIcon(settings.serverType);
    }

    async function loadSettings() {
        const defaultConfig = await sendMessageFromPopup({ command: "get_default_config" });
        const storedSettings = await new Promise((resolve) => {
            chrome.storage.local.get(['serverType', 'localServerAddress', 'remoteServerAddress', 'messageBoxSize', 'messageBoxPosition', 'popupScale', 'colorTheme', 'customColor', 'darkMode'], resolve);
        });

        originalSettings = { ...defaultConfig, ...storedSettings };
        applySettingsToPanel(originalSettings);
    }

    async function openControlPanel() {
        document.body.classList.add('control-panel-active');
        await loadSettings();
        loginContent.style.display = 'none';
        loggedInContent.style.display = 'none';
        controlPanel.style.display = 'block';
        header.style.display = 'none';

        // Activate the "Message Box" tab by default
        menuItems.forEach(i => i.classList.remove('active'));
        settingsPanes.forEach(p => p.classList.remove('active'));

        const defaultMenuItem = document.querySelector('.menu-item[data-target="message-box-settings"]');
        const defaultPane = document.getElementById('message-box-settings');
        
        if (defaultMenuItem && defaultPane) {
            defaultMenuItem.classList.add('active');
            defaultPane.classList.add('active');
        } else {
            // Fallback to the first tab if the default is not found
            menuItems[0]?.classList.add('active');
            settingsPanes[0]?.classList.add('active');
        }
    
        const { logged_in } = await _get_session(['logged_in']);
        const serverSettingsPane = document.getElementById('server-settings');
        const warningMsg = serverSettingsPane.querySelector('.warning-msg');
    
        if (logged_in) {
            // Disable server settings
            serverChoiceBtns.forEach(btn => {
                btn.style.pointerEvents = 'none';
                btn.style.opacity = '0.5';
            });
            localServerAddress.disabled = true;
            remoteServerAddress.disabled = true;
            restoreDefaultsBtn.disabled = false;
    
            // Show a message
            warningMsg.innerHTML = '<i class="fas fa-exclamation-triangle"></i><p>Logout for modifications.</p>';
            warningMsg.style.display = 'flex';
        } else {
            // Ensure server settings are enabled if not logged in
            serverChoiceBtns.forEach(btn => {
                btn.style.pointerEvents = 'auto';
                btn.style.opacity = '1';
            });
            localServerAddress.disabled = false;
            remoteServerAddress.disabled = false;
            restoreDefaultsBtn.disabled = false;
    
            warningMsg.innerHTML = '<i class="fas fa-exclamation-triangle"></i><p>Ask admin before change!</p>';
            warningMsg.style.display = 'flex';
        }
    }

    async function closeControlPanel() {
        document.body.classList.remove('control-panel-active');
        controlPanel.style.display = 'none';
        header.style.display = 'block';
        const { logged_in } = await _get_session(['logged_in']);
        if (logged_in) {
            loggedInContent.style.display = 'block';
        } else {
            loginContent.style.display = 'block';
        }
    }

    saveSettingsBtn.addEventListener('click', async () => {
        const activeColorOption = colorThemeSelector.querySelector('.color-option.active');
        const currentSettings = {
            serverType: document.querySelector('.server-choice-btn.active').dataset.serverType,
            localServerAddress: localServerAddress.value,
            remoteServerAddress: remoteServerAddress.value,
            messageBoxSize: document.querySelector('.size-btn.active').dataset.size,
            messageBoxPosition: positionGrid.querySelector('.grid-cell.selected').dataset.position,
            popupScale: parseFloat(scaleSelector.querySelector('.scale-option.active').dataset.scale),
            colorTheme: activeColorOption ? activeColorOption.dataset.color : 'custom',
            customColor: customColorPicker.value,
            darkMode: themeToggle.checked
        };

        const hasChanged = JSON.stringify(currentSettings) !== JSON.stringify(originalSettings);

        if (hasChanged) {
            await saveSettings();
            sendMessageToContentScript({ 
                size: currentSettings.messageBoxSize, 
                position: currentSettings.messageBoxPosition 
            });
            originalSettings = { ...currentSettings }; // Update original settings to reflect saved state
            updateServerStatusIcon(currentSettings.serverType);
            const infoMsgContainer = document.getElementById('info-msg-container');
            const infoMsgText = document.getElementById('info-msg-text');
            infoMsgText.textContent = 'Saved!';
            infoMsgContainer.style.display = 'flex';
            setTimeout(() => {
                infoMsgContainer.style.display = 'none';
            }, 2000);
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
        const confirmed = await showConfirm("Are you sure you want to restore all settings to their default values?");
        if (confirmed) {
            const { logged_in } = await _get_session(['logged_in']);
            if (logged_in) {
                await showAlert("Server settings cannot be changed while logged in and will be preserved.", "Info");
            }

            const defaultConfig = await sendMessageFromPopup({ command: "get_default_config" });
        
            if (logged_in) {
                // If logged in, only restore message box and appearance settings
                defaultConfig.serverType = originalSettings.serverType;
                defaultConfig.localServerAddress = originalSettings.localServerAddress;
                defaultConfig.remoteServerAddress = originalSettings.remoteServerAddress;
            }
            
            applySettingsToPanel(defaultConfig);
        
            await saveSettings();
            sendMessageToContentScript({ 
                size: defaultConfig.messageBoxSize, 
                position: defaultConfig.messageBoxPosition 
            });
            updateServerStatusIcon(defaultConfig.serverType);

            originalSettings = { ...defaultConfig };
        
            const infoMsgContainer = document.getElementById('info-msg-container');
            const infoMsgText = document.getElementById('info-msg-text');
            infoMsgText.textContent = "Defaults Restored!";
            infoMsgContainer.style.display = 'flex';
            setTimeout(() => {
                infoMsgContainer.style.display = 'none';
            }, 2000);
        }
    });

    async function handleCloseControlPanel() {
        const activeColorOption = colorThemeSelector.querySelector('.color-option.active');
        const currentSettings = {
            serverType: document.querySelector('.server-choice-btn.active').dataset.serverType,
            localServerAddress: localServerAddress.value,
            remoteServerAddress: remoteServerAddress.value,
            messageBoxSize: document.querySelector('.size-btn.active').dataset.size,
            messageBoxPosition: positionGrid.querySelector('.grid-cell.selected').dataset.position,
            popupScale: parseFloat(scaleSelector.querySelector('.scale-option.active').dataset.scale),
            colorTheme: activeColorOption ? activeColorOption.dataset.color : 'custom',
            customColor: customColorPicker.value,
            darkMode: themeToggle.checked
        };

        const hasChanged = JSON.stringify(currentSettings) !== JSON.stringify(originalSettings);

        if (hasChanged) {
            const confirmed = await showConfirm("You have unsaved changes. Do you want to discard them?");
            if (confirmed) {
                applySettingsToPanel(originalSettings);
                await closeControlPanel();
            }
        } else {
            await closeControlPanel();
        }
    }

    controlPanelOpenBtn.addEventListener('click', async () => {
        if (controlPanel.style.display !== 'block') { // If control panel is open
            await openControlPanel();
        }
    });

    controlPanelCloseBtn.addEventListener('click', async () => {
        if (controlPanel.style.display === 'block') { // If control panel is open
            await handleCloseControlPanel();
        }
    });

    cancelSettingsBtn.addEventListener('click', handleCloseControlPanel);

    function sendMessageToContentScript(style, retries = 3) {
        chrome.tabs.query({ active: true, currentWindow: true }, function(tabs) {
            if (tabs[0] && tabs[0].id) {
                chrome.tabs.sendMessage(tabs[0].id, {
                    type: "update_message_box_style",
                    style: style
                }, function(response) {
                    if (chrome.runtime.lastError || !response?.success) {
                        if (retries > 0) {
                            setTimeout(() => {
                                sendMessageToContentScript(style, retries - 1);
                            }, 100);
                        } else {
                            console.error("Failed to send message to content script after multiple retries.");
                        }
                    }
                });
            }
        });
    }

    const sizeBtns = document.querySelectorAll('.size-btn');

    sizeBtns.forEach(btn => {
        btn.addEventListener('click', (event) => {
            sizeBtns.forEach(b => b.classList.remove('active'));
            event.target.classList.add('active');
        });
    });

    positionGrid.addEventListener('click', (event) => {
        if (event.target.classList.contains('grid-cell')) {
            positionGrid.querySelectorAll('.grid-cell').forEach(cell => cell.classList.remove('selected'));
            event.target.classList.add('selected');
        }
    });


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