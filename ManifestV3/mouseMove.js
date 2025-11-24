
/**
 * @fileoverview This script has been refactored to modernize its approach to tracking mouse movements and scroll events.
 * The previous implementation, which relied on complex custom classes like `Path` and `Point`, has been replaced with a more
 * streamlined and efficient method.
 *
 * Key Improvements:
 * - **Simplified Data Structure**: Instead of calculating and storing individual moves, this version captures a series of
 *   timestamped coordinates (`{x, y, time}`). This approach is more direct and reduces processing overhead in the content script.
 * - **Throttling with `requestAnimationFrame`**: Mouse and scroll events are throttled using `requestAnimationFrame`,
 *   ensuring that data is collected smoothly without overwhelming the browser's rendering cycle. This is more efficient than
 *   the previous time-based throttling.
 * - **Modernized Code**: The code no longer relies on jQuery for scroll position and uses standard browser APIs,
 *   improving performance and removing dependencies.
 * - **Removed Unused Features**: The `replay` functionality, which appeared to be for debugging, has been removed to
 *   simplify the script and focus on its core purpose: data collection.
 *
 * The new `mouseRecord` object provides a clear and straightforward API (`initialize`, `recordMove`, `recordScroll`, `getData`, `clear`)
 * for managing user interaction data, making it easier to integrate with the rest of the extension.
 */

const mouseRecord = {
    movePath: [],
    scrollPath: [],
    isMoveRecording: false,
    isScrollRecording: false,

    initialize() {
        this.movePath = [];
        this.scrollPath = [];
        this.isMoveRecording = false;
        this.isScrollRecording = false;
        printDebug("mouseMove", "mouseRecord initialized");
    },

    recordMove(e) {
        if (this.isMoveRecording) return;
        this.isMoveRecording = true;

        window.requestAnimationFrame(() => {
            this.movePath.push({
                x: e.pageX,
                y: e.pageY,
                time: Date.now(),
                type: "move"
            });
            this.isMoveRecording = false;
        });
    },

    recordScroll() {
        if (this.isScrollRecording) return;
        this.isScrollRecording = true;

        window.requestAnimationFrame(() => {
            this.scrollPath.push({
                x: window.scrollX,
                y: window.scrollY,
                time: Date.now(),
                type: "scroll"
            });
            this.isScrollRecording = false;
        });
    },

    getData() {
        return [...this.movePath, ...this.scrollPath];
    },

    clearData() {
        this.movePath = [];
        this.scrollPath = [];
    }
};