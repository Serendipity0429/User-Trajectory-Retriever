document.addEventListener('DOMContentLoaded', function() {
    // Setup UI handlers (toggles)
    BenchmarkSettings.setupConfigurationHandlers();

    // --- Configuration Management ---
    const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

    // Use centralized configuration handlers for LLM, RAG, and Search
    BenchmarkSettings.setupConfigurationActionHandlers(csrfToken, true, true);
});
