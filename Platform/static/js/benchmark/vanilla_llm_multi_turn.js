document.addEventListener('DOMContentLoaded', function() {
    BenchmarkUtils.MultiTurnPage.init({
        pipelineType: 'vanilla_llm_multi_turn',
        urls: {
            ...BenchmarkUrls, // Include common urls
            batchDeleteSessions: BenchmarkUrls.multiTurn.batchDeleteSessions,
            deleteSessionGroup: BenchmarkUrls.multiTurn.deleteSessionGroup,
            createSession: BenchmarkUrls.multiTurn.createSession,
            getSession: BenchmarkUrls.multiTurn.getSession,
            runTrial: BenchmarkUrls.multiTurn.runTrial,
            retrySession: BenchmarkUrls.multiTurn.retrySession,
            deleteSession: BenchmarkUrls.multiTurn.deleteSession,
            exportSession: BenchmarkUrls.multiTurn.exportSession,
            loadRun: BenchmarkUrls.vanillaLlmMultiTurn.loadRun,
            runPipeline: BenchmarkUrls.vanillaLlmMultiTurn.runPipeline,
            stopPipeline: BenchmarkUrls.vanillaLlmMultiTurn.stopPipeline,
        },
        csvPrefix: 'vanilla-multiturn'
    });
});