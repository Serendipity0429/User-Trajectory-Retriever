document.addEventListener('DOMContentLoaded', function() {
    BenchmarkUtils.MultiTurnPage.init({
        pipelineType: 'vanilla_llm_multi_turn',
        csvPrefix: 'vanilla-multiturn'
    });
});