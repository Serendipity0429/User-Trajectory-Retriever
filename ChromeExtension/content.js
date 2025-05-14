// var debug = true;
// var debug1 = false;

var current_url = window.location.href;
var current_referrer = document.referrer;
var current_serp_link = "";
var is_task_active = false;

// check whether there is an active task
function checkIsTaskActive() {
    chrome.runtime.sendMessage({task_active: "request"}, function (response) {
        is_task_active = response.task_active;
        console.log("Task is active: " + is_task_active);
    })
}

checkIsTaskActive();

function storage_link() {
    var temp_ref = current_referrer.match(/www\.(baidu)?(sogou)?(so)?\.com\/(s|web)/g);
    if (temp_ref != null) {
        current_serp_link = current_url;
        chrome.runtime.sendMessage({
            link_store: "request",
            url: current_url,
            serp_link: current_serp_link
        }, function (response) {
            if (debug) console.log(response);
        });
    } else {
        chrome.runtime.sendMessage({ref_request: current_referrer}, function (response) {
            current_serp_link = response;
            // this_interface = parseInt(response.split(">")[0]);
            if (current_serp_link != "") {
                chrome.runtime.sendMessage({
                    link_store: "request",
                    url: current_url,
                    serp_link: current_serp_link
                }, function (response) {
                    if (debug) console.log(response);
                });
            }
        });
    }
}


chrome.runtime.sendMessage({log_status: "request"}, function (response) {
    console.log(current_url.substring(0, 22))
    if (current_url.substring(0, 22) != "http://127.0.0.1:8000/"
        && response.log_status == true) {
        logged_in = true;
        storage_link();
        if (debug) console.log("content.js is loaded");
        viewState.initialize();
        rrweb.record({
            emit(event) {
                mPage.addRRWebEvent(event);
            },
        });
        if (debug) console.log("initialize done");

        checkIsTaskActive();
        let observer = new MutationObserver(function (mutations) {
            if (current_url !== window.location.href) {
                viewState.sendMessage();
                current_referrer = current_url;
                current_url = window.location.href;
                storage_link();
                viewState.initialize();
                mPage.rrweb_events = []; // clear the rrweb events
                rrweb.record.takeFullSnapshot();
                if (debug) console.log("initialize again");
            } else {
                viewState.update();
            }
        });
        let config = {childList: true, subtree: true, attributes: true};
        observer.observe(document.body, config);
    }
});

chrome.runtime.onMessage.addListener(function (request, sender, sendResponse) {
    if (request.type == "msg_from_popup") {
        if (request.update_webpage_info)
            viewState.sendMessage();
    }
})