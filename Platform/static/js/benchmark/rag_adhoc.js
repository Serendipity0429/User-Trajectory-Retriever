document.addEventListener('DOMContentLoaded', function() {
    BenchmarkUtils.AdhocPage.init({
        pipelineType: 'rag_adhoc',
        urls: {
            listRuns: window.benchmarkUrls.listRuns,
            batchDeleteRuns: window.benchmarkUrls.batchDeleteRuns,
            deleteRunPrefix: '/benchmark/api/rag_adhoc/delete_run/',
            getRunPrefix: '/benchmark/api/rag_adhoc/get_run/',
            runPipeline: window.benchmarkUrls.runPipeline,
            stopPipeline: window.benchmarkUrls.stopPipeline,
        },
        csvPrefix: 'rag-adhoc',
        buildFormData: function(formData) {
            formData.append('rag_prompt_template', document.getElementById('rag_prompt_template').value);
        },
        onRetry: function() {
            alert("Retry logic not fully implemented for RAG yet.");
        }
    });

    // --- Web Search Test Logic ---
    const webSearchBtn = document.getElementById('test-web-search-btn');
    if (webSearchBtn) {
        webSearchBtn.addEventListener('click', function() {
            const query = document.getElementById('web-search-query').value.trim();
            if (!query) {
                alert('Please enter a search query.');
                return;
            }

            const btn = this;
            const originalHtml = btn.innerHTML;
            const resultsContainer = document.getElementById('web-search-results');
            const resultsList = document.getElementById('web-search-results-list');

            btn.disabled = true;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Searching...';
            resultsContainer.style.display = 'none';
            resultsList.innerHTML = '';

            const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

            fetch(window.benchmarkUrls.webSearch, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({ query: query })
            })
            .then(response => response.json())
            .then(data => {
                resultsContainer.style.display = 'block';
                if (data.error) {
                    BenchmarkUtils.BenchmarkRenderer.renderSearchError(resultsList, `Error: ${data.error}`);
                } else if (data.results && data.results.length > 0) {
                    BenchmarkUtils.BenchmarkRenderer.renderSearchResults(data.results, resultsList);
                } else {
                    BenchmarkUtils.BenchmarkRenderer.renderNoSearchResults(resultsList);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                resultsContainer.style.display = 'block';
                BenchmarkUtils.BenchmarkRenderer.renderSearchError(resultsList, `An error occurred: ${error.message}`);
            })
            .finally(() => {
                btn.disabled = false;
                btn.innerHTML = originalHtml;
            });
        });
    }
});