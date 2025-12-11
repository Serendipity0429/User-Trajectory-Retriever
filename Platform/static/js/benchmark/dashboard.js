document.addEventListener('DOMContentLoaded', function() {
    // Setup UI handlers (toggles)
    BenchmarkUtils.setupConfigurationHandlers();

    // --- Configuration Management ---
    const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

    // LLM Settings
    if (document.getElementById('test-connection-btn')) {
        document.getElementById('test-connection-btn').addEventListener('click', function() {
            const data = {
                llm_base_url: document.getElementById('llm_base_url').value,
                llm_api_key: document.getElementById('llm_api_key').value,
                llm_model: document.getElementById('llm_model').value
            };
            BenchmarkUtils.testConnection(window.benchmarkUrls.testLlmConnection, csrfToken, data, 'connection-status', 'test-connection-btn');
        });
    }

    if (document.getElementById('save-llm-settings-btn')) {
        document.getElementById('save-llm-settings-btn').addEventListener('click', function() {
            const data = {
                llm_base_url: document.getElementById('llm_base_url').value,
                llm_api_key: document.getElementById('llm_api_key').value,
                llm_model: document.getElementById('llm_model').value,
                max_retries: document.getElementById('max_retries') ? document.getElementById('max_retries').value : 3
            };
            BenchmarkUtils.saveSettings(window.benchmarkUrls.saveLlmSettings, csrfToken, data, 'save-llm-settings-btn');
        });
    }

    if (document.getElementById('restore-defaults-btn')) {
        document.getElementById('restore-defaults-btn').addEventListener('click', function() {
            BenchmarkUtils.restoreDefaults(window.benchmarkUrls.getLlmEnvVars, (data) => {
                if (data.llm_base_url) document.getElementById('llm_base_url').value = data.llm_base_url;
                if (data.llm_api_key) document.getElementById('llm_api_key').value = data.llm_api_key;
                if (data.llm_model) document.getElementById('llm_model').value = data.llm_model;
            });
        });
    }

    // RAG Settings
    if (document.getElementById('save-rag-settings-btn')) {
        document.getElementById('save-rag-settings-btn').addEventListener('click', function() {
            const data = {
                prompt_template: document.getElementById('rag_prompt_template').value
            };
            BenchmarkUtils.saveSettings(window.benchmarkUrls.saveRagSettings, csrfToken, data, 'save-rag-settings-btn');
        });
    }

    if (document.getElementById('restore-rag-defaults-btn')) {
        document.getElementById('restore-rag-defaults-btn').addEventListener('click', function() {
             fetch(window.benchmarkUrls.getDefaultRagPrompt)
                .then(res => res.json())
                .then(data => {
                    if(data.default_prompt) {
                         document.getElementById('rag_prompt_template').value = data.default_prompt;
                    }
                })
                .catch(err => console.error(err));
        });
    }

    // Search Settings
    if (document.getElementById('save-search-settings-btn')) {
        document.getElementById('save-search-settings-btn').addEventListener('click', function() {
            let searchProvider = 'serper'; // default
            const checkedProvider = document.querySelector('input[name="search_provider"]:checked');
            // Check dropdown for dashboard
            const dropdownProvider = document.getElementById('search_provider');
            
            if (checkedProvider) {
                 searchProvider = checkedProvider.value;
            } else if (dropdownProvider && dropdownProvider.tagName === 'SELECT') {
                 searchProvider = dropdownProvider.value;
            }


            const serperApiKey = document.getElementById('serper_api_key').value;
            const serperFetchFullContent = document.getElementById('serper_fetch_full_content') ? document.getElementById('serper_fetch_full_content').checked : false;
            
            const data = {
                search_provider: searchProvider,
                serper_api_key: serperApiKey,
                serper_fetch_full_content: serperFetchFullContent
            };
            BenchmarkUtils.saveSettings(window.benchmarkUrls.saveSearchSettings, csrfToken, data, 'save-search-settings-btn');
        });
    }
});
