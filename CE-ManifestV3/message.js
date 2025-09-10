/**
 * @fileoverview Defines core message models for the extension's content scripts,
 * This file has been updated to use asynchronous message passing
 * as required by Manifest V3.
 */
class Message {
    constructor() {
        this.send_flag = false; // Whether to send the message to the backend
        this.username = "";
        this.command = "";
        /* command types
            - check_logging_status: Check the user's logging status
            - request_link_update: A request to update a link
            - inject_script: Inject a script into the page
            - send_message: Send a message to the backend
            - get_active_task: Get the active task ID
            -
        */
        this.start_timestamp = 0;
        this.end_timestamp = 0;
        this.dwell_time = 0;
        this.page_timestamps = [];
        this.type = "msg_from_content"; // Three types of messages: from content, from background, from popup
        this.url = "";
        this.referrer = "";
        this.mouse_moves = "";
        this.event_list = "";
        this.rrweb_record = "";
    }

    initialize() {
        this.send_flag = false;
        this.username = "";
        this.start_timestamp = 0;
        this.end_timestamp = 0;
        this.dwell_time = 0;
        this.page_timestamps = "";
        this.type = "msg_from_content";
        this.url = "";
        this.referrer = "";
        this.mouse_moves = "";
        this.event_list = "";
        this.rrweb_record = "";
    }
}

// Main body
printDebug("message.js is loaded");