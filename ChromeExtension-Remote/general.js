var baseUrl = "http://101.6.41.59:32904";
var taskUrl = baseUrl + "/task/";
var dataUrl = taskUrl + "data/";
if (debug) console.log("General Page is Loaded!");

var last_active_event_timestamp = -1;
var last_passive_event_timestamp = -1;
var min_active_event_interval = 200;
var min_passive_event_interval = 100;

var freeze_overlay = null;

var pending_default = false; // whether the default action is pending
var pending_target = null;
var on_annotation = false; // whether the annotation window is on

var is_server_page = window.location.href.startsWith(baseUrl) || window.location.href.startsWith("chrome://extensions/") || window.location.href.startsWith("chrome-extension://");

function throttle(func, limit) {
    let inThrottle;
    return function () {
        const args = arguments;
        const context = this;
        if (!inThrottle) {
            func.apply(context, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

// get the element hierarchy in HTML format
// leave only the tag name, id, and class name
function getElementHierarchyHTML(element) {
    if (!element || !element.tagName) return ['<html>']; // Return root if no element is provided
    let current = element;
    let hierarchy = [];

    while (current) {
        let tagName = current.tagName.toLowerCase();
        let attributes = '';
        for (let attr of current.attributes) {
            attributes += ` ${attr.name}="${attr.value}"`;
        }
        hierarchy.push(`<${tagName}${attributes}>`);
        current = current.parentElement;
    }
    return hierarchy;
}

// display the annotation window
function displayAnnotationWindow(event, target, type, event_time, screen_x, screen_y, client_x, client_y, tag, content, related_info) {
    on_annotation = true;
    freezePage();
    const style = document.createElement('style');
    style.innerHTML = `
        :root { --primary-purple: #6A1B9A; --secondary-purple: #9C27B0; --light-purple: #E1BEE7; }
        .annotation-wrapper { position: fixed; }
        .annotation-modal { background: white; padding: 5%; border-radius: 10px; box-shadow: 0 0 20px rgba(0,0,0,0.2); width: 90%; height: 90%; max-width: 500px; border: 2px solid var(--primary-purple); font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; font-size: 16px; box-sizing: initial; color: #000; }
        .annotation-modal .question-container { margin-bottom: 0; padding-left: 2%; }
        .annotation-modal .question-container:has(textarea) { padding-left: 0; }
        .annotation-modal h2 { color: var(--accent-purple); margin-top: 0; margin-bottom: 5px; display: block; font-size: 20px; font-weight: bold; unicode-bidi: isolate; }
        .annotation-modal h2 div.event-type { color: var(--primary-purple); display: inline; }
        .annotation-modal textarea { width: 96%; padding: 2%; border: 1px solid var(--light-purple); border-radius: 5px; resize: none; min-height: 90px; margin: 10px 0; font-size: 16px; }
        .annotation-modal .checkbox-group { display: flex; align-items: center; gap: 10px; }
        .annotation-modal input[type="checkbox"] { accent-color: var(--secondary-purple); width: 18px; height: 18px; }
        .annotation-modal button { background: var(--secondary-purple); color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; transition: background 0.3s ease; font-size: 16px; }
        .annotation-modal button:hover { background: var(--primary-purple); }
        .annotation-modal .btn-ignore { background: #6c757d; color: white; }
        .annotation-modal .btn-ignore:hover { background: #5a6268; }
        .annotation-modal .form-footer { padding-top: 20px; display: flex; justify-content: space-between; align-items: center; bottom: 0; }
        `;
    style.innerHTML.replaceAll(';', ' !important;'); // override all styles
    const overlay = $('<div class="annotation-overlay rr-ignore"></div>');
    const modal = $(`
    <div class="annotation-wrapper rr-ignore">
        <div class="annotation-modal">
            <div class="questions-container">
                <div class="question-container">
                    <h2>What is the purpose of this <div class="event-type">${type}</div> event?</h2>
                    <textarea id="purpose" placeholder="Describe the event purpose..."></textarea>
                </div>
            </div>
            <div class="question-container">
                <h2>Event Classification</h2>
                <div class="checkbox-group">
                    <input type="checkbox" id="key-event">
                    <label for="key-event">Mark as Key Event</label>
                </div>
            </div>
            <div class="form-footer">
                <button type="button" id="submit-btn">Submit</button>
                <button type="button" id="ignore-btn" class="btn-ignore">Ignore this event</button>
            </div>
        </div>
    </div>`);

    // setting the size of the annotation window
    var viewportLeft = client_x;
    var viewportTop = client_y;

    const popupWidth = 500;
    const popupHeight = 350;

    if (viewportLeft + popupWidth > window.innerWidth) {
        viewportLeft = viewportLeft - popupWidth;
    }

    if (viewportTop + popupHeight > window.innerHeight) {
        viewportTop = viewportTop - popupHeight;
    }

    if (viewportLeft < 0) {
        viewportLeft = 0;
    }
    if (viewportTop < 0) {
        viewportTop = 0;
    }

    modal.css({
        'position': 'fixed',
        'top': `${viewportTop}px`,
        'left': `${viewportLeft}px`,
        'width': `${popupWidth}px`,
        'height': `${popupHeight}px`,
        'z-index': '100000',
    });


    $('head').append(style);
    overlay.append(modal).appendTo('body');
    overlay.show();


    //Event handler for submit button
    var annotation = {
        ignored: true, purpose: '', isKeyEvent: false, timestamp: event_time
    };

    function endAnnotation() {
        // Close the Window
        overlay.remove();
        unfreezePage();
        // Do the default action of target element
        pending_default = true;
        pending_target = target;
        switch (type) {
            case 'click':
                target.click();
                break;
            case 'change':
                break;
            default:
                break;
        }
        on_annotation = false;
    }

    // Submit handler
    $('#submit-btn').click(function () {
        const purpose = $('#purpose').val().trim();
        const isKeyEvent = $('#key-event').is(':checked');
        let hierarchy = getElementHierarchyHTML(target);

        // Basic validation
        if (!purpose) {
            alert('Please describe the event purpose');
            return;
        }

        // Prepare data object
        annotation.ignored = false;
        annotation.purpose = purpose;
        annotation.isKeyEvent = isKeyEvent;

        // Here you would typically send data to server
        console.log('Annotation Data:', annotation);

        // Clear form
        $('#purpose').val('');
        $('#key-event').prop('checked', false);

        endAnnotation();
        activeEventEnd(type, event_time, screen_x, screen_y, client_x, client_y, tag, content, hierarchy, related_info, annotation);
    });

    // Ignore button handler
    $('#ignore-btn').click(function () {
        // Clear form
        $('#purpose').val('');
        $('#key-event').prop('checked', false);

        // Here you would typically send ignore notification to server
        console.log('Event ignored');

        endAnnotation();
        activeEventEnd(type, event_time, screen_x, screen_y, client_x, client_y, tag, content, related_info, null); // annotation is null
    });
}

// freeze the page until the annotation is done
function freezePage() {
    freeze_overlay = document.createElement("div");
    freeze_overlay.className = "freeze-overlay rr-ignore";
    freeze_overlay.style.position = "fixed";
    freeze_overlay.style.top = "0";
    freeze_overlay.style.left = "0";
    freeze_overlay.style.width = "100%";
    freeze_overlay.style.height = "100%";
    freeze_overlay.style.backgroundColor = "rgba(0,0,0,0.5)";
    freeze_overlay.style.zIndex = "100000";
    document.body.appendChild(freeze_overlay);
    // disable scrolling
    document.documentElement.style.overflow = 'hidden';
    document.body.style.overflow = 'hidden';
    document.documentElement.style.touchAction = 'none'; // 阻止移动端触摸滚动
    // when click on freeze_overlay, alert users they need to annotate the event
    freeze_overlay.addEventListener("click", function () {
        alert("Please annotate the event first!");
    });
}

// unfreeze the page
function unfreezePage() {
    if (freeze_overlay != null) {
        document.documentElement.style.overflow = '';
        document.body.style.overflow = '';
        document.documentElement.style.touchAction = 'auto';
        freeze_overlay.remove();
    }
}

// recover the absolute hyperlink given the relative hyperlink
function recoverAbsoluteLink(relative_link) {
    if (typeof relative_link !== 'string') {
        return "";
    }
    if (relative_link && !relative_link.startsWith('http') && !relative_link.startsWith('//')) {
        try {
            return new URL(relative_link, window.location.href).href;
        } catch (e) {
            return relative_link;
        }
    }
    return relative_link;
}

/*
    Event handlers
 */

    
// !important !important
var PASSIVE_MODE = true; // whether to annotate the events

function handleEvent(event, type) {
    if (on_annotation) return;

    const target = event.target;
    if (!target || !target.tagName) return;

    // 忽略插件自身UI的事件
    if (target.closest('.annotation-overlay') || target.closest('.freeze-overlay')) {
        return;
    }

    checkIsTaskActive();
    if (!is_task_active && !debug) {
        return;
    }

    const event_time = new Date().getTime();
    const is_active = isElementActive(target, type);

    if (is_active) {
        // if (event_time - last_active_event_timestamp < min_active_event_interval) {
        //     return;
        // }
        // last_active_event_timestamp = event_time;
        activeEventHandler(event, type);
    } else {
        passiveEventHandler(event, type);
    }
}

function isElementActive(element, eventType) {
    if (eventType !== 'click') return false;
    const tagName = element.tagName.toLowerCase();
    const type = element.getAttribute('type');
    if (tagName === 'a' && element.hasAttribute('href')) return true;
    if (tagName === 'button' || (tagName === 'input' && (type === 'submit' || type === 'button' || type === 'reset'))) return true;
    if (element.closest('a[href], button')) return true; // Also check parents
    return false;
}

function activeEventHandler(event, type) {
    if (!PASSIVE_MODE) {
        event.preventDefault();
        event.stopPropagation();
    }

    const e = event || window.event;
    const target = e.target;
    const hierarchy = getElementHierarchyHTML(target);
    const related_info = getRelatedInfo(target, type);

    mPage.addActiveEvent(type, new Date().getTime(), e.screenX, e.screenY, e.clientX, e.clientY, target.tagName, getElementContent(target), hierarchy, related_info, '');
}

function passiveEventHandler(event, type) {
    const e = event || window.event;
    const target = e.target;
    const hierarchy = getElementHierarchyHTML(target);
    const related_info = getRelatedInfo(target, type, e);

    mPage.addPassiveEvent(type, new Date().getTime(), e.screenX, e.screenY, e.clientX, e.clientY, target.tagName, getElementContent(target), hierarchy, related_info);
}

function getElementContent(target) {
    const tagName = target.tagName ? target.tagName.toLowerCase() : '';
    if (tagName === "img") return target.src;
    if (tagName === "input" || tagName === "textarea") return target.value;
    return target.innerText;
}

function getRelatedInfo(target, type, event = null) {
    let related_info = {};
    const tagName = target.tagName ? target.tagName.toLowerCase() : '';

    switch (type) {
        case 'click':
            const anchor = target.closest('a[href]');
            if (anchor) {
                related_info.href = recoverAbsoluteLink(anchor.getAttribute('href'));
            } else if (tagName === 'input' || tagName === 'button') {
                const form = target.closest('form');
                if (form && form.hasAttribute('action')) {
                    related_info.href = recoverAbsoluteLink(form.getAttribute('action'));
                }
            }
            break;
        case 'scroll':
            related_info = { 'scrollX': window.scrollX, 'scrollY': window.scrollY };
            break;
        case 'key press':
            if (event) {
                related_info = { 'ctrlKey': event.ctrlKey, 'shiftKey': event.shiftKey, 'altKey': event.altKey, 'metaKey': event.metaKey, 'key': event.key };
            }
            break;
        case 'copy':
            related_info = { 'copied_text': window.getSelection().toString() };
            break;
        case 'paste':
            if (event && event.clipboardData) {
                related_info = { 'pasted_text': event.clipboardData.getData('text') };
            }
            break;
        case 'change':
            related_info = { 'new_value': target.value };
            break;
    }
    return related_info;
}

function setupEventListeners() {
    if (is_server_page) return;

    // Active/Passive Events
    document.body.addEventListener('click', (e) => handleEvent(e, 'click'), true); // Use capture phase to potentially prevent default

    // Passive Events with throttling
    document.body.addEventListener('mouseover', throttle((e) => passiveEventHandler(e, 'hover'), 50), true);
    document.addEventListener('scroll', throttle((e) => passiveEventHandler(e, 'scroll'), 50), true);

    // Other passive events
    document.body.addEventListener('contextmenu', (e) => passiveEventHandler(e, 'right click'), true);
    document.body.addEventListener('change', (e) => passiveEventHandler(e, 'change'), true);
    document.addEventListener('keypress', (e) => passiveEventHandler(e, 'key press'), true);
    document.addEventListener('copy', (e) => passiveEventHandler(e, 'copy'), true);
    document.addEventListener('paste', (e) => passiveEventHandler(e, 'paste'), true);
    document.addEventListener('drag', (e) => passiveEventHandler(e, 'drag'), true);
    document.addEventListener('drop', (e) => passiveEventHandler(e, 'drop'), true);

    window.addEventListener('blur', (e) => passiveEventHandler(e, 'blur'), true);
    window.addEventListener('focus', (e) => passiveEventHandler(e, 'focus'), true);

    if (debug) console.log("Event listeners set up using delegation.");
}

/*
    End of event handlers
 */

mPage.init_content = function () {
    mPage.title = document.title;
};

mPage.initialize = function () {
    mPage.click_results = new Array();
    mPage.click_others = new Array();
    mPage.event_list = new Array();
    mPage.init_content();
};

mPage.initialize();

setTimeout(mPage.init_content, 3000); // wait for the page to load


// Initialize after DOM is loaded
document.addEventListener("DOMContentLoaded", function (event) {
    if (debug) console.log("DOM fully loaded and parsed");
    mPage.init_content();
    // Setup listeners once the script is running
    chrome.runtime.sendMessage({ log_status: "request" }, function (response) {
        if (!is_server_page) {
            setupEventListeners();
            setInterval(checkIsTaskActive, 60000);
        }
    });
});


// Display a "general.js loaded" box on the upper right corner for 3 seconds
// should have a class named 'rr-ignore' to avoid being recorded by rrweb
document.addEventListener("DOMContentLoaded", function (event) {
    displayLoadedBox("general.js");
});
