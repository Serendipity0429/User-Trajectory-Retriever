/**
* @fileoverview Manages page-specific data and events.
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

class UnitPage {
    constructor() {
        this.title = null;
        this.url = "";
        this.event_list = [];
        this.rrweb_record = [];
    }

    getTitle() {
        return this.title;
    }

    getEventList() {
        return this.event_list;
    }

    getRRWebEvents() {
        return this.rrweb_record;
    }

    initialize() {
        printDebug("page", "UnitPage: initialize");
        this.event_list = [];
        this.rrweb_record = [];
        this.title = document.title;
        this.url = window.location.href;
    }

    addEvent(isActive, type, timestamp, screenX, screenY, clientX, clientY, tag, content, hierachy, related_info, annotation = null) {
        const new_event = new Event(isActive, type, timestamp, screenX, screenY, clientX, clientY, tag, content, hierachy, related_info, annotation);
        this.event_list.push(new_event);
    }

    addActiveEvent(type, timestamp, screenX, screenY, clientX, clientY, tag, content, hierachy, related_info, annotation = null) {
        this.addEvent(true, type, timestamp, screenX, screenY, clientX, clientY, tag, content, hierachy, related_info, annotation);
    }

    addPassiveEvent(type, timestamp, screenX, screenY, clientX, clientY, tag, content, hierachy, related_info) {
        this.addEvent(false, type, timestamp, screenX, screenY, clientX, clientY, tag, content, hierachy, related_info);
    }

    addRRWebEvent(event) {
        this.rrweb_record.push(event);
    }
}

class PageManager {
    constructor() {
        this.start_timestamp = 0;
        this.end_timestamp = 0;
        this.dwell_time = 0;
        this.page_timestamps = [];
        this.last_viewed_time = 0;
    }

    initialize() {
        printDebug("page", "PageManager initialize");
        this.start_timestamp = _time_now();
        this.end_timestamp = this.start_timestamp;
        this.dwell_time = 0;
        this.page_timestamps = [];
        this.last_viewed_time = this.start_timestamp;
    }

    pageInteract() {
        this.last_viewed_time = _time_now();
    }

    pageLeave() {
        this.end_timestamp = _time_now();
        this.page_timestamps.push({ inT: this.last_viewed_time, outT: this.end_timestamp });
        this.dwell_time += this.end_timestamp - this.last_viewed_time;
        this.last_viewed_time = this.end_timestamp;
    }
}

class ViewState {
    constructor(unitPage, pageManager) {
        this.unitPage = unitPage;
        this.pageManager = pageManager;
        this.is_sent = false;
        this.sent_when_active = false;
        this.is_visible = true;
        this.time_last_op = 0;
        this.time_limit = 60000; // 1 minute
        this._is_visibility_listener_added = false;
        this._are_event_listeners_added = false;
    }

    checkState() {
        if (_time_now() - this.time_last_op >= this.time_limit && this.is_visible) {
            this.toggleState();
        } else if (this.is_visible) {
            setTimeout(() => this.checkState(), this.time_limit);
        }
    }

    toggleState() {
        this.is_visible = !this.is_visible;
        printDebug("page", `ViewState: view state changed to ${this.is_visible}`);
        if (this.is_visible) {
            this.checkState();
            this.pageManager.pageInteract();
        } else {
            this.pageManager.pageLeave();
        }
    }

    pageInteract() {
        this.time_last_op = _time_now();
        if (!this.is_visible) {
            this.toggleState();
        }
    }

    mMove(e) {
        this.pageInteract();
        mouseRecord.recordMove(e);
    }

    mScroll() {
        this.pageInteract();
        mouseRecord.recordScroll();
    }

    initialize() {
        printDebug("page", "ViewState: initializing");
        this.is_sent = false;

        if (!this._is_visibility_listener_added) {
            document.addEventListener("visibilitychange", (event) => {
                if (document.hidden) {
                    this.pageManager.pageLeave();
                    if (this.sent_when_active) {
                        this.sent_when_active = false;
                        return;
                    }
                    this.flush();
                } else {
                    this.pageManager.pageInteract();
                }
            });
            this._is_visibility_listener_added = true;
        }

        if (!this._are_event_listeners_added) {
            window.addEventListener('mousemove', (e) => this.mMove(e));
            window.addEventListener('scroll', () => this.mScroll());
            window.addEventListener('focus', () => this.pageInteract());
            window.addEventListener('blur', () => this.pageManager.pageLeave());
            window.addEventListener('beforeunload', () => this.flush());
            this._are_event_listeners_added = true;
        }

        this.is_visible = !document.hidden;
        this.time_last_op = _time_now();

        this.unitPage.initialize();
        this.pageManager.initialize();
        mouseRecord.initialize();
        this.checkState();
    }

    sendMessage() {
        if (this.is_sent || _is_server_page(_content_vars.url_now)) {
            return;
        }

        this.pageManager.pageLeave();

        const message = new Message();
        message.command = "send_message";
        message.send_flag = true;
        message.start_timestamp = this.pageManager.start_timestamp;
        message.end_timestamp = this.pageManager.end_timestamp;
        message.dwell_time = this.pageManager.dwell_time;
        message.page_timestamps = JSON.stringify(this.pageManager.page_timestamps);
        message.url = _content_vars.url_now;
        message.referrer = _content_vars.referrer_now;
        message.title = this.unitPage.getTitle();
        message.mouse_moves = JSON.stringify(mouseRecord.getData());
        message.event_list = JSON.stringify(this.unitPage.getEventList());
        message.rrweb_record = JSON.stringify(this.unitPage.getRRWebEvents());
        message.sent_when_active = this.sent_when_active;

        chrome.runtime.sendMessage(message, (response) => {
            if (response && response.success) {
                printDebug("page", "ViewState: message sent successfully.");
            } else {
                printDebug("page", "ViewState: failed to send message.");
            }
        });

        this.is_sent = true;
    }

        flush() {
        if (this.is_sent) {
            return;
        }
        this.sendMessage();
        this.initialize();
        if (window.rrweb) {
            this.rrweb_record = []; // Clear the rrweb events that are already sent
            this.event_list = []; // Clear the events that are already sent
            rrweb.record.takeFullSnapshot();
        }
    }
}

const unitPage = new UnitPage();
const pageManager = new PageManager();
const viewState = new ViewState(unitPage, pageManager);

printDebug("page", "page.js is loaded");