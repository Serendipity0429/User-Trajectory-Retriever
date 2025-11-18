/**
 * @fileoverview Defines core message models for the extension's content scripts,
 * This file has been updated to use asynchronous message passing
 * as required by Manifest V3.
 */
class Message {
    constructor() {
        this.send_flag = false;
        this.command = "";
        this.start_timestamp = 0;
        this.end_timestamp = 0;
        this.dwell_time = 0;
        this.page_switch_record = [];
        this.type = "msg_from_content";
        this.url = "";
        this.referrer = "";
        this.mouse_moves = "";
        this.event_list = "";
        this.rrweb_record = "";
        this.sent_when_active = false;
    }
}