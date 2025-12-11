document.addEventListener('DOMContentLoaded', function() {
    BenchmarkUtils.MultiTurnPage.init({
        pipelineType: 'vanilla_llm_multi_turn',
        urls: {
            batchDeleteSessions: '/benchmark/api/multi_turn/batch_delete_sessions/',
            deleteSessionGroup: (id) => `/benchmark/api/multi_turn/delete_session_group/${id}/`,
            createSession: window.benchmarkUrls.createSession,
            getSession: (id) => `/benchmark/api/multi_turn/get_session/${id}/`,
            runTrial: (id) => `/benchmark/api/multi_turn/run_trial/${id}/`,
            retrySession: (id) => `/benchmark/api/multi_turn/retry_session/${id}/`,
            deleteSession: (id) => `/benchmark/api/multi_turn/delete_session/${id}/`,
            exportSession: (id) => `/benchmark/api/multi_turn/export_session/${id}/`,
            loadRun: (id) => `/benchmark/api/multi_turn/load_run/${id}/`,
            runPipeline: window.benchmarkUrls.runPipeline,
            stopPipeline: window.benchmarkUrls.stopVanillaLlmMultiTurnPipeline,
        },
        csvPrefix: 'vanilla-multiturn'
    });
});