var mPage = {
    query: "",
    html: null,
    title: null,
    interface: 1,
    preAnnotate: -1, // if the user has annotated the preliminaries (e.g. task purpose)

    event_list: [], // a list of events (e.g. mouse clicks, mouse movements, etc.) including annotations
    rrweb_events: [], // a list of rrweb events


    getQuery: function () {
        return mPage.query;
    },


    getHtml: function () {
        return mPage.html;
    },

    getTitle: function () {
        return mPage.title;
    },

    getInterface: function () {
        return mPage.interface;
    },

    getPreAnnotate: function () {
        return mPage.preAnnotate;
    },

    getEventList: function () {
        return mPage.event_list;
    },

    getRRWebEvents: function () {
        return mPage.rrweb_events;
    },


    lastUpdate: 0,

    update: function () {
        if (debug) console.log("mPage update");
    },

    initialize: function () {
        mPage.preAnnotate = -1;
        mPage.event_list = [];
        mPage.rrweb_events = [];
        if (debug) console.log("mPage initialize");
    },


    // add a new event
    addEvent(isActive, type, timestamp, screenX, screenY, clientX, clientY, tag, content, hierachy, related_info, annotation = null) {
        let new_event = {
            isActive: isActive,
            type: type,
            timestamp: timestamp,
            screenX: screenX,
            screenY: screenY,
            clientX: clientX,
            clientY: clientY,
            tag: tag,
            content: content,
            hierachy: hierachy,
            related_info: related_info, // e.g. the href of a clicked link
            annotation: annotation,
        };
        mPage.event_list.push(new_event);
    },

    addActiveEvent(type, timestamp, screenX, screenY, clientX, clientY, tag, content, hierachy, related_info, annotation = null) {
        mPage.addEvent(true, type, timestamp, screenX, screenY, clientX, clientY, tag, content, hierachy, related_info, annotation);
    },

    addPassiveEvent(type, timestamp, screenX, screenY, clientX, clientY, tag, content, hierachy, related_info) {
        mPage.addEvent(false, type, timestamp, screenX, screenY, clientX, clientY, tag, content, hierachy, related_info);
    },

    addRRWebEvent(event) {
        mPage.rrweb_events.push(event);
    }

};
// var debug = true;
var debug = false;
if (debug) console.log("page.js is loaded");
