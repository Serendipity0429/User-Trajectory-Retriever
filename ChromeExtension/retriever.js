// To post all user's trajectory data to the server
if (debug) console.log("retriever.js loaded");
var baseUrl = "http://127.0.0.1:8000/"; // The base URL of the server

// Initialize the page
mPage.initialize = function () {
    mPage.preRate = -1;
    var random_seed = Math.random();
    if (random_seed <= 0.3) {
        mPage.pre_annotate(); // To ask the user to annotate the task purpose
    }
    mPage.click_results = new Array();
    mPage.click_others = new Array();
    mPage.init_content();
};

// Initialize the content of the page
mPage.init_content = function () {
    mPage.query = $("#upquery").val();
    mPage.html = document.documentElement.outerHTML;
    mPage.title = document.title;
    var url_pair = current_referrer + mPage.query;
    chrome.runtime.sendMessage({interface_request: url_pair}, function (response) {
        mPage.interface = response;
        // window.alert("interface"+ response);
    });
};

// To ask the user to annotate the task purpose
mPage.pre_annotate = function () {
    var start_timestamp = pageManager.start_timestamp;
    var isConfirm = window.confirm("Please annotate before task!");
    if (isConfirm == true) {
        mPage.preAnnotate = 1;
        window.open (baseUrl + "/task/pre_task_annotation/" + start_timestamp, 'newwindow','height=1000,width=1200,top=0,left=0,toolbar=no,menubar=no,scrollbars=no, resizable=no,location=no, status=no');
    }
};