document.addEventListener('DOMContentLoaded', function() {
    BenchmarkUtils.MultiTurnPage.init({
        pipelineType: 'rag_multi_turn',
        csvPrefix: 'rag-multiturn'
    });

    // --- Search Results Modal Listener ---
    document.addEventListener('click', function(e) {
        if (e.target && e.target.closest('.view-search-results-btn')) {
            const btn = e.target.closest('.view-search-results-btn');
            try {
                const results = JSON.parse(decodeURIComponent(btn.dataset.results));
                const container = document.getElementById('modal-search-results-container');
                BenchmarkUtils.BenchmarkRenderer.renderModalSearchResults(results, container);
                const modal = new bootstrap.Modal(document.getElementById('searchResultsListModal'));
                modal.show();
            } catch (err) {
                console.error("Error opening results modal:", err);
                alert("Failed to load results details.");
            }
        }
    });
});