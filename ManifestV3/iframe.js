async function initializeInIframe() {
    try {
        rrweb.record({
            emit(event) {
                window.parent.postMessage(event, '*');
            },
            recordCrossOriginIframes: true,
            recordCanvas: true,
            // inlineImages: true,
            collectFonts: true,
        });
        console.log("rrweb recording started in iframe.");
    } catch (error) {
        console.error("Error during iframe initialization:", error);
    }
}

document.addEventListener("DOMContentLoaded", () => {
    if (window.self !== window.top) {
        initializeInIframe();
    }
});
