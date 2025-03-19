var debug = true;
var debug1 = false;
var debug = true;
//var debug1 = true;

var current_url = window.location.href;
// var current_url = document.location;
var current_referrer = document.referrer;
var current_serp_link = "";
var this_interface = 1;

var is_task_active = false;


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
    if (current_url.substring(0, 22) == "http://127.0.0.1:8000/") {
        return;
    }
    else if (response.log_status == true) {
        logged_in = true;
        storage_link();
        if (debug) console.log("content.js is loaded");
        viewState.initialize();
        if (debug) console.log("initialize done");

        checkIsTaskActive();

        window.addEventListener("DOMSubtreeModified", function (event) {
            checkIsTaskActive();
            // alert("Task is active: " + is_task_active);
            if (current_url !== window.location.href) {
                viewState.sendMessage();
                current_referrer = current_url;
                current_url = window.location.href;
                storage_link();
                viewState.initialize();
                if (debug) console.log("initialize again");
            } else {
                // var origin = "???";
                // var temp = current_url.match(/www\.(baidu)?(sogou)?(so)?\.com\/(s|web)/g);
                // if (temp != null) {
                //     switch (temp[0]) {
                //         case "www.sogou.com/web":
                //             origin = "sogou";
                //             break;
                //
                //         case "www.baidu.com/s":
                //             origin = "baidu";
                //             break;
                //
                //         case "www.so.com/s":
                //             origin = "360";
                //             break;
                //
                //         default:
                //             break;
                //     }
                // }
                // if (origin != "???") {
                viewState.update();
                // }
            }
        });
    }
});