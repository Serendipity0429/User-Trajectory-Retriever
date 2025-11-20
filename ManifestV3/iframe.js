let isStartRequested = false;
let areChecksPassed = false;
let isRecording = false;

function startRecording() {
    if (isRecording || !isStartRequested || !areChecksPassed) return;

    isRecording = true;
    rrweb.record({
        emit(event) {
            window.parent.postMessage(event, '*');
        },
        recordCrossOriginIframes: true,
        recordCanvas: true,
        inlineStylesheet: true,
        inlineImages: true,
        collectFonts: true,
    });
    printDebug("iframe", "rrweb recording initialized in iframe.");
}

window.addEventListener('message', (event) => {
    if (event.data && event.data.type === 'start-recording') {
        isStartRequested = true;
        startRecording();
    }
});

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
            // printDebug("iframe", "No active task. Exiting iframe script.");
            return;
        }

        // Wait a bit for the iframe content to stabilize
        await new Promise(resolve => setTimeout(resolve, 500));

        areChecksPassed = true;
        startRecording();

    } catch (error) {
        console.error("Error during iframe initialization:", error);
    }
}

if (document.readyState === 'complete') {
    if (window.self !== window.top) {
        initializeInIframe();
    }
} else {
    window.addEventListener("load", () => {
        if (window.self !== window.top) {
            initializeInIframe();
        }
    });
}
