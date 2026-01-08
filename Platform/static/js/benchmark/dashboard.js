document.addEventListener('DOMContentLoaded', function() {
    // Setup UI handlers (toggles)
    BenchmarkSettings.setupConfigurationHandlers();

    // Setup configuration action handlers for LLM, RAG, and Search
    BenchmarkSettings.setupConfigurationActionHandlers();
});
