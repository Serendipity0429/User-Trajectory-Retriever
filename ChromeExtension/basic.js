var msg = {
    send_flag: true,
    username: "",
    start_timestamp: 0,
    end_timestamp: 0,
    dwell_time: 0,
    page_timestamps: [],
    type: "",
    origin: "",
    url: "",
    referrer: "",
    query: "",
    html: "",
    mouse_moves: "",
    interface: 1,
    preAnnotate: -1,

    event_list: "",
    rrweb_events: "",

    initialize: function () {
        msg.send_flag = true;
        msg.start_timestamp = 0;
        msg.end_timestamp = 0;
        msg.dwell_time = 0;
        msg.page_timestamps = new Array();
        msg.type = "";
        msg.origin = "";
        msg.url = "";
        msg.referrer = ""
        msg.query = "";
        msg.html = "";
        msg.mouse_moves = "";
        msg.username = "";
        msg.interface = 1;
        msg.preAnnotate = -1;
        msg.event_list = "";
        msg.rrweb_events = "";
    }
};

var pageTimestamp = function (inT, outT) {
    this.inT = inT;
    this.outT = outT;
    this.getDwell = function () {
        return this.outT - this.inT;
    };
};

var pageManager = {
    start_timestamp: 0,
    end_timestamp: 0,
    dwell_time: 0,
    page_timestamps: [],
    lastViewTime: 0,

    initialize: function () {
        pageManager.start_timestamp = (new Date()).getTime();
        pageManager.end_timestamp = pageManager.start_timestamp;
        pageManager.dwell_time = 0;
        pageManager.page_timestamps = [];
        pageManager.lastViewTime = pageManager.start_timestamp;
        if (debug) console.log("pageManager initialize");
    },
    getIn: function () {
        pageManager.lastViewTime = (new Date()).getTime();
    },
    getOut: function () {
        pageManager.end_timestamp = (new Date()).getTime();
        pageManager.page_timestamps.push(new pageTimestamp(pageManager.lastViewTime, pageManager.end_timestamp));
        pageManager.dwell_time += pageManager.end_timestamp - pageManager.lastViewTime;
        pageManager.lastViewTime = pageManager.end_timestamp;
    }
};

var viewState = {
    show: true,
    lastOp: 0,
    timeLimit: 100000,
    sent_current_state: false, // If true, the current state has been sent to the server
    check: function () {
        if (debug) console.log("check state");
        if ((new Date()).getTime() - viewState.lastOp >= viewState.timeLimit && viewState.show == true)
            viewState.toggleState();
        else if (viewState.show == true)
            setTimeout(viewState.check, viewState.timeLimit);
    },
    toggleState: function () {
        if (debug) console.log("View State Changed from " + viewState.show + " to " + !viewState.show);
        if (viewState.show == false) {
            viewState.show = true;
            viewState.check();
            pageManager.getIn();
        } else {
            viewState.show = false;
            pageManager.getOut();
            mRec.pause();
        }
    },

    getIn: function () {
        viewState.lastOp = (new Date()).getTime();
        if (viewState.show == false) {
            viewState.toggleState();
        }
    },
    getOut: function () {
        if (viewState.show == true) {
            viewState.toggleState();
        }
    },
    tabEnter: function () {
        viewState.getIn();
    },
    tabLeave: function () {
        viewState.getOut();
    },
    focus: function () {
        if (debug) console.log("focus");
        viewState.getIn();
    },
    blur: function () {
        if (debug) console.log("blur");
        viewState.getOut();
    },
    mMove: function (e) {
        viewState.getIn();
        mRec.move(e);
    },
    mScroll: function () {
        viewState.getIn();
        mRec.scroll();
    },
    update: function () {
        //if (debug) console.log("update");
        // mPage.update();
        viewState.sent_current_state = false;
        //viewState.getIn();
    },
    close: function () {
        if (is_task_active || checkIsTaskActive()) {
            viewState.sendMessage();
        }
    },
    initialize: function () {
        viewState.sent_current_state = false;

        document.addEventListener("visibilitychange", function (event) {
            var hidden = event.target.webkitHidden;
            if (hidden) viewState.tabLeave();
            else viewState.tabEnter();
        }, false);

        // window.onbeforeunload = viewState.close;
        // NOTICE: the visibilitychange event is also triggered when the page is closed, so we don't need to use onbeforeunload

        $(window).focus(viewState.focus);
        $(window).blur(viewState.blur);
        viewState.show = true;
        viewState.lastOp = (new Date()).getTime();

        let current_url = window.location.href;

        if (debug) {
            console.log("origin=" + origin);
            console.log(viewState);
            console.log(pageManager);
            console.log(mPage);
            console.log(mRec);
        }

        if (debug) console.log("extension is working on general page");
        $(window).bind('mousemove', viewState.mMove);
        $(window).bind('scroll', viewState.mScroll);
        chrome.runtime.sendMessage({ file: "general.js" }, function (response) {
            if (response.scriptFinish == true) {
                console.log("execute script done");
                pageManager.initialize();
                mPage.initialize();
                mRec.initialize();
                viewState.check();
            }
        });
    },
    sendMessage: function () {
        if (debug) console.log("send message");
        if (viewState.sent_current_state == true) {
            return;
        }
        if (msg.url.substring(0, 22) == baseUrl) { // avoid the local server
            return;
        }
        pageManager.getOut();
        mRec.end();

        var current_url = window.location.href;

        msg.type = "general";
        
        msg.start_timestamp = pageManager.start_timestamp;
        msg.end_timestamp = pageManager.end_timestamp;
        msg.dwell_time = pageManager.dwell_time;
        msg.page_timestamps = JSON.stringify(pageManager.page_timestamps);
        msg.url = current_url;
        msg.referrer = current_referrer
        // msg.html = document.documentElement.outerHTML;
        msg.title = mPage.getTitle();
        msg.mouse_moves = JSON.stringify(mRec.getData());
        msg.event_list = JSON.stringify(mPage.getEventList());
        msg.rrweb_events = JSON.stringify(mPage.getRRWebEvents());

        chrome.runtime.sendMessage(msg);
        viewState.sent_current_state = true;
        msg.initialize();
    }
};

// Display a "basic.js loaded" box on the upper right corner for 3 seconds
// should have a class named 'rr-ignore' to avoid being recorded by rrweb
document.addEventListener("DOMContentLoaded", function (event) {
    displayLoadedBox("basic.js");
});
