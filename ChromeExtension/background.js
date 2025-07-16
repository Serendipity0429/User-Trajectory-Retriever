var baseUrl = "http://127.0.0.1:8000";
var checkUrl = baseUrl + "/user/check/";
var dataUrl = baseUrl + "/task/data/";
var cancelUrl = baseUrl + "/task/cancel_task/";
var username, password;
var version = "1.0";
var debug1 = true;
var logged_in = false;

var lastReminder = 0;

var current_task = -1;

function storeInfo(Msg) {
    var key = (new Date()).getTime();
    localStorage["" + key] = Msg;
    return "" + key;
}

function deleteInfo(key) {
    localStorage.removeItem(key);
}

function closeAllIrrelevantTabs() {      // 获取所有标签页
    chrome.tabs.query({}, (tabs) => {
        // 关闭所有标签页
        const tabIds = tabs.filter(tab => !tab.url.startsWith(baseUrl)).map(tab => tab.id);
        const homeTabIds = tabs.filter(tab => tab.url.startsWith(baseUrl)).map(tab => tab.id);
        if (homeTabIds.length == 0) {
            chrome.tabs.create({ url: "https://bing.com" });
        }
        chrome.tabs.remove(tabIds, () => {

        });
    });
}

function checkActiveTaskID() {
    if (localStorage['username'] == undefined || localStorage['password'] == undefined || !logged_in) {
        return -1;
    }
    var username = localStorage['username'];
    var password = localStorage['password'];
    var send_data = { username: username, password: password };
    var result = -1 ;
    $.ajax({
        type: "POST",
        url: baseUrl + '/task/active_task/',
        dataType: 'json',
        async: false,
        data: send_data,
        success: function (data, textStatus) {
            if (current_task != data) {
                closeAllIrrelevantTabs();
            }
            current_task = data;
            result = data;
        },
        error: function () {
            result = -1;
            current_task = -1;
        }
    });
    return result;
}

function sendInfo(Msg) {
    username = localStorage['username'];
    password = localStorage['password'];
    var verified = verifyUser();
    if (verified != 0) return;

    // var key = storeInfo(Msg);
    $.ajax({
        type: "POST", dataType: "text", //dataType: 'json',
        url: dataUrl, data: { message: Msg }, //contentType: "application/json; charset=utf-8",
        success: function (data) {
            // deleteInfo(key);
        }, error: function (jqXHR, textStatus, errorThrown) {
        }
    });
}

function flush() {
    for (var i = localStorage.length - 1; i >= 0; i--) {
        var lastkey = localStorage.key(i);
        if (lastkey.match(/[0-9]*/g)[0] != lastkey) continue;
        var Msg = localStorage[lastkey];
        deleteInfo(lastkey);
        sendInfo(Msg);
    }
}

// Helper to convert Uint8Array to Base64 string
// Pako.deflate returns a Uint8Array, which needs to be Base64 encoded for sending via AJAX/chrome.runtime.sendMessage
function uint8ArrayToBase64(bytes) {
    var binary = '';
    var len = bytes.byteLength;
    for (var i = 0; i < len; i++) {
        binary += String.fromCharCode(bytes[i]);
    }
    return btoa(binary);
}



chrome.runtime.onMessage.addListener(function (Msg, sender, sendResponse) {
    if (debug1) console.log(Msg);
    if (Msg.log_status == "request") { // check if the user is logged in
        var verified = verifyUser();
        if (verified == 0) {
            chrome.browserAction.setBadgeText({ text: 'on' });
            chrome.browserAction.setBadgeBackgroundColor({ color: [202, 181, 225, 255] });
            sendResponse({ log_status: true });
        } else chrome.browserAction.setBadgeText({ text: '' });
        sendResponse({ log_status: false });
        return;
    } else if (Msg.link_store == "request_update") { // store the link
        var now_time = new Date().getTime();
        var data = { interface: Msg.interface, expiry: now_time + 1800000 };
        localStorage.setItem(Msg.url + Msg.query, JSON.stringify(data));
        sendResponse("localStorage done");
        return;
    }
    if (Msg.interface_request != undefined) { // get the interface
        // window.alert(Msg.interface_request);
        var value = JSON.parse(localStorage.getItem(Msg.interface_request));
        if (value != undefined) {
            var now_time = new Date().getTime();
            if (now_time <= value.expiry) {
                sendResponse(value.interface);
            } else {
                localStorage.removeItem(Msg.interface_request);
                // window.alert('expiry!'); // 过期
                sendResponse(1);
            }
        } else {
            // window.alert('no records!'); // 空记录
            sendResponse(1);
        }

        return;
    }
    if (Msg.file != undefined) { // store the file
        chrome.tabs.executeScript(sender.tab.id, Msg);
        sendResponse({ scriptFinish: true });
        return;
    }
    if (Msg.send_flag == true) { // send the data
        Msg.username = localStorage['username'];
        let msgJsonString = JSON.stringify(Msg);
        let compressedData = pako.deflate(msgJsonString, { to: 'string' });
        let compressedBase64 = uint8ArrayToBase64(compressedData);
        sendInfo(compressedBase64);
    }

    if (Msg.task_active == "request") {
        let task_id = checkActiveTaskID();
        let task_active = task_id != -1;
        sendResponse({ task_active: task_active, task_id: task_id });
        return;
    }

    if (Msg.log_request == 'on') {
        logged_in = true;
        return;
    } else if (Msg.log_request == 'off') {
        logged_in = false;
        return;
    }
});

function verifyUser() {
    if (debug1) console.log("checking...");
    var result = -1;
    if (debug1) console.log(localStorage['username']);
    if (debug1) console.log(localStorage['password']);
    if (localStorage['username'] != undefined && localStorage['password'] != undefined) {
        var name = localStorage['username'];
        var psw = localStorage['password'];
        if (debug1) console.log("POSTing...");
        $.ajax({
            type: "POST",
            url: checkUrl,
            dataType: 'json',
            async: false,
            data: { username: name, password: psw },
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

function IsJsonString(str) {
    try {
        JSON.parse(str);
    } catch (e) {
        return false;
    }
    return true;
}

function clearlocalStorage() {
    for (var i = 0; i < localStorage.length; i++) {
        //check if past expiration date
        var this_key = localStorage.key(i);
        if (IsJsonString(localStorage.getItem(this_key))) {
            var values = JSON.parse(localStorage.getItem(this_key));
            if (values.expiry < new Date().getTime()) {
                localStorage.removeItem(this_key);
            }
        }

    }

}


flush();
setInterval(function () {
    clearlocalStorage();
}, 60000);


