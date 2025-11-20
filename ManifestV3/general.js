(async () => {
    /**
     * @fileoverview General event listeners for content scripts.
     */


    await initializeConfig();

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

    const is_task_active = taskStatusResponse ? taskStatusResponse.is_task_active : false;

    if (!is_task_active) {
        // NOTICE: Since general.js is loaded before content.js, this return will cause content.js to not load as well.
        printDebug("general", "No active task, script is disabled");
        return;
    }

    const ANNOTATION_MODAL_STYLE = `
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

    function GENERATE_ANNOTATION_MODAL_HTML(type) {
        const ANNOTATION_MODAL_HTML = `
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
    </div>
    `;
        return ANNOTATION_MODAL_HTML;
    }

    const annotation_module = {
        is_annotating: false,
        freeze_overlay: null,
        annotation_id: 0,

        MODAL_STYLE: ANNOTATION_MODAL_STYLE,
        MODAL_HTML: (type) => GENERATE_ANNOTATION_MODAL_HTML(type),

        display(event, target, type, eventTime, screenX, screenY, clientX, clientY, tag, content, relatedInfo) {
            this.is_annotating = true;
            this.annotation_id++;
            const currentAnnotationId = this.annotation_id;

            this.freezePage();
            const style = document.createElement('style');
            style.innerHTML = this.MODAL_STYLE.replaceAll(';', ' !important;');

            const overlay = document.createElement('div');
            overlay.className = 'annotation-overlay rr-ignore';

            const modalHTML = this.MODAL_HTML(type);
            const modal = document.createElement('div');
            modal.innerHTML = modalHTML;

            const popup_width = 500;
            const popup_height = 350;
            let viewport_left = clientX;
            let viewport_top = clientY;
            if (viewport_left + popup_width > window.innerWidth) viewport_left -= popup_width;
            if (viewport_top + popup_height > window.innerHeight) viewport_top -= popup_height;
            viewport_left = Math.max(0, viewport_left);
            viewport_top = Math.max(0, viewport_top);

            Object.assign(modal.style, {
                'position': 'fixed',
                'top': `${viewport_top}px`,
                'left': `${viewport_left}px`,
                'width': `${popup_width}px`,
                'height': `${popup_height}px`,
                'z-index': '100000',
            });

            document.head.appendChild(style);
            overlay.appendChild(modal);
            document.body.appendChild(overlay);
            overlay.style.display = 'block';

            const endAnnotation = (annotationId) => {
                if (annotationId !== this.annotation_id) {
                    return;
                }
                overlay.remove();
                this.unfreezePage();
                if (type === 'click') {
                    const anchor = target.closest('a[href]');
                    if (anchor && anchor.href) {
                        window.location.href = anchor.href;
                    } else {
                        target.click();
                    }
                }
                this.is_annotating = false;
            };

            document.getElementById('submit-btn').addEventListener('click', () => {
                const purpose = document.getElementById('purpose').value.trim();
                const is_key_event = document.getElementById('key-event').checked;
                if (!purpose) {
                    alert('Please describe the event purpose.');
                    return;
                }
                const hierarchy = event_tracker.getElementHierarchyHTML(target);
                const annotation = { ignored: false, purpose, isKeyEvent: is_key_event, timestamp: eventTime };
                unitPage.addActiveEvent(type, eventTime, screenX, screenY, clientX, clientY, tag, content, hierarchy, relatedInfo, annotation);
                endAnnotation(currentAnnotationId);
            });

            document.getElementById('ignore-btn').addEventListener('click', () => {
                const hierarchy = event_tracker.getElementHierarchyHTML(target);
                unitPage.addActiveEvent(type, eventTime, screenX, screenY, clientX, clientY, tag, content, hierarchy, relatedInfo, null);
                endAnnotation(currentAnnotationId);
            });
        },

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

        unfreezePage() {
            if (this.freeze_overlay) {
                document.documentElement.style.overflow = '';
                document.body.style.overflow = '';
                this.freeze_overlay.remove();
                this.freeze_overlay = null;
            }
        }
    };


    const event_tracker = {

        getCssSelector(el) {
            if (!(el instanceof Element)) return;
            const path = [];
            while (el.nodeType === Node.ELEMENT_NODE) {
                if (el.classList.contains('evidence-highlight') && el.tagName.toLowerCase() === 'span') {
                    el = el.parentNode;
                    continue;
                }
                let selector = el.nodeName.toLowerCase();
                if (el.id) {
                    selector += '#' + el.id;
                    path.unshift(selector);
                    break;
                } else {
                    let sib = el, nth = 1;
                    while (sib = sib.previousElementSibling) {
                        if (sib.nodeName.toLowerCase() == selector)
                            nth++;
                    }
                    if (nth != 1)
                        selector += ":nth-of-type("+nth+")";
                }
                path.unshift(selector);
                el = el.parentNode;
            }
            return path.join(" > ");
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
            if (!element || !element.tagName || depth <= 0) return ['<html>'];
            const hierarchy = [];
            let current = element;
            while (current && depth > 0) {
                const tag_name = current.tagName.toLowerCase();
                const attributes = Array.from(current.attributes).map(attr => ` ${attr.name}="${attr.value}"`).join('');
                hierarchy.push(`<${tag_name}${attributes}>`);
                current = current.parentElement;
                depth--;
            }
            return hierarchy;
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
            related_info.dom_position = this.getCssSelector(target);

            if (getConfig().is_passive_mode) {
                const hierarchy = this.getElementHierarchyHTML(target);
                unitPage.addActiveEvent(type, Date.now(), e.screenX, e.screenY, e.clientX, e.clientY, target.tagName, this.getElementContent(target), hierarchy, related_info, '');
            } else {
                annotation_module.display(event, target, type, Date.now(), e.screenX, e.screenY, e.clientX, e.clientY, target.tagName, this.getElementContent(target), related_info);
            }
        },

        passiveEventHandler(event, type) {
            const e = event || window.event;
            const target = e.target;
            const hierarchy = this.getElementHierarchyHTML(target);
            const related_info = this.getRelatedInfo(target, type, e);
            related_info.dom_position = this.getCssSelector(target);
            unitPage.addPassiveEvent(type, Date.now(), e.screenX, e.screenY, e.clientX, e.clientY, target.tagName, this.getElementContent(target), hierarchy, related_info);
        },

        handleEvent(event, type) {
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
