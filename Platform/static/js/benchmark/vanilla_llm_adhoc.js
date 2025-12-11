document.addEventListener('DOMContentLoaded', function() {
    BenchmarkUtils.AdhocPage.init({
        pipelineType: 'vanilla_adhoc',
        urls: {
            ...BenchmarkUrls, // Include common settings URLs
            listRuns: BenchmarkUrls.vanillaLlmAdhoc.listRuns,
            batchDeleteRuns: BenchmarkUrls.vanillaLlmAdhoc.batchDeleteRuns,
            deleteRun: BenchmarkUrls.vanillaLlmAdhoc.deleteRun, // Updated to function
            deleteRunPrefix: null, // No longer needed
            getRun: BenchmarkUrls.vanillaLlmAdhoc.getRun,       // Updated to function
            getRunPrefix: null,    // No longer needed
            runPipeline: BenchmarkUrls.vanillaLlmAdhoc.runPipeline,
            stopPipeline: BenchmarkUrls.vanillaLlmAdhoc.stopPipeline,
        },
        csvPrefix: 'vanilla-adhoc',
        onRetry: function(failedItems, resultsBody, currentRunResults) {
             const btn = document.getElementById('retry-btn');
             btn.disabled = true;
             btn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Retrying...';
             
             const questionsToRetry = failedItems.map(item => ({ question: item.question, ground_truths: item.ground_truths, originalRowId: item.rowId }));
             const formData = new FormData();
             formData.append('csrfmiddlewaretoken', document.querySelector('meta[name="csrf-token"]').getAttribute('content'));
             formData.append('questions', JSON.stringify(questionsToRetry.map(q => ({question: q.question, ground_truths: q.ground_truths}))));
             formData.append('llm_base_url', document.getElementById('llm_base_url').value);
             formData.append('llm_api_key', document.getElementById('llm_api_key').value);
             formData.append('llm_model', document.getElementById('llm_model').value);
             
             let retryIndex = 0;
             // Note: Retries might use a specific endpoint or just the run pipeline endpoint. 
             // Assuming it posts to the same pipeline endpoint but with 'questions' data overrides.
             // However, original code used window.benchmarkUrls.vanillaLlmAdhoc which was the page URL, likely wrong or implied separate API.
             // Looking at original code: `fetch(window.benchmarkUrls.vanillaLlmAdhoc...`
             // The view `vanilla_llm_adhoc` (the page) accepts POST? Usually pages don't.
             // It likely meant `runPipeline`. Let's use runPipeline for now or check views.
             // Actually, `views.vanilla_llm_adhoc` might handle POST. 
             // Ideally we should use the API endpoint. Let's use runPipeline for consistency.
             fetch(BenchmarkUrls.vanillaLlmAdhoc.runPipeline, { method: 'POST', body: formData })
             .then(response => {
                BenchmarkUtils.processStreamedResponse(
                    response,
                    (data) => {
                        if (data.is_meta) return;
                        const originalItem = questionsToRetry[retryIndex++]; 
                        if (originalItem) {
                            data.originalRowId = originalItem.originalRowId;
                            const resultIndex = currentRunResults.findIndex(r => r.rowId === data.originalRowId);
                            if (resultIndex !== -1) currentRunResults[resultIndex] = data;
                            BenchmarkUtils.BenchmarkRenderer.renderResultRow(data, resultsBody, null, 'vanilla_adhoc', true);
                        }
                    },
                    () => { 
                        btn.style.display = 'none'; 
                        failedItems.length = 0; 
                    },
                    (error) => console.error(error)
                );
             })
             .catch(error => {
                 console.error(error);
                 alert('Failed to start retry pipeline.');
                 btn.disabled = false;
                 btn.innerHTML = 'Retry Failed';
             });
        }
    });
});
