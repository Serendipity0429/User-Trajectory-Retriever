(async () => {
    /**
     * @fileoverview General event listeners for content scripts.
     */


    await initializeConfig();

    let is_task_active = false;

    const checkTaskStatus = async () => {
        const taskStatusResponse = await new Promise((resolve) => {
            chrome.runtime.sendMessage({ type: "msg_from_popup", command: "get_active_task" }, (response) => {
                if (chrome.runtime.lastError) {
                    console.error("Error getting task status in general.js:", chrome.runtime.lastError.message);
                    resolve(null);
                    return;
                }
                resolve(response);
            });
        });
        is_task_active = taskStatusResponse ? taskStatusResponse.is_task_active : false;
        printDebug("general", `Task status updated: ${is_task_active}`);
    };

    await checkTaskStatus();

    chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
        if (message.command === 'refresh_task_status') {
            checkTaskStatus();
        }
    });

    const event_tracker = {

        getCssSelector(el) {
            return getCssSelector(el);
        },

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
        
        getElementHierarchyHTML(element, depth = 10) {
            return getElementHierarchyHTML(element, depth);
        },

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

        getElementContent(target) {
            const tag_name = target.tagName ? target.tagName.toLowerCase() : '';
            if (tag_name === "img") return target.src;
            if (tag_name === "input" || tag_name === "textarea") return target.value;
            return target.innerText;
        },
        
        recoverAbsoluteLink(relativeLink) {
            if (typeof relativeLink !== 'string' || !relativeLink) return "";
            if (relativeLink.startsWith('http') || relativeLink.startsWith('//')) return relativeLink;
            try {
                return new URL(relativeLink, window.location.href).href;
            } catch (e) {
                return relativeLink;
            }
        },

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
        
        activeEventHandler(event, type) {
            if (!getConfig().is_passive_mode) {
                event.preventDefault();
                event.stopPropagation();
            }

            const e = event || window.event;
            const target = e.target;
            const related_info = this.getRelatedInfo(target, type);
            related_info.dom_position = getCssSelector(target);

            if (getConfig().is_passive_mode) {
                const hierarchy = getElementHierarchyHTML(target);
                unitPage.addActiveEvent(type, Date.now(), e.screenX, e.screenY, e.clientX, e.clientY, target.tagName, this.getElementContent(target), hierarchy, related_info, '');
            } else {
                annotation_module.display(event, target, type, Date.now(), e.screenX, e.screenY, e.clientX, e.clientY, target.tagName, this.getElementContent(target), related_info);
            }
        },

        passiveEventHandler(event, type) {
            const e = event || window.event;
            const target = e.target;
            const hierarchy = getElementHierarchyHTML(target);
            const related_info = this.getRelatedInfo(target, type, e);
            related_info.dom_position = getCssSelector(target);
            unitPage.addPassiveEvent(type, Date.now(), e.screenX, e.screenY, e.clientX, e.clientY, target.tagName, this.getElementContent(target), hierarchy, related_info);
        },

        handleEvent(event, type) {
            if (!is_task_active) return;
            if (annotation_module.is_annotating) return;

            const target = event.target;
            if (!target || !target.tagName || target.closest('.annotation-overlay, .freeze-overlay')) {
                return;
            }

            if (this.isElementActive(target, type)) {
                this.activeEventHandler(event, type);
            } else {
                this.passiveEventHandler(event, type);
            }
        },

        initialize() {
            if (typeof _content_vars !== 'undefined' && _content_vars.url_now && _is_server_page(_content_vars.url_now)) return;
            
            document.addEventListener('click', (e) => this.handleEvent(e, 'click'), true);

            const throttled_hover = this.throttle((e) => this.passiveEventHandler(e, 'hover'), 50);
            const throttled_scroll = this.throttle((e) => this.passiveEventHandler(e, 'scroll'), 50);
            document.addEventListener('mouseover', throttled_hover, true);
            document.addEventListener('scroll', throttled_scroll, true);
            
            const passive_events = ['contextmenu', 'change', 'keypress', 'copy', 'paste', 'drag', 'drop'];
            passive_events.forEach(eventType => {
                const handler = (e) => this.passiveEventHandler(e, eventType.replace('contextmenu', 'right click'));
                document.addEventListener(eventType, handler, true);
            });
            
            window.addEventListener('blur', (e) => this.passiveEventHandler(e, 'blur'), true);
            window.addEventListener('focus', (e) => this.passiveEventHandler(e, 'focus'), true);

            printDebug("general", "Event tracker initialized with " + (getConfig().is_passive_mode ? "passive" : "active") + " mode.");
        }
    };
    // Defer initialization until everything is ready to avoid accessing null elements
    if (document.readyState === "complete") {
        document.addEventListener("loaded", event_tracker.initialize.bind(event_tracker));
    } else {
        event_tracker.initialize();
    }

    printDebug("general", "general.js is loaded");
})();