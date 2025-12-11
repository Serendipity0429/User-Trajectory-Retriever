document.addEventListener('DOMContentLoaded', function() {
    BenchmarkUtils.MultiTurnPage.init({
        pipelineType: 'rag_multi_turn',
        urls: {
            batchDeleteSessions: '/benchmark/api/multi_turn/batch_delete_sessions/',
            deleteSessionGroup: (id) => `/benchmark/api/multi_turn/delete_session_group/${id}/`,
            createSession: window.benchmarkUrls.createSession,
            getSession: (id) => `/benchmark/api/multi_turn/get_session/${id}/`,
            runTrial: (id) => `/benchmark/api/multi_turn/run_trial/${id}/`,
            retrySession: (id) => `/benchmark/api/multi_turn/retry_session/${id}/`,
            deleteSession: (id) => `/benchmark/api/multi_turn/delete_session/${id}/`,
            exportSession: (id) => `/benchmark/api/multi_turn/export_session/${id}/`,
            loadRun: (id) => `/benchmark/api/multi_turn/load_rag_run/${id}/`,
            runPipeline: window.benchmarkUrls.runPipeline,
            stopPipeline: window.benchmarkUrls.stopRagMultiTurnPipeline,
        },
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