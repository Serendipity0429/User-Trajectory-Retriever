async function initializeInIframe() {
    try {
        await initializeConfig();

        const login_response = await new Promise((resolve, reject) => {
            chrome.runtime.sendMessage({ command: "check_logging_status" }, (response) => {
                if (chrome.runtime.lastError) {
                    return reject(chrome.runtime.lastError);
                }
                resolve(response);
            });
        });

        if (!login_response || !login_response.log_status) {
            printDebug("iframe", "User is not logged in. Exiting iframe script.");
            return;
        }

        const task_response = await new Promise((resolve, reject) => {
            chrome.runtime.sendMessage({ command: "get_active_task" }, function (response) {
                if (chrome.runtime.lastError) {
                    console.error("Error checking task status in iframe:", chrome.runtime.lastError.message);
                    return reject(chrome.runtime.lastError);
                }
                resolve(response);
            });
        });

        if (!task_response || !task_response.is_task_active) {
            printDebug("iframe", "No active task. Exiting iframe script.");
            return;
        }

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
