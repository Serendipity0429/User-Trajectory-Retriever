var baseUrl = "http://127.0.0.1:8000";
var checkUrl = baseUrl + "/user/check/";
var loginUrl = baseUrl + "/user/login/";
var registerUrl = baseUrl + "/user/signup/";
var feedbackUrl = baseUrl + "/task/home/";
var downloadLink = "";
var taskSniff = null;
var logged_in = false;

function displayActiveTask() {
    var task_id = getActiveTask();
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
    } else if (task_id != -1) { // There is an active task
        switchTaskButtonStatus('on');
        $("#active_task").text("Active task: " + task_id);
        $("#active_task").css("color", "#000");
    }
}

function userTab() {

    $("#failMsg1").hide();
    $("#failMsg2").hide();
    $("#failMsg3").hide();
    $("#login").hide();
    $("#logged").show();
    $("#username_text_logged").text("User " + localStorage['username']);
    $("#bt_end_task").hide();
    displayActiveTask();
    // Routinely check whether there is an active task
    taskSniff = setInterval(displayActiveTask, 2000);
}

function loginTab() {
    $("#logged").hide();
    $("#failMsg1").hide();
    $("#failMsg2").hide();
    $("#failMsg3").hide();
    $("#login").show();
}

function initializeServer() {
    //console.log("initializing...");
    var result = -1;
    $.ajax({
        type: "POST",
        url: baseUrl + "/task/initialize/",
        dataType: 'json',
        async: false,
        data: {username: localStorage['username'], password: localStorage['password']},
        success: function (data, textStatus) {
            result = 0;
        },
        error: function () {
            result = -1;
        }
    });
    return result;
}

function verifyUser() {
    //console.log("checking...");
    var result = -1;
    if (localStorage['username'] != undefined && localStorage['password'] != undefined) {
        var name = localStorage['username'];
        var psw = localStorage['password'];
        //console.log("POSTing...");
        $.ajax({
            type: "POST",
            url: checkUrl,
            dataType: 'json',
            async: false,
            data: {username: name, password: psw},
            success: function (data, textStatus) {
                if (data == 0) {
                    result = 0;
                }
                if (data == 1) {
                    result = 1;
                }
                if (data == 2) {
                    result = 2;
                }
            },
            error: function () {
                result = -1;
            }
        });
    }
    return result;
}

function userLogin() {
    if (localStorage['username'] != undefined && localStorage['password'] != undefined) {
        var name = localStorage['username'];
        var psw = localStorage['password'];
        //console.log("POSTing...");
        $.ajax({
            type: "POST",
            url: loginUrl,
            dataType: 'json',
            async: false,
            data: {username: name, password: psw, ext: true},
            success: function (data, textStatus) {

            },
            error: function () {

            }
        });
        chrome.runtime.sendMessage({log_request: 'on'});
    }
}

function register() {
    window.open(registerUrl);
}

function trylogin() {
    //console.log("logging...");
    localStorage['password'] = "" + $("#psw").val();
    localStorage['username'] = "" + $("#username").val();
    var verified = verifyUser();
    if (verified == 0) {
        userTab();
        userLogin();
        initializeServer();
        chrome.browserAction.setBadgeText({text: 'on'});
        chrome.browserAction.setBadgeBackgroundColor({color: [202, 181, 225, 255]});
    } else {
        chrome.browserAction.setBadgeText({text: ''});
        if (verified == 1) {
            $("#failMsg2").hide();
            $("#failMsg3").hide();
            $("#failMsg1").show();
        }
        if (verified == 2) {
            $("#failMsg1").hide();
            $("#failMsg3").hide();
            $("#failMsg2").show();
        }
        if (verified == -1) {
            $("#failMsg1").hide();
            $("#failMsg2").hide();
            $("#failMsg3").show();
        }
    }
}

function feedback() {
    if (confirm("Tip: If the task process is on-going (the relevant pages are not closed), please close the pages before annotating!\nIf not, ignore this message.")) window.open(feedbackUrl);
}

function download() {
    window.open(downloadLink, '_blank');
}

function logout() {
    clearInterval(taskSniff)
    localStorage['username'] = null;
    localStorage['password'] = null;
    chrome.browserAction.setBadgeText({text: ''});
    location.reload();
    chrome.runtime.sendMessage({log_request: 'off'});
}

// Get the active task
function getActiveTask(task_id = null) {
    var username = localStorage['username'];
    var password = localStorage['password'];
    var send_data = {username: username, password: password};
    if (!(task_id == null || task_id == -1 || task_id == undefined)) {
        send_data = {username: username, password: password, task_id: task_id};
    }
    var result = -1;
    $.ajax({
        type: "POST",
        url: baseUrl + '/task/active_task/',
        dataType: 'json',
        async: false,
        data: send_data,
        success: function (data, textStatus) {
            result = data;
        },
        error: function () {
            result = -2;
        }
    });
    return result;
}

// Start a task
function starttask() {
    // Ask back-end to start a task
    // Disable the start task button
    $("#bt_start_task").attr("disabled", true);
    chrome.runtime.sendMessage({start_task: true});
    var task_id = getActiveTask();
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
    var isConfirm = confirm("Do you want to start a task?");
    if (isConfirm) {
        task_id = (new Date()).getTime();
        window.open(baseUrl + '/task/pre_task_annotation/' + task_id, 'newwindow', 'height=1000,width=1200,top=0,left=0,toolbar=no,menubar=no,scrollbars=no, resizable=no,location=no, status=no');
        switchTaskButtonStatus('on');
    } else {
        switchTaskButtonStatus('off');
    }
}

// End a task
function endtask() {
    // Ask back-end to end a task
    // Disable the end task button
    $("#bt_end_task").attr("disabled", true);
    chrome.runtime.sendMessage({end_task: true});
    var task_id = getActiveTask();
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
    var isConfirm = confirm("Do you want to end the task?");
    if (isConfirm && task_id != -1) {
        window.open(baseUrl + '/task/post_task_annotation/' + task_id, 'newwindow', 'height=1000,width=1200,top=0,left=0,toolbar=no,menubar=no,scrollbars=no, resizable=no,location=no, status=no');
        switchTaskButtonStatus('off');
    } else {
        switchTaskButtonStatus('on');
    }
}

function tooluse() {

}


// Switch task button status
function switchTaskButtonStatus(task_status) {
    if (task_status == 'on') {
        $("#bt_start_task").attr("disabled", true);
        $("#bt_end_task").attr("disabled", false);
        $("#bt_end_task").show();
        $("#bt_start_task").hide();
        $("#bt_tool_use").attr("disabled", false);
    } else if (task_status == 'off') {
        $("#bt_start_task").attr("disabled", false);
        $("#bt_end_task").attr("disabled", true);
        $("#bt_end_task").hide();
        $("#bt_start_task").show();
        $("#bt_tool_use").attr("disabled", true);
    }
}


chrome.runtime.onMessage.addListener(function (request, sender, sendResponse) {
    if (request == "task_start_fail") {
        alert("The task has not been started successfully.");
        switchTaskButtonStatus('off');
    } else if (request == "task_end_fail") {
        alert("The task has not been ended successfully.");
        switchTaskButtonStatus('on');
    } else if (request == "task_start_success") {
        alert("The task has been started successfully.");
        switchTaskButtonStatus('on');
    } else if (request == "task_end_success") {
        alert("The task has been ended successfully.");
        switchTaskButtonStatus('off');
    }
});

if (jQuery) {
    loginTab();
    $("#bt1").click(register);
    $("#bt2").click(trylogin);
    $("#bt4").click(feedback);
    $("#bt8").click(feedback);
    $("#bt6").click(logout);
    $("#bt_start_task").click(starttask);
    $("#bt_end_task").click(endtask);
    $("#bt_tool_use").click(tooluse);
    if (verifyUser() == 0) {
        userTab();
        chrome.browserAction.setBadgeText({text: 'on'});
        chrome.browserAction.setBadgeBackgroundColor({color: [202, 181, 225, 255]});
    } else {
        chrome.browserAction.setBadgeText({text: ''});
    }
} else {
    console.log("jQuery is needed!");
}


