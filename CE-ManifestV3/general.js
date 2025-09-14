/**
 * @fileoverview General event listeners for content scripts.
 */

// --- MODULE: Annotation Manager ---
// Handles the UI and logic for annotating user events. This is only used
// if event_tracker.is_passive_mode is set to false.
const annotation_module = {
    // State
    is_annotating: false,
    freeze_overlay: null,

    // Constants for the annotation modal UI
    // ANNOTATION_MODAL_STYLE and GENERATE_ANNOTATION_MODAL_HTML is defined in utils/resources.js
    MODAL_STYLE: ANNOTATION_MODAL_STYLE,
    MODAL_HTML: (type) => GENERATE_ANNOTATION_MODAL_HTML(type),

    /**
     * Displays the annotation window for an event.
     */
    display(event, target, type, eventTime, screenX, screenY, clientX, clientY, tag, content, relatedInfo) {
        this.is_annotating = true;
        this.freezePage();
        const style = document.createElement('style');
        style.innerHTML = this.MODAL_STYLE.replaceAll(';', ' !important;');

        const overlay = $('<div class="annotation-overlay rr-ignore"></div>');
        const modal = $(this.MODAL_HTML(type));

        // Position the modal near the event coordinates
        const popup_width = 500;
        const popup_height = 350;
        let viewport_left = clientX;
        let viewport_top = clientY;
        if (viewport_left + popup_width > window.innerWidth) viewport_left -= popup_width;
        if (viewport_top + popup_height > window.innerHeight) viewport_top -= popup_height;
        viewport_left = Math.max(0, viewport_left);
        viewport_top = Math.max(0, viewport_top);

        modal.css({
            'position': 'fixed',
            'top': `${viewport_top}px`,
            'left': `${viewport_left}px`,
            'width': `${popup_width}px`,
            'height': `${popup_height}px`,
            'z-index': '100000',
        });

        $('head').append(style);
        overlay.append(modal).appendTo('body');
        overlay.show();

        const endAnnotation = () => {
            overlay.remove();
            this.unfreezePage();
            if (type === 'click') {
                const anchor = target.closest('a[href]');
                // If it's a link, navigate to it after annotation
                if (anchor && anchor.href) {
                    window.location.href = anchor.href;
                } else {
                    target.click(); // Otherwise, trigger the original click
                }
            }
            this.is_annotating = false;
        };

        $('#submit-btn').on('click', () => {
            const purpose = $('#purpose').val().trim();
            const is_key_event = $('#key-event').is(':checked');
            if (!purpose) {
                alert('Please describe the event purpose.');
                return;
            }
            const hierarchy = event_tracker.getElementHierarchyHTML(target);
            const annotation = { ignored: false, purpose, isKeyEvent: is_key_event, timestamp: eventTime };
            unitPage.addActiveEvent(type, eventTime, screenX, screenY, clientX, clientY, tag, content, hierarchy, relatedInfo, annotation);
            endAnnotation();
        });

        $('#ignore-btn').on('click', () => {
            const hierarchy = event_tracker.getElementHierarchyHTML(target);
            unitPage.addActiveEvent(type, eventTime, screenX, screenY, clientX, clientY, tag, content, hierarchy, relatedInfo, null);
            endAnnotation();
        });
    },

    /**
     * Freezes the page with an overlay to prevent interaction during annotation.
     */
    freezePage() {
        this.freeze_overlay = document.createElement("div");
        this.freeze_overlay.className = "freeze-overlay rr-ignore";
        Object.assign(this.freeze_overlay.style, {
            position: "fixed", top: "0", left: "0", width: "100%", height: "100%",
            backgroundColor: "rgba(0,0,0,0.5)", zIndex: "99999"
        });
        document.body.appendChild(this.freeze_overlay);
        document.documentElement.style.overflow = 'hidden';
        document.body.style.overflow = 'hidden';
        this.freeze_overlay.addEventListener("click", () => alert("Please annotate the event first!"));
    },

    /**
     * Unfreezes the page by removing the overlay.
     */
    unfreezePage() {
        if (this.freeze_overlay) {
            document.documentElement.style.overflow = '';
            document.body.style.overflow = '';
            this.freeze_overlay.remove();
            this.freeze_overlay = null;
        }
    }
};

// --- MODULE: Event Tracker ---
// Manages the setup and handling of all DOM event listeners for tracking user behavior.
const event_tracker = {
    is_passive_mode: config.is_passive_mode, // If false, enables the annotation feature on "active" events.


    /**
     * Utility to limit the rate at which a function gets called.
     * @param {Function} func The function to throttle.
     * @param {number} limit The throttle interval in milliseconds.
     */
    throttle(func, limit) {
        let in_throttle;
        return function(...args) {
            if (!in_throttle) {
                func.apply(this, args);
                in_throttle = true;
                setTimeout(() => in_throttle = false, limit);
            }
        };
    },
    
    /**
     * Gets the element's hierarchy as an array of HTML strings.
     * @param {HTMLElement} element The starting element.
     * @returns {string[]}
     */
    getElementHierarchyHTML(element) {
        if (!element || !element.tagName) return ['<html>'];
        const hierarchy = [];
        let current = element;
        while (current) {
            const tag_name = current.tagName.toLowerCase();
            const attributes = Array.from(current.attributes).map(attr => ` ${attr.name}="${attr.value}"`).join('');
            hierarchy.push(`<${tag_name}${attributes}>`);
            current = current.parentElement;
        }
        return hierarchy;
    },

    /**
     * Determines if an element interaction is considered "active" (e.g., clicking a link).
     * @param {HTMLElement} element The event target element.
     * @param {string} eventType The type of event.
     * @returns {boolean}
     */
    isElementActive(element, eventType) {
        if (eventType !== 'click') return false;
        const tag_name = element.tagName.toLowerCase();
        const type_attr = element.getAttribute('type');
        const active_tags = ['a', 'button'];
        const active_input_types = ['submit', 'button', 'reset'];
        if (active_tags.includes(tag_name) && element.hasAttribute('href')) return true;
        if (tag_name === 'input' && active_input_types.includes(type_attr)) return true;
        return !!element.closest('a[href], button');
    },

    /**
     * Extracts the visible content from a target element.
     * @param {HTMLElement} target The element to extract content from.
     * @returns {string}
     */
    getElementContent(target) {
        const tag_name = target.tagName ? target.tagName.toLowerCase() : '';
        if (tag_name === "img") return target.src;
        if (tag_name === "input" || tag_name === "textarea") return target.value;
        return target.innerText;
    },
    
    /**
     * Recovers the absolute URL from a relative link.
     * @param {string} relativeLink The relative URL path.
     * @returns {string} The absolute URL.
     */
    recoverAbsoluteLink(relativeLink) {
        if (typeof relativeLink !== 'string' || !relativeLink) return "";
        if (relativeLink.startsWith('http') || relativeLink.startsWith('//')) return relativeLink;
        try {
            return new URL(relativeLink, window.location.href).href;
        } catch (e) {
            return relativeLink;
        }
    },

    /**
     * Gathers context-specific information related to an event.
     * @param {HTMLElement} target The event target element.
     * @param {string} type The event type.
     * @param {Event} [event=null] The original DOM event object.
     * @returns {object}
     */
    getRelatedInfo(target, type, event = null) {
        const related_info = {};
        const tag_name = target.tagName ? target.tagName.toLowerCase() : '';

        switch (type) {
            case 'click':
                const anchor = target.closest('a[href]');
                if (anchor) {
                    related_info.href = this.recoverAbsoluteLink(anchor.getAttribute('href'));
                } else if (tag_name === 'input' || tag_name === 'button') {
                    const form = target.closest('form');
                    if (form?.hasAttribute('action')) {
                        related_info.href = this.recoverAbsoluteLink(form.getAttribute('action'));
                    }
                }
                break;
            case 'scroll':
                related_info.scrollX = window.scrollX;
                related_info.scrollY = window.scrollY;
                break;
            case 'keypress':
                if (event) {
                    related_info.key = event.key;
                    related_info.ctrlKey = event.ctrlKey;
                    related_info.shiftKey = event.shiftKey;
                }
                break;
            case 'copy':
                related_info.copiedText = window.getSelection().toString();
                break;
            case 'paste':
                if (event?.clipboardData) {
                    related_info.pastedText = event.clipboardData.getData('text');
                }
                break;
            case 'change':
                related_info.newValue = target.value;
                break;
        }
        return related_info;
    },
    
    /**
     * Records an "active" user event, potentially triggering an annotation.
     */
    activeEventHandler(event, type) {
        if (!this.is_passive_mode) {
            event.preventDefault();
            event.stopPropagation();
        }

        const e = event || window.event;
        const target = e.target;
        const related_info = this.getRelatedInfo(target, type);

        if (this.is_passive_mode) {
            const hierarchy = this.getElementHierarchyHTML(target);
            unitPage.addActiveEvent(type, Date.now(), e.screenX, e.screenY, e.clientX, e.clientY, target.tagName, this.getElementContent(target), hierarchy, related_info, '');
        } else {
            annotation_module.display(event, target, type, Date.now(), e.screenX, e.screenY, e.clientX, e.clientY, target.tagName, this.getElementContent(target), related_info);
        }
    },

    /**
     * Records a "passive" user event without interrupting the user.
     */
    passiveEventHandler(event, type) {
        const e = event || window.event;
        const target = e.target;
        const hierarchy = this.getElementHierarchyHTML(target);
        const related_info = this.getRelatedInfo(target, type, e);
        unitPage.addPassiveEvent(type, Date.now(), e.screenX, e.screenY, e.clientX, e.clientY, target.tagName, this.getElementContent(target), hierarchy, related_info);
    },

    /**
     * Main event handler that routes events to active or passive handlers.
     */
    handleEvent(event, type) {
        if (annotation_module.is_annotating) return;

        const target = event.target;
        if (!target || !target.tagName || target.closest('.annotation-overlay, .freeze-overlay')) {
            return;
        }

        if (!_content_vars.is_task_active && !config.is_dev) {
            return;
        }

        if (this.isElementActive(target, type)) {
            this.activeEventHandler(event, type);
        } else {
            this.passiveEventHandler(event, type);
        }
    },

    /**
     * Sets up all the necessary event listeners on the page.
     */
    initialize() {
        if (_is_server_page(_content_vars.url_now)) return;
        
        // Use capture phase for click to potentially prevent default action for annotation
        document.body.addEventListener('click', (e) => this.handleEvent(e, 'click'), true);

        // Passive Events with throttling
        const throttled_hover = this.throttle((e) => this.passiveEventHandler(e, 'hover'), 50);
        const throttled_scroll = this.throttle((e) => this.passiveEventHandler(e, 'scroll'), 50);
        document.body.addEventListener('mouseover', throttled_hover, true);
        document.addEventListener('scroll', throttled_scroll, true);
        
        // Other passive events
        const passive_events = ['contextmenu', 'change', 'keypress', 'copy', 'paste', 'drag', 'drop'];
        passive_events.forEach(eventType => {
            const handler = (e) => this.passiveEventHandler(e, eventType.replace('contextmenu', 'right click'));
            document.body.addEventListener(eventType, handler, true);
        });
        
        window.addEventListener('blur', (e) => this.passiveEventHandler(e, 'blur'), true);
        window.addEventListener('focus', (e) => this.passiveEventHandler(e, 'focus'), true);

        if (config.is_dev) console.log("Event listeners initialized.");
    }
};

// Main body
printDebug("general.js is loaded");