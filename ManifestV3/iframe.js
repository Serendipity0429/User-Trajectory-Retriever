async function initializeInIframe() {
    try {
        await initializeConfig();
        rrweb.record({
            emit(event) {
                window.parent.postMessage(event, '*');
            },
            recordCrossOriginIframes: true,
            recordCanvas: true,
            // inlineImages: true,         
            collectFonts: true,
        });
        printDebug("iframe", "rrweb recording initialized in iframe.");
    } catch (error) {
        console.error("Error during iframe initialization:", error);
    }
}

document.addEventListener("DOMContentLoaded", () => {
    if (window.self !== window.top) {
        initializeInIframe();
    }
});
