document.addEventListener('DOMContentLoaded', function() {
    BenchmarkUtils.MultiTurnPage.init({
        pipelineType: 'rag_multi_turn',
        csvPrefix: 'rag-multiturn',
        buildFormData: function(formData) {
             const pipelineTypeInput = document.getElementById('pipeline-mode-pipeline');
             if (pipelineTypeInput) {
                 const val = pipelineTypeInput.value;
                 let reformStrategy = 'no_reform';
                 if (val.includes('reform')) reformStrategy = 'reform';
                 if (val.includes('no_reform')) reformStrategy = 'no_reform';
                 formData.append('reformulation_strategy', reformStrategy);
             }
        }
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