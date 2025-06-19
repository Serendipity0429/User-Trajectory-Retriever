var baseUrl = "http://127.0.0.1:8000";
var taskUrl = baseUrl + "/task/";
var dataUrl = taskUrl + "data/";
if (debug) console.log("General Page is Loade;d!");

var last_active_event_timestamp = -1;
var last_passive_event_timestamp = -1;
var min_active_event_interval = 200;
var min_passive_event_interval = 100;

var freeze_overlay = null;

var pending_default = false; // whether the default action is pending
var pending_target = null;
var on_annotation = false; // whether the annotation window is on

var is_server_page = window.location.href.substring(0, 21) == baseUrl;

// TODO: enable drag and drop for the annotation window

// get the element hierarchy in HTML format
// leave only the tag name, id, and class name
function getElementHierarchyHTML(element) {
    let current = element;
    let html = '';

    while (current) {
        const tagName = current.tagName.toLowerCase();
        const id = current.id ? ` id="${current.id}"` : '';
        const className = current.className ? ` class="${current.className}"` : '';
        html = `<${tagName}${id}${className}>${html}</${tagName}>`;
        current = current.parentElement;
    }
    return html;
}

// display the annotation window
function displayAnnotationWindow(event, target, type, event_time, screen_x, screen_y, client_x, client_y, tag, content, related_info) {
    on_annotation = true;
    freezePage();
    const style = document.createElement('style');
    style.innerHTML = `
        :root {
            --primary-purple: #6A1B9A;
            --secondary-purple: #9C27B0;
            --light-purple: #E1BEE7;
        }
        
        .annotation-wrapper {
            position: fixed;
        }
        
        .annotation-modal {
            background: white;
            padding: 5%;
            border-radius: 10px;
            box-shadow: 0 0 20px rgba(0,0,0,0.2);
            width: 90%;
            height: 90%;
            max-width: 500px;
            border: 2px solid var(--primary-purple);
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            font-size: 16px;
            box-sizing: initial;
            color: #000;
        }

        .annotation-modal .question-container {
            margin-bottom: 0;
            padding-left: 2%;
        }
        
        .annotation-modal .question-container:has(textarea) {
            padding-left: 0;
        }

        .annotation-modal h2 {
            color: var(--accent-purple);
            margin-top: 0;
            margin-bottom: 5px;
            display: block;
            font-size: 20px;
            font-weight: bold;
            unicode-bidi: isolate;
        }
        
        .annotation-modal h2 div.event-type {
            color: var(--primary-purple);
            display: inline;
        }

        .annotation-modal textarea {
            width: 96%;
            padding: 2%;
            border: 1px solid var(--light-purple);
            border-radius: 5px;
            resize: none;
            min-height: 90px;
            margin: 10px 0;
            font-size: 16px; 
        }

        .annotation-modal .checkbox-group {
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .annotation-modal input[type="checkbox"] {
            accent-color: var(--secondary-purple);
            width: 18px;
            height: 18px;
        }

        .annotation-modal button {
            background: var(--secondary-purple);
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 5px;
            cursor: pointer;
            transition: background 0.3s ease;
            font-size: 16px;
        }

        .annotation-modal button:hover {
            background: var(--primary-purple);
        }

        .annotation-modal .btn-ignore {
            background: #6c757d; /* Grey color */
            color: white;
        }

        .annotation-modal .btn-ignore:hover {
            background: #5a6268; /* Darker grey */
        }


        .annotation-modal .form-footer {
            padding-top: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            bottom: 0;
        }
        `;
    style.innerHTML.replaceAll(';', ' !important;'); // override all styles
    const overlay = $('<div class="annotation-overlay rr-ignore"></div>');
    const modal = $(`
    <div class="annotation-wrapper rr-ignore">
        <div class="annotation-modal">
            <div class="questions-container">
                <!-- Question 1 - Purpose -->
                <div class="question-container">
                    <h2>What is the purpose of this <div class="event-type">${type}</div> event?</h2>
                    <textarea id="purpose" placeholder="Describe the event purpose..."></textarea>
                </div>
            </div>
    
            <!-- Question 2 - Key Event -->
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
        activeEventEnd(type, event_time, screen_x, screen_y, client_x, client_y, tag, content, hierachy, related_info, annotation);
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
    if (relative_link == undefined) {
        return "";
    }
    if (relative_link[0] !== "h") {
        var url = window.location.href;
        var start_id = url.search('.com');
        relative_link = url.slice(0, start_id + 4) + relative_link;
    }
    return relative_link;
}

/*
    Event handlers
 */

// !important !important
var PASSIVE_MODE = true; // whether to annotate the events

// Active event handler
function activeEventHandler(event, type) {
    if (on_annotation) return;

    console.log(type + " active event", event);
    if (pending_default && pending_target == event.target) { // if the default action is pending, do nothing
        console.log("pending default");
        pending_default = false;
        pending_target = null;
        console.log(pending_default);
        return;
    }
    var event_time = (new Date()).getTime();
    // filter out the repeated active event
    if (event_time - last_active_event_timestamp < min_active_event_interval) {
        return;
    } else {
        last_active_event_timestamp = event_time;
    }

    checkIsTaskActive();
    if (!is_task_active && !debug) {
        return;
    }

    if (!PASSIVE_MODE) {
        event.preventDefault();
        event.stopPropagation(); // stop the event from bubbling up
    }

    let e = event || window.event;
    let screen_x = e.screenX;
    let screen_y = e.screenY;
    let client_x = e.clientX;
    let client_y = e.clientY;
    let target = e.currentTarget;
    let tag = e.target.tagName; // tag name

    if (client_x == undefined) {
        // set the position to the center of the webpage
        console.log("client_x is undefined");
        screen_x = window.screen.width;
        screen_y = window.screen.height;
        client_x = window.innerWidth / 2;
        client_y = window.innerHeight / 2;
    }

    if (debug) console.log("client_x: " + client_x + " client_y: " + client_y);

    let content = "";
    if (tag == "img") {
        content = e.target.src;
    } else if (tag == "input" || tag == "textarea") {
        content = e.target.value;
    } else {
        content = e.target.innerText;
    }


    let href = $($(this).get(0)).attr("href");
    href = recoverAbsoluteLink(href);

    related_info = { 'href': href };
    // set related_info according to the event type and target
    switch (type) {
        case 'click':
            if (tag == 'input' || tag == 'button') {
                // get the form element that the button belongs to
                let form = $(target).closest('form');
                if (form.length > 0) {
                    let form_href = form.attr('action');
                    // parse the form link
                    form_href = recoverAbsoluteLink(related_info);
                    related_info = { 'href': form_href };
                }
            }
            break;
        default:
            break;
    }

    if (PASSIVE_MODE) {
        let hierachy = getElementHierarchyHTML(e.target);
        activeEventEnd(type, event_time, screen_x, screen_y, client_x, client_y, tag, content, hierachy, related_info, '');
    } else {
        // open an annotation window at the clicked position
        displayAnnotationWindow(event, target, type, event_time, screen_x, screen_y, client_x, client_y, tag, content, related_info);
    }
}

function activeEventEnd(type, event_time, screen_x, screen_y, client_x, client_y, tag, content, hierachy, related_info, annotation) {
    // add the event to the event list
    mPage.addActiveEvent(type, event_time, screen_x, screen_y, client_x, client_y, tag, content, hierachy, related_info, annotation);
}


function passiveEventHandler(event, type) {
    if (on_annotation) return;
    var event_time = (new Date()).getTime();
    // filter out the repeated or too frequent passive event
    if (event_time - last_passive_event_timestamp < min_passive_event_interval) {
        return;
    } else {
        last_passive_event_timestamp = event_time;
    }
    if (debug) console.log(type + " passive event", event);
    // checkIsTaskActive();
    if (!is_task_active && !debug) {
        return;
    }

    // event.preventDefault();
    // event.stopPropagation(); // stop the event from bubbling up

    var e = event || window.event;
    var screen_x = e.screenX;
    var screen_y = e.screenY;
    var client_x = e.clientX;
    var client_y = e.clientY;
    var target = e.currentTarget;
    var tag = e.target.tagName; // tag name
    if (tag == undefined) {
        tag = e.target.nodeName;
    }
    var content = "";
    if (tag == "IMG") {
        content = e.target.src;
    } else if (tag == "INPUT" || tag == "TEXTAREA") {
        content = e.target.value;
    } else {
        content = e.target.innerText;
    }

    var related_info = {};
    // set related_info according to the event type and target
    switch (type) {
        case 'scroll':
            related_info = { 'scrollX': window.scrollX, 'scrollY': window.scrollY };
        case 'hover':
            break;
        case 'right click':
            break;
        case 'key press':
            related_info = {
                'ctrlKey': e.ctrlKey, 'shiftKey': e.shiftKey, 'altKey': e.altKey, 'metaKey': e.metaKey, 'key': e.key,
            }
            break;
        case 'copy':
            var copied_text = window.getSelection().toString();
            related_info = { 'copied_text': copied_text };
            break;
        case 'paste':
            var pasted_text = e.clipboardData.getData('text');
            related_info = { 'pasted_text': pasted_text };
            break;
        case 'change':
            // get the original value of the input element and the new value
            var new_value = e.target.value;
            related_info = { 'new_value': new_value };
            break;
        case 'blur':
            break;
        case 'focus':
            break;
        case 'drag':
            break;
        default:
            break;
    }

    let hierachy = getElementHierarchyHTML(e.target);

    // add the event to the event list
    mPage.addPassiveEvent(type, event_time, screen_x, screen_y, client_x, client_y, tag, content, hierachy, related_info);
}

function clickEvent(event, is_active = true) {
    if (is_active) {
        activeEventHandler(event, 'click');
    } else {
        passiveEventHandler(event, 'click');
    }
}

function activeClickEvent(event) {
    clickEvent(event, true);
}

function passiveClickEvent(event) {
    clickEvent(event, false);
}

function hoverEvent(event) {
    passiveEventHandler(event, 'hover');
}

function rightClickEvent(event) {
    passiveEventHandler(event, 'right click');
}

function keyPressEvent(event) {
    passiveEventHandler(event, 'key press');
}

function changeEvent(event) {
    passiveEventHandler(event, 'change');
}

function scrollEvent(event) {
    passiveEventHandler(event, 'scroll');
}

function copyEvent(event) {
    passiveEventHandler(event, 'copy');
}

function pasteEvent(event) {
    passiveEventHandler(event, 'paste');
}

function dragEvent(event) {
    passiveEventHandler(event, 'drag');
}

function dropEvent(event) {
    passiveEventHandler(event, 'drop');
}

function windowBlurEvent(event) {
    passiveEventHandler(event, 'blur');
}

function windowFocusEvent(event) {
    passiveEventHandler(event, 'focus');
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

setTimeout(mPage.init_content, 500); // wait for the page to load
setTimeout(mPage.init_content, 3000); // wait for the page to load


chrome.runtime.sendMessage({ log_status: "request" }, function (response) {
    if (current_url.substring(0, 21) == baseUrl) {
        mPage.update = function () {
        };
    } else {
        // var interactive_element = "div, a, button, input, textarea, select, img";
        var interactive_element = "*";
        var excluded_element = ".annotation-overlay *, .annotation-overlay, body, html, .freeze-overlay"
        mPage.update = function () {
            is_server_page = window.location.href.substring(0, 21) == baseUrl;
            $(interactive_element).not(excluded_element).each(function (id, element) {
                // click event
                if ($(element).attr("bindClick") == undefined) {
                    var tag_name = $(element).prop("tagName");
                    var type = $(element).attr("type");
                    // if ($(element).attr('href') != undefined || tag_name == 'BUTTON' || type == 'submit' || type == 'button') {
                    if ($(element).attr('href') != undefined && tag_name == 'A') {
                        $(element).attr("bindClick", true);
                        $(element).on("click", activeClickEvent);
                    } else {
                        // judge if it is wrapped by <a> or <button>
                        if (($(element).closest('a').length > 0 && $(element).closest('a').attr('href') != undefined)
                            || $(element).closest('button').length > 0 || $(element).closest('input').length > 0) {
                            return; // it is already binded by the parent element
                        }
                        $(element).on("click", passiveClickEvent);
                    }
                }
                // hover event
                if ($(element).attr("bindHover") == undefined) {
                    $(element).attr("bindHover", true);
                    $(element).on("mouseover", hoverEvent);
                }
                // right click event
                if ($(element).attr("bindRightClick") == undefined) {
                    $(element).attr("bindRightClick", true);
                    $(element).on("contextmenu", rightClickEvent);
                }
                // change event
                if ($(element).attr("bindChange") == undefined) {
                    var tag_name = $(element).prop("tagName");
                    if (tag_name == 'TEXTAREA' || tag_name == 'INPUT') {
                        $(element).attr("bindChange", true);
                        $(element).on("change", changeEvent);
                    }
                }
            }
            );

        }
            ;
        addEventListener("scroll", scrollEvent);
        addEventListener("keypress", keyPressEvent);
        addEventListener("copy", copyEvent);
        addEventListener("paste", pasteEvent);
        addEventListener("blur", windowBlurEvent);
        addEventListener("focus", windowFocusEvent);
        addEventListener("drag", dragEvent);
        addEventListener("drop", dropEvent);
    }

    addEventListener("DOMContentLoaded", function (event) {
        if (debug) console.log("DOM fully loaded and parsed");
        mPage.update();
        const observer = new MutationObserver(function (mutations) {
            // if (debug) console.log("DOM changed: " + mutations);
            mPage.update();
        });
        if (debug) console.log(document.body);
        // observe all <a> elements
        observer.observe(document.body, { childList: true, subtree: true, attributes: true });
    });

    setTimeout(mPage.update, 1500);
    setInterval(checkIsTaskActive, 60000);
});

// setTimeout(viewState.sendMessage, 1500);