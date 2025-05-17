// Configuration
const config = {
    baseUrl: "http://127.0.0.1:8000",
    minActiveEventInterval: 200,
    minPassiveEventInterval: 100,
    debug: typeof debug !== 'undefined' ? debug : false
};

// Initialize URLs
config.taskUrl = config.baseUrl + "/task/";
config.dataUrl = config.taskUrl + "data/";

// State management
const state = {
    lastActiveEventTimestamp: -1,
    lastPassiveEventTimestamp: -1,
    freezeOverlay: null,
    pendingDefault: false,
    pendingTarget: null,
    isAnnotating: false,
    isServerPage: window.location.href.startsWith(config.baseUrl),
    isTaskActive: true // Default to true, will be updated by checkIsTaskActive
};

// Utility functions
const utils = {
    // Get element hierarchy in HTML format
    getElementHierarchy(element) {
        const result = [];
        let current = element;
        while (current) {
            const tagName = current.tagName?.toLowerCase();
            if (!tagName) break;

            const id = current.id ? ` id="${current.id}"` : '';
            const className = current.className ? ` class="${current.className}"` : '';
            result.unshift(`<${tagName}${id}${className}>`);
            result.push(`</${tagName}>`);
            current = current.parentElement;
        }
        return result.join('');
    },

    // Convert relative link to absolute
    getAbsoluteLink(relativeLink) {
        if (!relativeLink) return "";
        if (!relativeLink.startsWith("h")) {
            const url = window.location.href;
            const startId = url.search('.com');
            return startId !== -1 ? url.slice(0, startId + 4) + relativeLink : relativeLink;
        }
        return relativeLink;
    },

    // Throttle function to limit event frequency
    throttle(func, limit) {
        let lastCall = 0;
        return function (...args) {
            const now = Date.now();
            if (now - lastCall >= limit) {
                lastCall = now;
                return func.apply(this, args);
            }
        };
    },

    // Extract event data from event object
    extractEventData(event, type) {
        const e = event || window.event;

        // Always use the target (bottommost element) rather than currentTarget
        const target = e.target || e.srcElement;
        const tag = target.tagName || target.nodeName || '';
        let content = "";

        // Extract content based on tag type
        if (tag === "IMG" || tag === "img") {
            content = target.src;
        } else if (tag === "INPUT" || tag === "TEXTAREA" || tag === "input" || tag === "textarea") {
            content = target.value;
        } else {
            content = target.innerText;
        }

        // Position calculation
        const screenX = e.screenX || 0;
        const screenY = e.screenY || 0;
        let clientX = e.clientX;
        let clientY = e.clientY;

        // Fallback for events without position
        if (clientX === undefined) {
            clientX = window.innerWidth / 2;
            clientY = window.innerHeight / 2;
        }

        // Related info based on event type
        const relatedInfo = this.getRelatedInfo(e, type, target);

        return {
            type,
            timestamp: Date.now(),
            screenX,
            screenY,
            clientX,
            clientY,
            tag,
            content,
            hierarchy: this.getElementHierarchy(target),
            relatedInfo
        };
    },

    // Get event-specific related information
    getRelatedInfo(event, type, target) {
        switch (type) {
            case 'click':
                if (target.tagName === 'INPUT' || target.tagName === 'BUTTON') {
                    const form = $(target).closest('form');
                    if (form.length > 0) {
                        const formHref = this.getAbsoluteLink(form.attr('action'));
                        return {href: formHref};
                    }
                }
                return {href: this.getAbsoluteLink($(target).attr("href"))};

            case 'scroll':
                return {scrollX: window.scrollX, scrollY: window.scrollY};

            case 'key press':
                return {
                    ctrlKey: event.ctrlKey,
                    shiftKey: event.shiftKey,
                    altKey: event.altKey,
                    metaKey: event.metaKey,
                    key: event.key
                };

            case 'copy':
                return {copied_text: window.getSelection().toString()};

            case 'paste':
                return {pasted_text: event.clipboardData.getData('text')};

            case 'change':
                return {new_value: target.value};

            default:
                return {};
        }
    }
};

// Annotation system
const annotationSystem = {
    // Show the annotation window
    display(eventData, target) {
        state.isAnnotating = true;
        this.freezePage();

        // Store original event data for later use
        state.originalEvent = {
            eventData,
            target
        };

        // Create modal structure
        const modalHtml = this.createModalHTML(eventData);
        const style = this.createModalStyle();

        // Create the DOM elements
        const overlay = $('<div class="annotation-overlay rr-ignore"></div>');
        const modal = $(modalHtml);

        // Calculate position
        const position = this.calculateModalPosition(eventData.clientX, eventData.clientY);

        // Apply styles
        modal.css({
            'position': 'fixed',
            'top': `${position.top}px`,
            'left': `${position.left}px`,
            'width': `${position.width}px`,
            'height': `${position.height}px`,
            'z-index': '100000',
        });

        // Add to DOM
        $('head').append(style);
        overlay.append(modal).appendTo('body');

        // Set up event handlers
        this.setupEventHandlers(overlay, target, eventData);
    },

    // Create HTML for modal
    createModalHTML() {
        return `
    <div class="annotation-wrapper rr-ignore">
        <div class="annotation-modal">
            <div class="questions-container">
                <!-- Question 1 - Purpose -->
                <div class="question-container">
                    <h2>What is the purpose of this <div class="event-type">EVENT_TYPE_PLACEHOLDER</div> event?</h2>
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
    </div>`.replace('EVENT_TYPE_PLACEHOLDER', eventData.type);
    },

    // Create style for modal
    createModalStyle() {
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
    }`.replaceAll(';', ' !important;'); // Override all styles

        return style;
    },

    // Calculate modal position
    calculateModalPosition(clientX, clientY) {
        const popupWidth = 500;
        const popupHeight = 350;

        let left = clientX;
        let top = clientY;

        // Adjust if modal would go off screen
        if (left + popupWidth > window.innerWidth) {
            left = left - popupWidth;
        }

        if (top + popupHeight > window.innerHeight) {
            top = top - popupHeight;
        }

        // Ensure modal is within viewport
        left = Math.max(0, left);
        top = Math.max(0, top);

        return {left, top, width: popupWidth, height: popupHeight};
    },

    // Setup event handlers for the modal
    setupEventHandlers(overlay, target, eventData) {
        // Submit button handler
        $('#submit-btn').click(() => {
            const purpose = $('#purpose').val().trim();
            const isKeyEvent = $('#key-event').is(':checked');

            // Validation
            if (!purpose) {
                alert('Please describe the event purpose');
                return;
            }

            // Prepare annotation data
            const annotation = {
                ignored: false,
                purpose,
                isKeyEvent,
                timestamp: eventData.timestamp
            };

            // Close window and process event
            this.closeAnnotation(overlay);
            eventHandlers.activeEventEnd({...eventData, annotation});

            // Now execute the default action
            this.executeDefaultAction(target, eventData.type);
        });

        // Ignore button handler
        $('#ignore-btn').click(() => {
            this.closeAnnotation(overlay);
            eventHandlers.activeEventEnd({...eventData, annotation: null});

            // Now execute the default action
            this.executeDefaultAction(target, eventData.type);
        });
    },

    // Close annotation
    closeAnnotation(overlay) {
        overlay.remove();
        this.unfreezePage();
        state.isAnnotating = false;
    },

    // Execute default action separately
    executeDefaultAction(target, eventType) {
        if (!target) return;

        // Use a slight delay to ensure UI has updated
        setTimeout(() => {
            // For links, use location change or programmatic click depending on targets
            if (eventType === 'click') {
                if (target.tagName === 'A' && target.href) {
                    // For links, extract and follow the href directly
                    window.location.href = target.href;
                } else if (target.tagName === 'INPUT' &&
                    (target.type === 'submit' || target.type === 'button')) {
                    // For form submission or button click, execute programmatically
                    const form = $(target).closest('form')[0];
                    if (form) {
                        form.submit();
                    } else {
                        // If not inside a form, just trigger the click event
                        this.triggerDefaultAction(target);
                    }
                } else {
                    // For other elements, trigger the default action
                    this.triggerDefaultAction(target);
                }
            }
        }, 50); // Small delay to ensure UI has cleared
    },

    // Trigger the default action using programmatic click
    triggerDefaultAction(target) {
        // Create and dispatch a native click event
        const clickEvent = new MouseEvent('click', {
            bubbles: true,
            cancelable: true,
            view: window
        });

        // Set a flag to avoid re-capturing this click
        state.pendingDefault = true;
        state.pendingTarget = target;

        // Dispatch the event
        target.dispatchEvent(clickEvent);
    },

    // Freeze page while annotation is active
    freezePage() {
        state.freezeOverlay = document.createElement("div");
        state.freezeOverlay.className = "freeze-overlay rr-ignore";
        state.freezeOverlay.style.position = "fixed";
        state.freezeOverlay.style.top = "0";
        state.freezeOverlay.style.left = "0";
        state.freezeOverlay.style.width = "100%";
        state.freezeOverlay.style.height = "100%";
        state.freezeOverlay.style.backgroundColor = "rgba(0,0,0,0.5)";
        state.freezeOverlay.style.zIndex = "100000";
        document.body.appendChild(state.freezeOverlay);

        // Disable scrolling
        document.documentElement.style.overflow = 'hidden';
        document.body.style.overflow = 'hidden';
        document.documentElement.style.touchAction = 'none';

        // Alert when clicking overlay
        state.freezeOverlay.addEventListener("click", () => {
            alert("Please annotate the event first!");
        });
    },

    // Unfreeze page after annotation
    unfreezePage() {
        if (state.freezeOverlay) {
            document.documentElement.style.overflow = '';
            document.body.style.overflow = '';
            document.documentElement.style.touchAction = 'auto';
            state.freezeOverlay.remove();
            state.freezeOverlay = null;
        }
    }
};

// Event handlers module
// Event handlers module
const eventHandlers = {
    // Configuration
    PASSIVE_MODE: false, // Set to false to enable annotation mode

    // Handler for active events (click, etc)
    handleActive(event, type) {
        if (state.isAnnotating) return;

        if (config.debug) console.log(`${type} active event`, event);

        // Skip if default action is pending
        if (state.pendingDefault && state.pendingTarget === event.target) {
            state.pendingDefault = false;
            state.pendingTarget = null;
            return;
        }

        // Get current time for throttling
        const timestamp = Date.now();
        if (timestamp - state.lastActiveEventTimestamp < config.minActiveEventInterval) {
            return;
        }

        state.lastActiveEventTimestamp = timestamp;

        // Check if task is active
        if (typeof checkIsTaskActive === 'function') {
            checkIsTaskActive();
        }

        if (!state.isTaskActive && !config.debug) {
            return;
        }

        // Extract event data - event.target is already the bottommost element
        const eventData = utils.extractEventData(event, type);

        // For active events, prevent default to handle navigation after annotation
        if (!this.PASSIVE_MODE) {
            event.preventDefault();
            event.stopPropagation();
            annotationSystem.display(eventData, event.target);
        } else {
            this.activeEventEnd(eventData);
        }
    },

    // Handler for passive events
    handlePassive(event, type) {
        if (state.isAnnotating) return;

        // Get current time for throttling
        const timestamp = Date.now();
        if (timestamp - state.lastPassiveEventTimestamp < config.minPassiveEventInterval) {
            return;
        }

        state.lastPassiveEventTimestamp = timestamp;

        if (config.debug) console.log(`${type} passive event`, event);

        // Check if task is active
        if (typeof checkIsTaskActive === 'function') {
            checkIsTaskActive();
        }

        if (!state.isTaskActive && !config.debug) {
            return;
        }

        // Extract and process event data - event.target guarantees bottommost element
        const eventData = utils.extractEventData(event, type);
        this.passiveEventEnd(eventData);
    },

    // Process active event completion
    activeEventEnd(eventData) {
        if (typeof mPage !== 'undefined' && typeof mPage.addActiveEvent === 'function') {
            const {type, timestamp, screenX, screenY, clientX, clientY, tag, content, hierarchy, relatedInfo, annotation} = eventData;
            mPage.addActiveEvent(type, timestamp, screenX, screenY, clientX, clientY, tag, content, hierarchy, relatedInfo, annotation);
        }
    },

    // Process passive event completion
    passiveEventEnd(eventData) {
        if (typeof mPage !== 'undefined' && typeof mPage.addPassiveEvent === 'function') {
            const {type, timestamp, screenX, screenY, clientX, clientY, tag, content, hierarchy, relatedInfo} = eventData;
            mPage.addPassiveEvent(type, timestamp, screenX, screenY, clientX, clientY, tag, content, hierarchy, relatedInfo);
        }
    }
};

// Create throttled event handlers with focus on bottommost elements
const createEventHandlers = () => {
    return {
        // For all these handlers, event.target will be the bottommost element
        // Active events
        clickActive: (event) => eventHandlers.handleActive(event, 'click'),

        // Passive events
        // Passive events that don't need to be throttled
        clickPassive: (event) => eventHandlers.handlePassive(event, 'click'),
        rightClick: (event) => eventHandlers.handlePassive(event, 'right click'),
        keyPress: (event) => eventHandlers.handlePassive(event, 'key press'),
        change: (event) => eventHandlers.handlePassive(event, 'change'),
        copy: (event) => eventHandlers.handlePassive(event, 'copy'),
        paste: (event) => eventHandlers.handlePassive(event, 'paste'),
        drag: (event) => eventHandlers.handlePassive(event, 'drag'),
        drop: (event) => eventHandlers.handlePassive(event, 'drop'),
        windowBlur: (event) => eventHandlers.handlePassive(event, 'blur'),
        windowFocus: (event) => eventHandlers.handlePassive(event, 'focus'),
        // Passive events that need to be throttled
        scroll: (event) => utils.throttle((event) => eventHandlers.handlePassive(event, 'scroll'), config.minPassiveEventInterval),
        hover: (event) => utils.throttle((event) => eventHandlers.handlePassive(event, 'hover'), config.minPassiveEventInterval),
    };
};


// Set up the event delegation system
// Use event delegation instead of binding to every element
const setupEventDelegation = () => {
    if (state.isServerPage) {
        // No need to attach event handlers on server pages
        mPage.update = function () {
        };
        return;
    }

    const handlers = createEventHandlers();


    // Add document-level event listeners using delegation
    document.addEventListener('click', (event) => {
        // Ignore clicks on annotation overlay
        if (event.target.closest('.annotation-overlay, .freeze-overlay')) return;

        // Always record the most deeply nested element (event.target is already the bottommost element)
        const target = event.target;

        // Determine if this is an active element (that should trigger navigation/action)
        const isActiveElement = target.tagName === 'A' && target.hasAttribute('href') ||
            target.tagName === 'BUTTON' ||
            (target.tagName === 'INPUT' && (target.type === 'submit' || target.type === 'button'));

        // Check if element is wrapped by an active element
        const isWrappedByActive = target.closest('a[href], button, input[type="submit"], input[type="button"]') !== null;

        // If it's an active element, use active handler, otherwise use passive
        if (isActiveElement) {
            handlers.clickActive(event);
        } else if (!isWrappedByActive) {
            handlers.clickPassive(event);
        }
    }, false);

    // Add mouseover event delegation
    document.addEventListener('mouseover', handlers.hover, false);

    // Add contextmenu event delegation
    document.addEventListener('contextmenu', handlers.rightClick, false);

    // Add change event delegation for inputs and textareas - ensuring we capture the bottommost elements
    document.addEventListener('change', (event) => {
        // event.target is already the bottommost element
        if (event.target.tagName === 'INPUT' || event.target.tagName === 'TEXTAREA') {
            handlers.change(event);
        }
    }, false);

// Add other global event listeners with focus on bottommost elements
    window.addEventListener("scroll", handlers.scroll);
    window.addEventListener("keypress", handlers.keyPress);
    window.addEventListener("copy", handlers.copy);
    window.addEventListener("paste", handlers.paste);
    window.addEventListener("blur", handlers.windowBlur);
    window.addEventListener("focus", handlers.windowFocus);

    // Use event delegation for mouseover and other events that need bottommost elements
    document.addEventListener("mouseover", (event) => {
        // event.target is already the bottommost element by default
        handlers.hover(event);
    });

    document.addEventListener("contextmenu", (event) => {
        // event.target is already the bottommost element by default
        handlers.rightClick(event);
    });

    document.addEventListener("drag", (event) => {
        // event.target is already the bottommost element by default
        handlers.drag(event);
    });

    document.addEventListener("drop", (event) => {
        // event.target is already the bottommost element by default
        handlers.drop(event);
    });
};

/*
    Main Page Object
 */

// Initialize mPage content
mPage.init_content = function () {
    mPage.title = document.title;
};

// Initialize mPage data structures
mPage.initialize = function () {
    mPage.click_results = [];
    mPage.click_others = [];
    mPage.event_list = [];
    mPage.init_content();
};

mPage.initialize();

// Set timeouts for content initialization
setTimeout(mPage.init_content, 500); // Initial delay for content initialization
setTimeout(mPage.init_content, 3000); // Second delay for content initialization

// Start the application
document.addEventListener("DOMContentLoaded", () => {
    if (config.debug) console.log("DOM fully loaded and parsed");

    setupEventDelegation();

    mPage.update();

    // Set up MutationObserver to handle dynamically added elements
    const observer = new MutationObserver(() => {
        mPage.update();
    });

    // Observe the body for changes
    if (document.body) {
        observer.observe(document.body, {childList: true, subtree: true, attributes: true});
    }
});

// Set up timers for updates and checks
setTimeout(() => {
    mPage.update();
}, 1500);

setInterval(checkIsTaskActive, 60000);

// Debug message
if (config.debug) console.log("Webpage is Loaded!");