/**
 * @fileoverview Manages the UI for the annotation modal.
 * Separated from general.js for better maintainability.
 */

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
            // Use global getElementHierarchyHTML from utils.js
            const hierarchy = getElementHierarchyHTML(target);
            const annotation = { ignored: false, purpose, isKeyEvent: is_key_event, timestamp: eventTime };
            unitPage.addActiveEvent(type, eventTime, screenX, screenY, clientX, clientY, tag, content, hierarchy, relatedInfo, annotation);
            endAnnotation(currentAnnotationId);
        });

        document.getElementById('ignore-btn').addEventListener('click', () => {
            // Use global getElementHierarchyHTML from utils.js
            const hierarchy = getElementHierarchyHTML(target);
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
