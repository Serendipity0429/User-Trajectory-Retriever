var debug = false;
var baseUrl = "http://127.0.0.1:8000";
var checkUrl = baseUrl + "/user/check/";
var loginUrl = baseUrl + "/user/login/";
var registerUrl = baseUrl + "/user/signup/";
var feedbackUrl = baseUrl + "/task/home/";
var downloadLink = "";
var taskSniff = null;
var logged_in = false;
var task_id = -1;


// 封装通用的API请求函数
async function makeApiRequest(url, data = {}) {
    try {
        const response = await $.ajax({
            type: "POST",
            url: url,
            dataType: 'json',
            data: data
        });
        return response;
    } catch (error) {
        console.error(`API request failed: ${url}`, error);
        return -2;
    }
}

// 封装用户认证数据获取
function getUserCredentials() {
    return {
        username: localStorage['username'],
        password: localStorage['password']
    };
}

// 封装消息显示逻辑
function showFailMessage(messageType) {
    $("#failMsg1, #failMsg2, #failMsg3").hide();
    if (messageType >= 1 && messageType <= 3) {
        $(`#failMsg${messageType}`).show();
    }
}

// 封装UI切换逻辑
function switchUIState(showLogin) {
    if (showLogin) {
        $("#logged").hide();
        $("#login").show();
    } else {
        $("#login").hide();
        $("#logged").show();
    }
    showFailMessage(0); // 隐藏所有错误消息
}

async function displayActiveTask() {
    task_id = await getActiveTask();
    if (task_id == -1) {
        // No active task
        switchTaskButtonStatus('off');
        $("#active_task").text("No active task");
        $("#active_task").css("color", "#000");
    } else if (task_id == -2) {
        switchTaskButtonStatus('off')
        $("#bt_start_task").attr("disabled", true);
        $("#active_task").text("Fail to connect to server");
        $("#active_task").css("color", "#e13636");
    } else { // There is an active task
        switchTaskButtonStatus('on');
        $("#active_task").text("Active task ID: " + task_id);
        $("#active_task").css("color", "#000");
    }
}

function userTab() {
    switchUIState(false);
    $("#username_text_logged").text("User " + localStorage['username']);
    $("#bt_end_task").hide();
    displayActiveTask();
    // Routinely check whether there is an active task
    taskSniff = setInterval(displayActiveTask, 3000);
}

function loginTab() {
    switchUIState(true);
}

async function initializeServer() {
    const credentials = getUserCredentials();
    const result = await makeApiRequest(baseUrl + "/task/initialize/", credentials);
    
    if (result != -1) { // There is an active task
        switchTaskButtonStatus('on');
    }
    return result;
}

async function verifyUser() {
    if (!localStorage['username'] || !localStorage['password']) {
        return -1;
    }
    
    const credentials = getUserCredentials();
    const result = await makeApiRequest(checkUrl, credentials);
    
    // 返回具体的验证结果
    return result
}

async function userLogin() {
    if (!localStorage['username'] || !localStorage['password']) {
        return;
    }
    
    const credentials = getUserCredentials();
    credentials.ext = true;
    
    await makeApiRequest(loginUrl, credentials);
    chrome.runtime.sendMessage({log_request: 'on'});
}

function register() {
    window.open(registerUrl);
}

async function trylogin() {
    localStorage['password'] = "" + $("#psw").val();
    localStorage['username'] = "" + $("#username").val();
    
    const verified = await verifyUser();
    
    if (verified == 0) {
        userTab();
        await userLogin();
        await initializeServer();
        chrome.browserAction.setBadgeText({text: 'on'});
        chrome.browserAction.setBadgeBackgroundColor({color: [202, 181, 225, 255]});
    } else {
        chrome.browserAction.setBadgeText({text: ''});
        const messageMap = {1: 1, 2: 2, [-1]: 3};
        showFailMessage(messageMap[verified]);
    }
}

function feedback() {
    if (confirm("Tip: If the task process is on-going (the relevant pages are not closed), please close the pages before annotating!\nIf not, ignore this message.")) {
        window.open(feedbackUrl);
    }
}


function logout() {
    clearInterval(taskSniff);
    localStorage['username'] = null;
    localStorage['password'] = null;
    chrome.browserAction.setBadgeText({text: ''});
    location.reload();
    chrome.runtime.sendMessage({log_request: 'off'});
}

// Get the active task
async function getActiveTask(task_id = null) {
    const credentials = getUserCredentials();
    let send_data = credentials;
    
    if (task_id != null && task_id != -1 && task_id != undefined) {
        send_data = {...credentials, task_id: task_id};
    }
    
    try {
        const result = await makeApiRequest(baseUrl + '/task/active_task/', send_data);
        chrome.runtime.sendMessage({ task_active: "request" });
        return result;
    } catch (error) {
        return -2;
    }
}

// 封装窗口打开逻辑
function openTaskWindow(path, params = '', newWindow = false) {
    const url = baseUrl + path + params;
    if (debug) console.log("Opening task window:", url);
    if (newWindow) {
        const windowOptions = 'height=1000,width=1200,top=0,left=0,toolbar=no,menubar=no,scrollbars=no,resizable=no,location=no,status=no';
        window.open(url, 'newwindow', windowOptions);
    } else {
        window.open(url, '_blank');
    }
}

// Start a task
async function starttask() {
    $("#bt_start_task").attr("disabled", true);
    chrome.runtime.sendMessage({start_task: true});
    
    task_id = await getActiveTask();
    
    if (task_id == -2) {
        alert("The server is not available. Please try again later.");
        switchTaskButtonStatus('off');
        return;
    }
    
    if (task_id != -1) {
        alert("There is an active task. Please end the task first.");
        switchTaskButtonStatus('on');
        return;
    }
    
    const isConfirm = confirm("Do you want to start a task?");
    if (isConfirm) {
        const timestamp = (new Date()).getTime();
        openTaskWindow('/task/pre_task_annotation/', timestamp);
    } else {
        switchTaskButtonStatus('off');
    }
}

// End a task
async function endtask() {
    $("#bt_end_task").attr("disabled", true);
    chrome.runtime.sendMessage({end_task: true});
    
    task_id = await getActiveTask();
    
    if (task_id == -2) {
        alert("The server is not available. Please try again later.");
        switchTaskButtonStatus('on');
        return;
    }
    
    if (task_id == -1) {
        alert("There is no active task. Please start a task first.");
        switchTaskButtonStatus('off');
        return;
    }
    
    const isConfirm = confirm("Do you want to submit the answer?");
    if (isConfirm && task_id != -1) {
        chrome.tabs.query({active: true, currentWindow: true}, function (tabs) {
            chrome.tabs.sendMessage(tabs[0].id, {type: "msg_from_popup", update_webpage_info: true}, async function (response) {
                if (debug) console.log(response);
                const timestamp = (new Date()).getTime();
                openTaskWindow('/task/submit_answer/', `${task_id}/${timestamp}`);
                const activeTask = await getActiveTask();
                if (activeTask < 0) {
                    switchTaskButtonStatus('off');
                }
            });
        });
    } else {
        switchTaskButtonStatus('on');
    }
}

async function canceltask() {
    task_id = await getActiveTask();
    const isConfirm = confirm("Do you want to cancel the task?");
    if (isConfirm) {
        const timestamp = (new Date()).getTime();
        openTaskWindow('/task/cancel_task/', `${task_id}/${timestamp}`, false);
    }
}

async function viewtask() {
    task_id = await getActiveTask();
    if (task_id != -1) {
        const credentials = getUserCredentials();
        const url = `${baseUrl}/task/view_task_info/${task_id}/?username=${credentials.username}&password=${credentials.password}`;
        const windowOptions = 'height=700,width=930,top=0,left=0,toolbar=no,menubar=no,scrollbars=no,resizable=no,location=no,status=no';
        window.open(url, 'newwindow', windowOptions);
    }
}

function tooluse() {
    const windowOptions = 'height=570,width=620,top=0,left=0,toolbar=no,menubar=no,scrollbars=no,resizable=no,location=no,status=no';
    window.open(baseUrl + '/task/show_tool_use_page', 'newwindow', windowOptions);
}

// Switch task button status
function switchTaskButtonStatus(task_status) {
    const isActive = task_status === 'on';
    
    $("#bt_start_task").attr("disabled", isActive).toggle(!isActive);
    $("#bt_end_task").attr("disabled", !isActive).toggle(isActive);
    $("#bt_cancel_task").attr("disabled", !isActive);
    $("#bt_view_task_info").attr("disabled", !isActive);
    $("#bt_tool_use").attr("disabled", !isActive);
}

chrome.runtime.onMessage.addListener(function (request, sender, sendResponse) {
    const messageMap = {
        "task_start_fail": ["The task has not been started successfully.", 'off'],
        "task_end_fail": ["The task has not been ended successfully.", 'on'],
        "task_start_success": ["The task has been started successfully.", 'on'],
        "task_end_success": ["The task has been ended successfully.", 'off']
    };
    
    if (messageMap[request]) {
        const [message, status] = messageMap[request];
        alert(message);
        switchTaskButtonStatus(status);
    }
});

// 初始化
(async function init() {
    if (jQuery) {
        loginTab();
        
        // 绑定事件
        $("#bt1").click(register);
        $("#bt2").click(trylogin);
        $("#bt4").click(feedback);
        $("#bt8").click(feedback);
        $("#bt6").click(logout);
        $("#bt_start_task").click(starttask);
        $("#bt_end_task").click(endtask);
        $("#bt_cancel_task").click(canceltask);
        $("#bt_view_task_info").click(viewtask);
        $("#bt_tool_use").click(tooluse);
        
        // 验证用户
        const verified = await verifyUser();
        if (verified === 0) {
            userTab();
            chrome.browserAction.setBadgeText({text: 'on'});
            chrome.browserAction.setBadgeBackgroundColor({color: [202, 181, 225, 255]});
        } else {
            chrome.browserAction.setBadgeText({text: ''});
        }
    } else {
        console.log("jQuery is needed!");
    }
})();
