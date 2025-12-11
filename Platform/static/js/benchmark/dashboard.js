document.addEventListener('DOMContentLoaded', function() {
    // Setup UI handlers (toggles)
    BenchmarkUtils.setupConfigurationHandlers();

    // --- Configuration Management ---
    const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

    // Use centralized configuration handlers for LLM, RAG, and Search
    BenchmarkUtils.setupConfigurationActionHandlers(csrfToken, true, true);
});
