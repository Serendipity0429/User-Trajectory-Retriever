/**
* @fileoverview Manages page-specific data and events.
* This script serves as a data model and does not contain any direct calls to Chrome APIs.
* The core logic for communication with the service worker (background script) is handled
* by other content scripts, such as content.js.
*/
class Event {
    constructor(is_active, type, timestamp, screenX, screenY, clientX, clientY, tag, content, hierachy, related_info, annotation = null) {
        this.is_active = is_active;
        this.type = type;
        this.timestamp = timestamp;
        this.screenX = screenX;
        this.screenY = screenY;
        this.clientX = clientX;
        this.clientY = clientY;
        this.tag = tag;
        this.content = content;
        this.hierachy = hierachy;
        this.related_info = related_info;
        this.annotation = annotation;
    }
}

var unitPage = {
    time_last_update: 0,
    title: null,
    url: "",
    event_list: [], // a list of events (e.g. mouse clicks, mouse movements, etc.) including annotations
    rrweb_record: [], // a list of rrweb events


    getTitle: function () {
        return unitPage.title;
    },

    getEventList: function () {
        return unitPage.event_list;
    },

    getRRWebEvents: function () {
        return unitPage.rrweb_record;
    },


    update: function () {
        printDebug("unitPage: update");
        unitPage.time_last_update = _time_now();
    },

    initialize: function () {
        printDebug("unitPage: initialize");
        unitPage.time_last_update = _time_now();
        unitPage.event_list = [];
        unitPage.rrweb_record = [];
        unitPage.title = document.title;
        unitPage.url = window.location.href;
    },


    // add a new event
    addEvent(isActive, type, timestamp, screenX, screenY, clientX, clientY, tag, content, hierachy, related_info, annotation = null) {
        let new_event = new Event(isActive, type, timestamp, screenX, screenY, clientX, clientY, tag, content, hierachy, related_info, annotation);
        unitPage.event_list.push(new_event);
    },

    addActiveEvent(type, timestamp, screenX, screenY, clientX, clientY, tag, content, hierachy, related_info, annotation = null) {
        unitPage.addEvent(true, type, timestamp, screenX, screenY, clientX, clientY, tag, content, hierachy, related_info, annotation);
    },

    addPassiveEvent(type, timestamp, screenX, screenY, clientX, clientY, tag, content, hierachy, related_info) {
        unitPage.addEvent(false, type, timestamp, screenX, screenY, clientX, clientY, tag, content, hierachy, related_info);
    },

    addRRWebEvent(event) {
        unitPage.rrweb_record.push(event);
    }

};

class pageTimestamp {
    constructor(inT, outT) {
        this.inT = inT;
        this.outT = outT;
        this.getDwell = function () {
            return this.outT - this.inT;
        };
    }
}

var pageManager = {
    start_timestamp: 0,
    end_timestamp: 0,
    dwell_time: 0,
    page_timestamps: [],
    last_viewed_time: 0,

    initialize: function () {
        printDebug("pageManager initialize");
        pageManager.start_timestamp = _time_now()
        pageManager.end_timestamp = pageManager.start_timestamp;
        pageManager.dwell_time = 0;
        pageManager.page_timestamps = [];
        pageManager.last_viewed_time = pageManager.start_timestamp;

    },

    pageInteract: function () {
        pageManager.last_viewed_time = _time_now()
    },

    pageLeave: function () {
        pageManager.end_timestamp = _time_now()
        pageManager.page_timestamps.push(new pageTimestamp(pageManager.last_viewed_time, pageManager.end_timestamp));
        pageManager.dwell_time += pageManager.end_timestamp - pageManager.last_viewed_time;
        pageManager.last_viewed_time = pageManager.end_timestamp;
    }
};

// Manage the current state of the page
var viewState = {
    is_sent: false, // If true, the current state has been sent to the server
    sent_when_active: false, // If true, the current state was active when sent
    is_visible: true,
    time_last_op: 0,
    time_limit: 60000, // The time limit for user inactivity in milliseconds (1 minute now)
    _is_visibility_listener_added: false, // To ensure the visibilitychange listener is added only once

    checkState: function () {
        printDebug("viewState: checking the activity of current page...");
        if (_time_now() - viewState.time_last_op >= viewState.time_limit && viewState.is_visible == true)
            viewState.toggleState();
        else if (viewState.is_visible == true)
            setTimeout(viewState.checkState, viewState.time_limit);
    },

    toggleState: function () {
        printDebug(`viewState: view state changed from ${viewState.is_visible} to ${!viewState.is_visible}`);
        if (viewState.is_visible == false) {
            viewState.is_visible = true;
            viewState.checkState();
            pageManager.pageInteract();
        } else {
            viewState.is_visible = false;
            pageManager.pageLeave();
            mouseRecord.pause();
        }
    },

    // pageInteract: called when the user interacts with the page
    pageInteract: function () {
        printDebug("viewState: page activated");
        viewState.time_last_op = _time_now();
        if (viewState.is_visible == false) {
            viewState.toggleState();
        }
    },

    // pageLeave: called when the user leaves the page
    pageLeave: function () {
        printDebug("viewState: page deactivated");
        if (viewState.is_visible == true) {
            viewState.toggleState();
        }
    },

    // tabEnter: called when the tab is entered
    tabEnter: function () {
        printDebug("viewState: tab entered");
        viewState.pageInteract();
    },

    // tabLeave: called when the tab is exited
    tabLeave: function () {
        printDebug("viewState: tab exited");
        viewState.pageLeave();
    },

    focus: function () {
        printDebug("viewState: focus");
        viewState.pageInteract();
    },

    blur: function () {
        printDebug("viewState: blur");
        viewState.pageLeave();
    },

    mMove: function (e) {
        printDebug(`viewState: mouse move to ${e.clientX}, ${e.clientY}`);
        viewState.pageInteract();
        mouseRecord.move(e);
    },

    mScroll: function () {
        printDebug("viewState: scroll");
        viewState.pageInteract();
        mouseRecord.scroll();
    },

    update: function () {
        printDebug("viewState: update");
        unitPage.update();
        viewState.is_sent = false;
        viewState.pageInteract();
    },

    initialize: function () {
        printDebug("viewState: initializing");
        viewState.is_sent = false;
        // Check if visibility change listener is already added to avoid duplicates

        if (!viewState._is_visibility_listener_added) {
            document.addEventListener("visibilitychange", function (event) {
                // NOTICE: the visibilitychange event is also triggered when the page is closed, so we don't need to use onbeforeunload
                let hidden = event.target.webkitHidden;
                if (hidden) {
                    viewState.tabLeave();
                    if (viewState.sent_when_active === true) {
                        printDebug("viewState: already sent when active, skipping flush on tab leave.");
                        viewState.sent_when_active = false;
                        return;
                    } else {
                        viewState.flush();
                    }
                } else {
                    viewState.tabEnter();
                }
            }, false);

            viewState._is_visibility_listener_added = true;
        }

        // NOTICE: The unbind - bind pattern is not redundant, because if we bind the event listeners multiple times, they will be triggered mu zltiple times. And if we check whether the event listener is already bound, it is not straightforward in JavaScript and not efficient.
        // Unbind listeners before binding them again to prevent duplicates
        $(window).unbind('mousemove', viewState.mMove);
        $(window).unbind('scroll', viewState.mScroll);
        $(window).unbind('focus', viewState.focus);
        $(window).unbind('blur', viewState.blur);

        // Bind the event listeners
        $(window).bind('mousemove', viewState.mMove);
        $(window).bind('scroll', viewState.mScroll);
        $(window).focus(viewState.focus);
        $(window).blur(viewState.blur);

        // Judge if the page is currently visible
        viewState.is_visible = !document.hidden;
        viewState.time_last_op = _time_now();

        printDebug(viewState);
        printDebug(pageManager);
        printDebug(unitPage);
        printDebug(mouseRecord);

        unitPage.initialize();
        pageManager.initialize();
        mouseRecord.initialize();
        viewState.checkState();
    },

    sendMessage: function () {
        printDebug("viewState: send message");
        if (viewState.is_sent == true || _is_server_page(_content_vars.url_now)) { // avoid redundancy and the local server
            printDebug("viewState: message already sent or on server page, skipping sendMessage.");
            return;
        }

        pageManager.pageLeave();
        mouseRecord.end(); // End mouse recording

        var message = new Message(); // Message class is defined in message.js
        // Construct the message object for the service worker
        message.command = "send_message";
        message.send_flag = true;
        message.username = ""; // This will be filled in by the background script
        message.start_timestamp = pageManager.start_timestamp;
        message.end_timestamp = pageManager.end_timestamp;
        message.dwell_time = pageManager.dwell_time;
        message.page_timestamps = JSON.stringify(pageManager.page_timestamps);
        message.type = "msg_from_content";
        message.url = _content_vars.url_now; // defined in content.js
        message.referrer = _content_vars.referrer_now; // defined in content.js
        message.title = unitPage.getTitle();
        message.mouse_moves = JSON.stringify(mouseRecord.getData());
        message.event_list = JSON.stringify(unitPage.getEventList());
        message.rrweb_record = JSON.stringify(unitPage.getRRWebEvents());
        message.sent_when_active = viewState.sent_when_active;

        chrome.runtime.sendMessage(message, (response) => {
            if (response && response.success) printDebug("viewState: message sent to background script successfully.");
            else printDebug("viewState: failed to send message to background script.");
        });

        viewState.is_sent = true;
    },

    flush: function () {
        viewState.sendMessage();
        viewState.initialize();
        unitPage.rrweb_record = []; // clear the rrweb events
        rrweb.record.takeFullSnapshot(); // take a full snapshot of DOM
    }
};


// Main body
printDebug("page.js is loaded");