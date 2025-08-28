// var debug = true;
// var debug1 = false;

var baseUrl = "http://101.6.41.59:32904/"
var current_url = window.location.href;
var current_referrer = document.referrer;
var is_task_active = false;
var is_in_background = false; // This variable is not used in the current code, but can be used for future enhancements

// check whether there is an active task
function checkIsTaskActive() {
    chrome.runtime.sendMessage({ task_active: "request" }, function (response) {
        is_task_active = response.task_active;
        console.log("Task is active: " + is_task_active);
        console.log("Task ID: " + response.task_id);
    })
}

function getTaskActiveStatus() {
    // This function is used to check if the task is active
    return is_task_active;
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

(function(history){
    var pushState = history.pushState;
    var replaceState = history.replaceState;

    history.pushState = function(state) {
        if (typeof history.onpushstate == "function") {
            history.onpushstate({state: state});
        }
        setTimeout(() => {
            if (current_url !== window.location.href) {
                current_referrer = current_url;
                current_url = window.location.href;
                flush_view_state();
                if (debug) console.log("URL changed (pushState), re-initializing.");
            }
        }, 0);
        return pushState.apply(history, arguments);
    };
    
    history.replaceState = function(state) {
        if (typeof history.onreplacestate == "function") {
            history.onreplacestate({state: state});
        }
        setTimeout(() => {
            if (current_url !== window.location.href) {
                current_referrer = current_url;
                current_url = window.location.href;
                flush_view_state();
                if (debug) console.log("URL changed (replaceState), re-initializing.");
            }
        }, 0);
        return replaceState.apply(history, arguments);
    };
})(window.history);

window.addEventListener('popstate', () => {
    if (current_url !== window.location.href) {
        current_referrer = current_url;
        current_url = window.location.href;
        flush_view_state();
        if (debug) console.log("URL changed (popstate), re-initializing.");
    }
});


chrome.runtime.sendMessage({ log_status: "request" }, function (response) {
    console.log(current_url.substring(0, 22))
    checkIsTaskActive();
    if (current_url.startsWith(baseUrl) == false
        && response.log_status == true && is_task_active) {
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

        document.addEventListener("visibilitychange", function () {
            if (document.visibilityState === 'hidden') {
                if (debug) console.log("Page is hidden, flushing view state.");
                is_in_background = true;
                flush_view_state(true);
            } else {
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

// Display a "content.js loaded" box on the upper right corner for 3 seconds
// should have a class named 'rr-ignore' to avoid being recorded by rrweb
// When DOM loaded
function displayLoadedBox(script_name) {
    if(!getTaskActiveStatus()) {
        return; // Do not display the box if the task is not active
    }
    var current_url = window.location.href;
    if (current_url.startsWith(baseUrl) == true)
        return; // Avoid displaying the box on the local server
    const box = document.createElement('div');
    box.className = 'rr-block loaded-box';
    box.style.opacity = '0';
    box.style.transition = 'opacity 0.5s ease-in-out';
    
    // Fade in
    setTimeout(() => {
        box.style.opacity = '1';
    }, 10);
    box.style.position = 'fixed';
    box.style.right = '10px';
    box.style.backgroundColor = 'white';
    box.style.color = 'black';
    box.style.padding = '10px';
    box.style.border = '2px solid rgb(151, 67, 219)';
    box.style.zIndex = '1000000';
    box.innerText = `${script_name} loaded!`;
    
    // Check for existing loaded boxes and position accordingly
    const existingBoxes = document.querySelectorAll('.loaded-box');
    let topPosition = 10;
    
    existingBoxes.forEach(existingBox => {
        const rect = existingBox.getBoundingClientRect();
        if (rect.bottom > topPosition) {
            topPosition = rect.bottom + 10;
        }
    });
    
    box.style.top = `${topPosition}px`;
    
    document.body.appendChild(box);
    
    setTimeout(() => {
        box.style.opacity = '0';
        setTimeout(() => {
            box.remove();
        }, 500);
    }, 3000);
}


document.addEventListener("DOMContentLoaded", function (event) {
    displayLoadedBox("content.js");
});
