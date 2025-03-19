var mPage = {
    click_results: [],
    click_others: [],
    event_annotations: [],
    behaviours: [],
    query: "",
    page_id: 0,
    html: null,
    title: null,
    interface: 1,
    preAnnotate: -1, // if the user has annotated the preliminaries (e.g. task purpose)


    getQuery: function () {
        return mPage.query;
    },


    getHtml: function () {
        return mPage.html;
    },

    getTitle: function () {
        return mPage.title;
    },

    getPageId: function () {
        return mPage.page_id;
    },

    getInterface: function () {
        return mPage.interface;
    },

    getPreAnnotate: function () {
        return mPage.preAnnotate;
    },

    getClickedResults: function () {
        return mPage.click_results;
    },

    click: function (href, type, id, click_time, pos_x, pos_y, content, tag) {
        var new_click = {
            href: href,
            type: type,
            id: id,
            timestamp: click_time,
            pos_x: pos_x,
            pos_y: pos_y,
            content: content,
            tag: tag
        };
        mPage.click_results.push(new_click);
    },

    getClickedOthers: function () {
        return mPage.click_others;
    },
    clickother: function (href, pos_x, pos_y, timestamp, content, tag) {
        var new_click_record = {
            href: href,
            pos_x: pos_x,
            pos_y: pos_y,
            timestamp: timestamp,
            content: content,
            tag: tag
        };
        mPage.click_others.push(new_click_record);
    },
    lastUpdate: 0,

    update: function () {
        if (debug) console.log("mPage update");
    },

    initialize: function () {
        mPage.preAnnotate = -1;
        mPage.click_results = [];
        mPage.click_others = [];
        if (debug) console.log("mPage initialize");
    }
};

var debug = true;
if (debug) console.log("page.js is loaded");
mPage.initialize();