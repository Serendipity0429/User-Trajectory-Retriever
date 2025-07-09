// var debug = true;
// var debug1 = false;

var current_url = window.location.href;
var current_referrer = document.referrer;
var is_task_active = false;
var is_in_background = false; // This variable is not used in the current code, but can be used for future enhancements

// check whether there is an active task
function checkIsTaskActive() {
    chrome.runtime.sendMessage({ task_active: "request" }, function (response) {
        is_task_active = response.task_active;
        console.log("Task is active: " + is_task_active);
    })
}

checkIsTaskActive();

function storage_link() {
    // Originally designed to store SERP links, but now used for all pages
    // Leave it here for compatibility
}

function flush_view_state(send_message = true) {
    if (send_message) {
        viewState.sendMessage();
        storage_link();
    }
    viewState.initialize();
    mPage.rrweb_events = []; // clear the rrweb events
    rrweb.record.takeFullSnapshot();
}


chrome.runtime.sendMessage({ log_status: "request" }, function (response) {
    console.log(current_url.substring(0, 22))
    checkIsTaskActive();
    if (current_url.substring(0, 22) != "http://127.0.0.1:8000/"
        && response.log_status == true && is_task_active) {
        logged_in = true;
        storage_link();
        if (debug) console.log("content.js is loaded");
        viewState.initialize();
        rrweb.record({
            emit(event) {
                mPage.addRRWebEvent(event);
                viewState.update();
            },
        });
        if (debug) console.log("initialize done");

        let observer = new MutationObserver(function (mutations) {
            if (current_url !== window.location.href) {
                current_referrer = current_url;
                current_url = window.location.href;
                flush_view_state();
                if (debug) console.log("initialize again");
            } else {
                viewState.update();
            }
        });
        let config = { childList: true, subtree: true, attributes: true };
        observer.observe(document.body, config);

        document.addEventListener("visibilitychange", function () {
            if (document.visibilityState === 'hidden') {
                if (debug) console.log("Page is hidden, flushing view state.");
                is_in_background = true;
                flush_view_state(true);
            } else if (document.visibilityState === 'visible') {
                if (is_in_background) {
                    if (debug) console.log("Page is visible after being hidden, updating view state.");
                    flush_view_state(false); // do not send message to backend, we want to skip the rrweb events occured when the page was hidden
                    is_in_background = false;
                }
            }
        });
    }
});

chrome.runtime.onMessage.addListener(function (request, sender, sendResponse) {
    if (request.type == "msg_from_popup") {
        if (document.visibilityState === 'hidden') {
            if (debug) console.log("Page is hidden, so won't send response when popup requires.");
        }
        else {
            if (request.update_webpage_info)
                flush_view_state();
            sendResponse({ status: "success" });
        }
    }
})