var mPage = {
    click_results: [],
    click_others: [],
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

    getInterface: function () {
        return mPage.interface;
    },

    getPreAnnotate: function () {
        return mPage.preAnnotate;
    },

    getClickedResults: function () {
        return mPage.click_results;
    },

    click: function (link_obj, type, id, click_time, pos_x, pos_y, content) {
        var new_click = {
            href: $(link_obj).attr("href"),
            type: type,
            id: id,
            timestamp: click_time,
            pos_x: pos_x,
            pos_y: pos_y,
            content: content
        };
        mPage.click_results.push(new_click);
    },

    getClickedOthers: function () {
        return mPage.click_others;
    },
    clickother: function (href, pos_x, pos_y, timestamp, content) {
        var new_click_record = {
            href: href,
            pos_x: pos_x,
            pos_y: pos_y,
            timestamp: timestamp,
            content: content
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