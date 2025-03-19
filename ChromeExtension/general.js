var baseUrl = "http://127.0.0.1:8000";
var taskUrl = baseUrl + "/task/"
if (debug) console.log("General Page is Loaded!");

mPage.initialize = function () {
    mPage.click_results = new Array();
    mPage.click_others = new Array();
    mPage.init_content();
};

mPage.init_content = function () {
    mPage.title = document.title;
};

setTimeout(mPage.init_content, 1500);
setTimeout(mPage.init_content, 3000);

var last_event_timestamp = -1;
var min_click_interval = 200;

var freeze_overlay = null;

var pending_default = false; // whether the default action is pending
var pending_target = null;
var on_annotation = false; // whether the annotation window is on

var is_server_page = window.location.href.substring(0, 21) == baseUrl;

// TODO: enable drag and drop for the annotation window

// display the annotation window
function displayAnnotationWindow(event, screen_x, screen_y, client_x, client_y, event_time, event_type, target) {
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
    const overlay = $('<div class="annotation-overlay"></div>');
    const modal = $(`
    <div class="annotation-wrapper">
        <div class="annotation-modal">
            <div class="questions-container">
                <!-- Question 1 - Purpose -->
                <div class="question-container">
                    <h2>What is the purpose of this <div class="event-type">${event_type}</div> event?</h2>
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
    var annotationData = {
        ignored: true,
        purpose: '',
        isKeyEvent: false,
        timestamp: event_time
    };

    function endAnnotation() {
        mPage.event_annotations.push(annotationData);
        // Close the Window
        overlay.remove();
        unfreezePage();
        // Do the default action of target element
        pending_default = true;
        pending_target = target;
        on_annotation = false;
        switch(event_type) {
            case 'click':
                target.click();
                break;
            case 'right click':
                // display the right click menu at the clicked position
                var e = new MouseEvent('contextmenu', {
                    bubbles: false,
                    cancelable: true,
                    view: window,
                    screenX: screen_x,
                    screenY: screen_y,
                    clientX: client_x,
                    clientY: client_y
                });
                break;
            case 'change':
                target.change();
                break;
            default:
                break;
        }

    }

    // Submit handler
    $('#submit-btn').click(function () {
        const purpose = $('#purpose').val().trim();
        const isKeyEvent = $('#key-event').is(':checked');

        // Basic validation
        if (!purpose) {
            alert('Please describe the event purpose');
            return;
        }

        // Prepare data object
        annotationData.ignored = false;
        annotationData.purpose = purpose;
        annotationData.isKeyEvent = isKeyEvent;

        // Here you would typically send data to server
        console.log('Annotation Data:', annotationData);

        // Clear form
        $('#purpose').val('');
        $('#key-event').prop('checked', false);

        endAnnotation();
    });

    // Ignore button handler
    $('#ignore-btn').click(function () {
        // Clear form
        $('#purpose').val('');
        $('#key-event').prop('checked', false);

        // Here you would typically send ignore notification to server
        console.log('Event ignored');

        endAnnotation();
    });
}

// freeze the page until the annotation is done
function freezePage() {
    freeze_overlay = document.createElement("div");
    freeze_overlay.className = "freeze-overlay";
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

// Active event handler
function activeEventHandler(event, type) {
    if (on_annotation) {
        return;
    }
    console.log(type + " event", event);
    if (pending_default && pending_target == event.target) { // if the default action is pending, do nothing
        console.log("pending default");
        pending_default = false;
        pending_target = null;
        console.log(pending_default);
        return;
    }
    var event_time = (new Date()).getTime();
    // filter out the repeated click event
    if (event_time - last_event_timestamp < min_click_interval) {
        return;
    } else {
        last_event_timestamp = event_time;
    }

    checkIsTaskActive();
    if (!is_task_active && !debug) {
        return;
    }

    event.preventDefault();
    event.stopPropagation(); // stop the event from bubbling up
    var href = $($(this).get(0)).attr("href");
    if (href == undefined) {
        href = "";
    } else {
        if (href[0] !== "h") {
            var url = window.location.href;
            var start_id = url.search('.com');
            href = url.slice(0, start_id + 4) + href;
        }

    }
    var e = event || window.event;
    var screen_x = e.screenX;
    var screen_y = e.screenY;
    var client_x = e.clientX;
    var client_y = e.clientY;
    var target = e.currentTarget;
    var tag = e.target.tagName; // tag name
    tag = tag.toLowerCase();

    if (client_x == undefined) {
        // set the position to the center of the webpage
        console.log("client_x is undefined");
        screen_x = window.screen.width;
        screen_y = window.screen.height;
        client_x = window.innerWidth / 2;
        client_y = window.innerHeight / 2;
    }

    if(debug)
    {
        console.log("client_x: " + client_x + " client_y: " + client_y);
    }

    if (tag == "img") {
        content = e.target.src;
    } else if (tag == "input" || tag == "textarea") {
        content = e.target.value;
    } else {
        content = e.target.innerText;
    }

    switch (type) {
        case 'click':
            mPage.click(href, screen_x, screen_y, event_time, content, tag)
            break;
        case 'hover':
            break;
        case 'select':
            break;
        case 'right click':
            break;
        case 'key press':
            break;
        case 'change':
            break;
        default:
            break;
    }

    // open an annotation window at the clicked position
    displayAnnotationWindow(event, screen_x, screen_y, client_x, client_y, event_time, type, target);
}

function passiveEventHandler(event, type) {

}


function clickEvent(event) {
    activeEventHandler(event, 'click');
}

function hoverEvent(event) {
    passiveEventHandler(event, 'hover');
}

function rightClickEvent(event) {
    activeEventHandler(event, 'right click');
}

function keyPressEvent(event) {
    passiveEventHandler(event, 'key press');
}

function changeEvent(event) {
    activeEventHandler(event, 'change');
}

function scrollEvent(event) {
    console.log("scroll event", event);
    // mPage.scroll();
}

function copyEvent(event) {
    console.log("copy event", event);

}

if (current_url.substring(0, 21) == baseUrl) {
    mPage.update = function () {
    };
} else {
    // var interactive_element = "a, button, input, textarea, img";
    var interactive_element = "*";
    mPage.update = function () {
        is_server_page = window.location.href.substring(0, 21) == baseUrl;
        $(interactive_element).not(".annotation-overlay, body, html, .freeze-overlay").each(function (id, element) {
            // click event
            if ($(element).attr("bindClick") == undefined) {
                if ($(element).attr("href") != undefined || $(element).attr("type") == "button" || $(element).attr("type") == "submit") {
                    $(element).attr("bindClick", true);
                    $(element).on("click", clickEvent);
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
                $(element).attr("bindChange", true);
                $(element).on("change", changeEvent);
            }
        });
        addEventListener("scroll", scrollEvent);
        addEventListener("keypress", keyPressEvent);
        addEventListener("copy", copyEvent);
    };
}

setTimeout(mPage.update, 1500);