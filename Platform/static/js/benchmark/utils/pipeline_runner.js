/**
 * Pipeline runner utilities
 * Handles pipeline execution, progress tracking, and UI updates
 */

window.BenchmarkPipelineRunner = window.BenchmarkPipelineRunner || {};

/**
 * Run a pipeline.
 * @param {object} options
 * @param {string} options.url - The URL to post to.
 * @param {FormData} options.formData - The form data to send.
 * @param {object} options.ui - UI elements: { runBtn, stopBtn, retryBtn, progressContainer, progressBar, resultsContainer, resultsBody, statusDiv, spinner }
 * @param {object} options.callbacks - { onData, onMeta, onComplete, onError }
 * @param {number} options.totalItems - Total items for progress calculation.
 * @param {number} options.initialProcessedCount - Initial count of processed items (for resuming).
 * @param {Array} options.itemsData - Array of items being processed.
 * @returns {AbortController} - The controller to abort the request.
 */
window.BenchmarkPipelineRunner.start = function(options) {
    let { totalItems, initialProcessedCount = 0 } = options;
    const { url, formData, ui, callbacks, itemsData } = options;

    // UI Reset
    BenchmarkHelpers.setUIState(ui, { runBtn: 'none', stopBtn: 'block', retryBtn: 'none', progressContainer: 'block' });
    if (ui.stopBtn) ui.stopBtn.disabled = false;
    if (ui.progressBar) {
        const initialProgress = (totalItems > 0) ? Math.round((initialProcessedCount / totalItems) * 100) : 0;
        ui.progressBar.style.width = `${initialProgress}%`;
        ui.progressBar.textContent = `${initialProgress}%`;
    }

    BenchmarkHelpers.setUIState(ui, { resultsContainer: 'block', spinner: 'inline-block' });
    if (ui.resultsBody) ui.resultsBody.innerHTML = '';
    if (ui.statusDiv) ui.statusDiv.textContent = 'Initializing pipeline...';

    BenchmarkSettings.toggleConfigurationInputs(true);

    const controller = new AbortController();
    const signal = controller.signal;
    controller.pipelineId = formData.get('pipeline_id');

    let processedCount = initialProcessedCount;

    const updateStatus = () => {
        if (ui.statusDiv) {
            let text = `Processed ${processedCount} / ${totalItems || '?'} items...`;
            ui.statusDiv.innerText = text;
        }
    };

    updateStatus();

    fetch(url, { method: 'POST', body: formData, signal: signal })
    .then(response => {
        BenchmarkHelpers.processStreamedResponse(
            response,
            (data) => { // onData
                if (data.is_meta) {
                    if (data.type === 'total_count') {
                        totalItems = data.count;
                        updateStatus();
                    }
                    if (callbacks.onMeta) callbacks.onMeta(data);
                    return;
                }

                processedCount++;
                if (callbacks.onData) callbacks.onData(data, processedCount);

                // Update Progress
                if (ui.progressBar && totalItems > 0) {
                    const progress = Math.round((processedCount / totalItems) * 100);
                    ui.progressBar.style.width = `${progress}%`;
                    ui.progressBar.textContent = `${progress}%`;
                }

                updateStatus();
            },
            () => { // onComplete
                BenchmarkSettings.toggleConfigurationInputs(false);
                BenchmarkHelpers.setUIState(ui, { runBtn: 'block', stopBtn: 'none', spinner: 'none' });
                if (ui.statusDiv) ui.statusDiv.textContent = 'Pipeline finished.';
                if (callbacks.onComplete) callbacks.onComplete(processedCount);
            },
            (error) => { // onError
                if (ui.statusDiv) ui.statusDiv.textContent = error.name === 'AbortError'
                    ? "Pipeline stopped by user." : `Error: ${error.message}`;
                if (error.name !== 'AbortError') console.error('Error during stream processing:', error);
                BenchmarkSettings.toggleConfigurationInputs(false);
                BenchmarkHelpers.setUIState(ui, { runBtn: 'block', stopBtn: 'none', spinner: 'none' });
                if (callbacks.onError) callbacks.onError(error);
            },
            signal
        );
    })
    .catch(error => {
        if (error.name === 'AbortError') {
            if (ui.statusDiv) ui.statusDiv.textContent = "Pipeline stopped by user.";
        } else {
            console.error('Error starting the pipeline:', error);
            alert('Failed to start the pipeline.');
            if (ui.statusDiv) ui.statusDiv.textContent = "Failed to start pipeline.";
        }
        BenchmarkSettings.toggleConfigurationInputs(false);
        BenchmarkHelpers.setUIState(ui, { runBtn: 'block', stopBtn: 'none', spinner: 'none' });
    });

    return controller;
};
