// Centralized URL configuration
const API_PREFIX = '/benchmark/api';

const BenchmarkUrls = {
    // LLM & Settings
    saveLlmSettings: `${API_PREFIX}/save_llm_settings/`,
    getDefaultSettings: `${API_PREFIX}/get_default_settings/`,
    testLlmConnection: `${API_PREFIX}/test_llm_connection/`,
    
    // RAG & Search Settings
    saveRagSettings: `${API_PREFIX}/save_rag_settings/`,
    saveSearchSettings: `${API_PREFIX}/save_search_settings/`,
    getDefaultRagPrompt: `${API_PREFIX}/rag_adhoc/get_default_prompt/`,
    webSearch: `${API_PREFIX}/web_search/`,

    // Datasets
    datasets: {
        sync: `${API_PREFIX}/datasets/sync/`,
        upload: `${API_PREFIX}/datasets/upload/`,
        delete: (id) => `${API_PREFIX}/datasets/delete/${id}/`,
        activate: (id) => `${API_PREFIX}/datasets/activate/${id}/`
    },

    // Ad-hoc: Vanilla LLM
    vanillaLlmAdhoc: {
        listRuns: `${API_PREFIX}/vanilla_llm_adhoc/list_runs/`,
        getRun: (id) => `${API_PREFIX}/vanilla_llm_adhoc/get_run/${id}/`,
        deleteRun: (id) => `${API_PREFIX}/vanilla_llm_adhoc/delete_run/${id}/`,
        batchDeleteRuns: `${API_PREFIX}/vanilla_llm_adhoc/batch_delete_runs/`,
        runPipeline: `${API_PREFIX}/run_vanilla_llm_adhoc_pipeline/`,
        stopPipeline: `${API_PREFIX}/stop_vanilla_llm_adhoc_pipeline/`
    },

    // Ad-hoc: RAG
    ragAdhoc: {
        listRuns: `${API_PREFIX}/rag_adhoc/list_runs/`,
        getRun: (id) => `${API_PREFIX}/rag_adhoc/get_run/${id}/`,
        deleteRun: (id) => `${API_PREFIX}/rag_adhoc/delete_run/${id}/`,
        batchDeleteRuns: `${API_PREFIX}/rag_adhoc/batch_delete_runs/`,
        runPipeline: `${API_PREFIX}/run_rag_adhoc_pipeline/`,
        stopPipeline: `${API_PREFIX}/stop_rag_adhoc_pipeline/`
    },

    // Multi-turn Common
    multiTurn: {
        createSession: `${API_PREFIX}/multi_turn/create_session/`,
        createSessionGroup: `${API_PREFIX}/multi_turn/create_session_group/`,
        batchDeleteSessions: `${API_PREFIX}/multi_turn/batch_delete_sessions/`,
        deleteSessionGroup: (id) => `${API_PREFIX}/multi_turn/delete_session_group/${id}/`,
        getSession: (id) => `${API_PREFIX}/multi_turn/get_session/${id}/`,
        runTrial: (id) => `${API_PREFIX}/multi_turn/run_trial/${id}/`,
        retrySession: (id) => `${API_PREFIX}/multi_turn/retry_session/${id}/`,
        deleteSession: (id) => `${API_PREFIX}/multi_turn/delete_session/${id}/`,
        exportSession: (id) => `${API_PREFIX}/multi_turn/export_session/${id}/`,
    },

    // Multi-turn: Vanilla LLM
    vanillaLlmMultiTurn: {
        loadRun: (id) => `${API_PREFIX}/multi_turn/load_run/${id}/`,
        runPipeline: `${API_PREFIX}/run_vanilla_llm_multi_turn_pipeline/`,
        stopPipeline: `${API_PREFIX}/stop_vanilla_llm_multi_turn_pipeline/`
    },

    // Multi-turn: RAG
    ragMultiTurn: {
        loadRun: (id) => `${API_PREFIX}/multi_turn/load_rag_run/${id}/`,
        runPipeline: `${API_PREFIX}/run_rag_multi_turn_pipeline/`,
        stopPipeline: `${API_PREFIX}/stop_rag_multi_turn_pipeline/`
    },
    
    // Multi-turn: Vanilla Agent
    vanillaAgent: {
        loadRun: (id) => `${API_PREFIX}/multi_turn/load_agent_run/${id}/`,
        runPipeline: `${API_PREFIX}/run_vanilla_agent_pipeline/`,
        stopPipeline: `${API_PREFIX}/stop_vanilla_agent_pipeline/`
    },
    
    // Multi-turn: Browser Agent
    browserAgent: {
        loadRun: (id) => `${API_PREFIX}/multi_turn/load_agent_run/${id}/`, // Share loadRun for now as structure is same
        runPipeline: `${API_PREFIX}/run_browser_agent_pipeline/`,
        stopPipeline: `${API_PREFIX}/stop_browser_agent_pipeline/`
    }
};

const BenchmarkState = {
    config: {
        lastSavedBaseUrl: '',
        settingsInitialState: {}, // Stores the initial state of settings for change detection
        hasUnsavedChanges: false,
    },
    activeRun: {
        id: null,
        type: null, // 'vanilla_adhoc', 'rag_adhoc', 'multi_turn'
        data: null
    },
    ui: {}
};

const BenchmarkComponents = {
    createBadge: function(text, isCorrect, showNAForNull = false) {
        const span = document.createElement('span');
        span.className = 'badge';
        if (isCorrect === null && showNAForNull) {
            span.classList.add('bg-secondary');
            span.textContent = 'N/A';
        } else if (isCorrect) {
            span.classList.add('bg-success');
            span.textContent = text || 'Correct';
        } else {
            span.classList.add('bg-danger');
            span.textContent = text || 'Incorrect';
        }
        return span;
    },

    createIcon: function(className) {
        const i = document.createElement('i');
        i.className = className;
        return i;
    },

    createTextElement: function(tagName, className, textContent, title = '') {
        const element = document.createElement(tagName);
        element.className = className;
        element.textContent = textContent;
        if (title) {
            element.title = title;
        }
        return element;
    },

    createLink: function(href, className, textContent, target = '_self') {
        const link = document.createElement('a');
        link.href = href;
        link.className = className;
        link.textContent = textContent;
        link.target = target;
        return link;
    }
};

const BenchmarkUtils = {
    /**
     * Test the LLM connection.
     * @param {string} url - The URL to the test connection view.
     * @param {string} csrfToken - The CSRF token.
     * @param {object} data - The data to send (llm_base_url, llm_api_key).
     * @param {string} resultDivId - The ID of the div to display results.
     * @param {string} btnId - The ID of the test button.
     */
    testConnection: function(url, csrfToken, data, resultDivId, btnId) {
        const resultDiv = document.getElementById(resultDivId);
        const btn = document.getElementById(btnId);
        const originalText = btn.innerHTML;
        
        resultDiv.innerHTML = '';
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Testing...';

        fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify(data)
        })
        .then(response => response.json().then(data => ({status: response.status, body: data})))
        .then(({status, body}) => {
            if (status === 200) {
                resultDiv.innerHTML = `<span class="text-success small fw-semibold"><i class="bi bi-check-circle-fill me-1"></i>${body.message}</span>`;
                
                // If models are returned, enable datalist for the input
                if (body.models && Array.isArray(body.models) && body.models.length > 0) {
                    let modelInput = document.getElementById('llm_model');
                    if (modelInput) {
                        // If it was previously converted to select (by old logic), revert to input
                        if (modelInput.tagName === 'SELECT') {
                            const input = document.createElement('input');
                            input.type = 'text';
                            input.id = modelInput.id;
                            input.className = modelInput.className.replace('form-select', 'form-control');
                            input.value = modelInput.value;
                            modelInput.parentNode.replaceChild(input, modelInput);
                            modelInput = input;
                        }

                        const datalistId = 'llm_model_datalist';
                        let datalist = document.getElementById(datalistId);
                        
                        if (!datalist) {
                            datalist = document.createElement('datalist');
                            datalist.id = datalistId;
                            modelInput.parentNode.appendChild(datalist);
                            modelInput.setAttribute('list', datalistId);
                        } else {
                            datalist.innerHTML = '';
                        }
                        
                        // Sort models
                        body.models.sort();

                        // Populate options
                        body.models.forEach(modelName => {
                            const option = document.createElement('option');
                            option.value = modelName;
                            datalist.appendChild(option);
                        });
                    }
                }
            } else {
                resultDiv.innerHTML = `<span class="text-danger small fw-semibold"><i class="bi bi-exclamation-circle-fill me-1"></i>${body.error || 'An error occurred while testing the connection.'}</span>`;
            }
        })
        .catch(error => {
            resultDiv.innerHTML = `<span class="text-danger small fw-semibold"><i class="bi bi-exclamation-circle-fill me-1"></i>A network error occurred.</span>`;
            console.error('Error:', error);
        })
        .finally(() => {
            btn.disabled = false;
            btn.innerHTML = originalText;
        });
    },

    /**
     * Save settings to the server.
     * @param {string} url - The URL to the save settings view.
     * @param {string} csrfToken - The CSRF token.
     * @param {object} data - The settings data to save.
     * @param {string} btnId - The ID of the save button (to show feedback).
     */
    saveSettings: function(url, csrfToken, data, btnId) {
        fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify(data)
        })
        .then(response => response.json())
        .then(resData => {
            if (resData.status === 'ok') {
                const btn = document.getElementById(btnId);
                const originalText = btn.innerHTML;
                const originalClass = btn.className;
                
                btn.innerHTML = '<i class="bi bi-check-lg me-1"></i> Saved!';
                btn.classList.remove('btn-outline-primary', 'btn-primary', 'btn-outline-secondary');
                btn.classList.add('btn-success');
                
                setTimeout(() => {
                    btn.innerHTML = originalText;
                    btn.className = originalClass; 
                }, 1500);
                BenchmarkState.config.hasUnsavedChanges = false; // Reset flag on successful save
                BenchmarkUtils.saveInitialSettings(); // Update initial state
            } else {
                alert('Error saving settings: ' + (resData.message || 'Unknown error'));
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('A network error occurred while saving settings.');
        });
    },

    /**
     * Captures the current state of settings inputs.
     */
    saveInitialSettings: function() {
        BenchmarkState.config.settingsInitialState = {
            llm_base_url: document.getElementById('llm_base_url') ? document.getElementById('llm_base_url').value : '',
            llm_api_key: document.getElementById('llm_api_key') ? document.getElementById('llm_api_key').value : '',
            llm_model: document.getElementById('llm_model') ? document.getElementById('llm_model').value : '',
            max_retries: document.getElementById('max_retries') ? document.getElementById('max_retries').value : '',
            allow_reasoning: document.getElementById('allow_reasoning') ? document.getElementById('allow_reasoning').checked : false,
            temperature: document.getElementById('temperature') ? document.getElementById('temperature').value : '',
            top_p: document.getElementById('top_p') ? document.getElementById('top_p').value : '',
            max_tokens: document.getElementById('max_tokens') ? document.getElementById('max_tokens').value : '',
            
            rag_prompt_template: document.getElementById('rag_prompt_template') ? document.getElementById('rag_prompt_template').value : '',
            
            search_provider: document.getElementById('search_provider') ? document.getElementById('search_provider').value : '',
            search_limit: document.getElementById('search_limit') ? document.getElementById('search_limit').value : '',
            serper_api_key: document.getElementById('serper_api_key') ? document.getElementById('serper_api_key').value : '',
            serper_fetch_full_content: document.getElementById('serper_fetch_full_content') ? document.getElementById('serper_fetch_full_content').checked : false,
        };
        BenchmarkState.config.hasUnsavedChanges = false;
        if(document.getElementById('unsaved-changes-alert')) document.getElementById('unsaved-changes-alert').style.display = 'none';
    },

    /**
     * Checks for unsaved changes by comparing current values with initial state.
     */
    checkUnsavedChanges: function() {
        const initial = BenchmarkState.config.settingsInitialState || {};
        const current = {
            llm_base_url: document.getElementById('llm_base_url') ? document.getElementById('llm_base_url').value : '',
            llm_api_key: document.getElementById('llm_api_key') ? document.getElementById('llm_api_key').value : '',
            llm_model: document.getElementById('llm_model') ? document.getElementById('llm_model').value : '',
            max_retries: document.getElementById('max_retries') ? document.getElementById('max_retries').value : '',
            allow_reasoning: document.getElementById('allow_reasoning') ? document.getElementById('allow_reasoning').checked : false,
            temperature: document.getElementById('temperature') ? document.getElementById('temperature').value : '',
            top_p: document.getElementById('top_p') ? document.getElementById('top_p').value : '',
            max_tokens: document.getElementById('max_tokens') ? document.getElementById('max_tokens').value : '',
            
            rag_prompt_template: document.getElementById('rag_prompt_template') ? document.getElementById('rag_prompt_template').value : '',
            
            search_provider: document.getElementById('search_provider') ? document.getElementById('search_provider').value : '',
            search_limit: document.getElementById('search_limit') ? document.getElementById('search_limit').value : '',
            serper_api_key: document.getElementById('serper_api_key') ? document.getElementById('serper_api_key').value : '',
            serper_fetch_full_content: document.getElementById('serper_fetch_full_content') ? document.getElementById('serper_fetch_full_content').checked : false,
        };

        let hasChanges = false;
        for (const key in current) {
            // Loose equality to handle string vs number differences (e.g. "3" vs 3)
            if (current[key] != initial[key]) {
                hasChanges = true;
                break;
            }
        }

        BenchmarkState.config.hasUnsavedChanges = hasChanges;
        const alertEl = document.getElementById('unsaved-changes-alert');
        if (alertEl) {
            alertEl.style.display = hasChanges ? 'block' : 'none';
        }
    },

    /**
     * Restore default settings from .env via server.
     */
    restoreDefaults: function() {
        fetch(BenchmarkUrls.getDefaultSettings)
            .then(response => response.json())
            .then(data => {
                if(data.error) {
                    alert('Error loading default settings: ' + data.error);
                } else {
                    // Apply LLM settings
                    if (document.getElementById('llm_base_url') && data.llm_base_url) document.getElementById('llm_base_url').value = data.llm_base_url;
                    if (document.getElementById('llm_api_key') && data.llm_api_key) document.getElementById('llm_api_key').value = data.llm_api_key;
                    if (document.getElementById('llm_model') && data.llm_model) document.getElementById('llm_model').value = data.llm_model;
                    // Add advanced LLM settings
                    if (document.getElementById('max_retries') && data.max_retries) document.getElementById('max_retries').value = data.max_retries;
                    if (document.getElementById('allow_reasoning') && data.allow_reasoning !== undefined) document.getElementById('allow_reasoning').checked = data.allow_reasoning;
                    if (document.getElementById('temperature') && data.temperature !== undefined) document.getElementById('temperature').value = data.temperature;
                    if (document.getElementById('top_p') && data.top_p !== undefined) document.getElementById('top_p').value = data.top_p;
                    if (document.getElementById('max_tokens') && data.max_tokens !== undefined) document.getElementById('max_tokens').value = data.max_tokens;


                    // Apply RAG settings
                    if (document.getElementById('rag_prompt_template') && data.rag_prompt_template) document.getElementById('rag_prompt_template').value = data.rag_prompt_template;
                    
                    // Apply Search settings
                    if (document.getElementById('search_provider') && data.search_provider) {
                        document.getElementById('search_provider').value = data.search_provider;
                        // Trigger change to update UI for serper_api_key container visibility
                        document.getElementById('search_provider').dispatchEvent(new Event('change'));
                    }
                    if (document.getElementById('search_limit') && data.search_limit) document.getElementById('search_limit').value = data.search_limit;
                    if (document.getElementById('serper_api_key') && data.serper_api_key) document.getElementById('serper_api_key').value = data.serper_api_key;
                    if (document.getElementById('serper_fetch_full_content') && data.serper_fetch_full_content !== undefined) document.getElementById('serper_fetch_full_content').checked = data.serper_fetch_full_content;

                    // Update lastSavedBaseUrl and test connection
                    if (document.getElementById('llm_base_url')) {
                        BenchmarkState.config.lastSavedBaseUrl = document.getElementById('llm_base_url').value;
                        BenchmarkUtils.testConnection(BenchmarkUrls.testLlmConnection, document.querySelector('meta[name="csrf-token"]').getAttribute('content'), {
                            llm_base_url: document.getElementById('llm_base_url').value,
                            llm_api_key: document.getElementById('llm_api_key').value,
                            llm_model: document.getElementById('llm_model').value
                        }, 'test-connection-result', 'test-connection-btn');
                    }
                    BenchmarkUtils.saveInitialSettings(); // Update initial state after restoring defaults
                }
            })
            .catch(error => {
                console.error('Error restoring defaults:', error);
                alert('Failed to restore defaults.');
            });
    },

    /**
     * Setup common configuration UI handlers (toggles, visibility).
     */
    setupConfigurationHandlers: function() {
        // Toggle LLM API Key Visibility
        const llmApiKey = document.getElementById('llm_api_key');
        const toggleLlmKeyBtn = document.getElementById('toggle-llm-key-visibility');
        if (toggleLlmKeyBtn && llmApiKey) {
            toggleLlmKeyBtn.addEventListener('click', function() {
                const type = llmApiKey.getAttribute('type') === 'password' ? 'text' : 'password';
                llmApiKey.setAttribute('type', type);
                this.querySelector('i').classList.toggle('bi-eye');
                this.querySelector('i').classList.toggle('bi-eye-slash');
            });
        }

        // Toggle Serper API Key Visibility
        const serperApiKey = document.getElementById('serper_api_key');
        const toggleSerperKeyBtn = document.getElementById('toggle-serper-key-visibility');
        if (toggleSerperKeyBtn && serperApiKey) {
            toggleSerperKeyBtn.addEventListener('click', function() {
                const type = serperApiKey.getAttribute('type') === 'password' ? 'text' : 'password';
                serperApiKey.setAttribute('type', type);
                this.querySelector('i').classList.toggle('bi-eye');
                this.querySelector('i').classList.toggle('bi-eye-slash');
            });
        }

        // Search Provider Toggle
        const searchProvider = document.getElementById('search_provider');
        const serperApiKeyContainer = document.getElementById('serper_api_key_container');
        if (searchProvider && serperApiKeyContainer) {
            searchProvider.addEventListener('change', function() {
                if (this.value === 'serper') {
                    serperApiKeyContainer.style.display = 'block';
                } else {
                    serperApiKeyContainer.style.display = 'none';
                }
            });
            // Trigger once on load
            searchProvider.dispatchEvent(new Event('change'));
        }
    },

    /**
     * Validates the search limit input.
     * @returns {boolean} True if valid, false otherwise.
     */
    validateSearchLimit: function() {
        const searchLimitInput = document.getElementById('search_limit');
        const feedbackDiv = document.getElementById('search-limit-feedback');
        
        if (!searchLimitInput || !feedbackDiv) return true;

        const value = parseInt(searchLimitInput.value, 10);
        
        if (isNaN(value) || value < 1 || value > 10) {
            searchLimitInput.classList.add('is-invalid');
            feedbackDiv.textContent = 'Retrieved Doc Count must be between 1 and 10.';
            feedbackDiv.style.display = 'block';
            return false;
        } else {
            searchLimitInput.classList.remove('is-invalid');
            feedbackDiv.style.display = 'none';
            return true;
        }
    },

    /**
     * Setup event handlers for configuration actions.
     */
    setupConfigurationActionHandlers: function(csrfToken, includeRag = false, includeSearch = false) {
        // LLM Settings
        const testConnection = function() {
            const data = {
                llm_base_url: document.getElementById('llm_base_url').value,
                llm_api_key: document.getElementById('llm_api_key').value,
                llm_model: document.getElementById('llm_model').value
            };
            BenchmarkUtils.testConnection(BenchmarkUrls.testLlmConnection, csrfToken, data, 'test-connection-result', 'test-connection-btn');
        };

        if (document.getElementById('test-connection-btn')) {
            document.getElementById('test-connection-btn').addEventListener('click', testConnection);
        }
        
        // Trigger on page load
        testConnection(); 
        BenchmarkUtils.saveInitialSettings();

        // Search Limit Validation
        const searchLimitInput = document.getElementById('search_limit');
        if (searchLimitInput) {
            searchLimitInput.addEventListener('input', BenchmarkUtils.validateSearchLimit);
            searchLimitInput.addEventListener('change', BenchmarkUtils.validateSearchLimit);
        }

        // Check unsaved changes on input
        const checkChanges = () => BenchmarkUtils.checkUnsavedChanges();
        const settingsIds = [
            'llm_base_url', 'llm_model', 'llm_api_key', 'max_retries', 'allow_reasoning',
            'temperature', 'top_p', 'max_tokens',
            'rag_prompt_template',
            'search_provider', 'search_limit', 'serper_api_key', 'serper_fetch_full_content'
        ];
        settingsIds.forEach(id => {
            const el = document.getElementById(id);
            if(el) {
                el.addEventListener('input', checkChanges);
                el.addEventListener('change', checkChanges);
            }
        });

        // Global Reset Button
        const globalRestoreBtn = document.getElementById('global-restore-btn');
        if (globalRestoreBtn) {
            globalRestoreBtn.addEventListener('click', function() {
                if(confirm('Are you sure you want to restore ALL settings to their defaults?')) {
                     BenchmarkUtils.restoreDefaults();
                }
            });
        }

        // Global Save All Handler
        if (document.getElementById('save-all-settings-btn')) {
            document.getElementById('save-all-settings-btn').addEventListener('click', function() {
                if (!BenchmarkUtils.validateSearchLimit()) {
                    alert('Please correct the errors in the Search Settings tab.');
                    return;
                }

                const btn = this;
                const originalText = btn.innerHTML;
                btn.disabled = true;
                btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Saving...';

                const promises = [];

                // LLM
                const llmData = {
                    llm_base_url: document.getElementById('llm_base_url').value,
                    llm_api_key: document.getElementById('llm_api_key').value,
                    llm_model: document.getElementById('llm_model').value,
                    max_retries: document.getElementById('max_retries') ? document.getElementById('max_retries').value : 3,
                    allow_reasoning: document.getElementById('allow_reasoning') ? document.getElementById('allow_reasoning').checked : false,
                    temperature: document.getElementById('temperature') ? document.getElementById('temperature').value : 0.0,
                    top_p: document.getElementById('top_p') ? document.getElementById('top_p').value : 1.0,
                    max_tokens: document.getElementById('max_tokens') ? document.getElementById('max_tokens').value : null
                };
                promises.push(fetch(BenchmarkUrls.saveLlmSettings, {
                    method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrfToken},
                    body: JSON.stringify(llmData)
                }).then(r => r.json()));

                // Search
                if (document.getElementById('search_provider')) {
                    let searchProvider = document.getElementById('search_provider').value;
                    const searchData = {
                        search_provider: searchProvider,
                        search_limit: document.getElementById('search_limit') ? document.getElementById('search_limit').value : 5,
                        serper_api_key: document.getElementById('serper_api_key').value,
                        serper_fetch_full_content: document.getElementById('serper_fetch_full_content') ? document.getElementById('serper_fetch_full_content').checked : false
                    };
                    promises.push(fetch(BenchmarkUrls.saveSearchSettings, {
                        method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrfToken},
                        body: JSON.stringify(searchData)
                    }).then(r => r.json()));
                }

                // RAG
                if (document.getElementById('rag_prompt_template')) {
                     const ragData = { prompt_template: document.getElementById('rag_prompt_template').value };
                     promises.push(fetch(BenchmarkUrls.saveRagSettings, {
                        method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrfToken},
                        body: JSON.stringify(ragData)
                    }).then(r => r.json()));
                }

                Promise.all(promises).then(results => {
                    const allOk = results.every(r => r.status === 'ok');
                    if (allOk) {
                        btn.innerHTML = '<i class="bi bi-check-lg me-1"></i> Saved!';
                        btn.classList.remove('btn-primary');
                        btn.classList.add('btn-success');
                        BenchmarkState.config.hasUnsavedChanges = false;
                        BenchmarkUtils.saveInitialSettings();
                        if(document.getElementById('unsaved-changes-alert')) document.getElementById('unsaved-changes-alert').style.display = 'none';

                        setTimeout(() => {
                            btn.innerHTML = originalText;
                            btn.classList.remove('btn-success');
                            btn.classList.add('btn-primary');
                            btn.disabled = false;
                        }, 1500);
                        
                        // Re-test connection if base URL changed
                        if (llmData.llm_base_url !== BenchmarkState.config.lastSavedBaseUrl) {
                            testConnection();
                            BenchmarkState.config.lastSavedBaseUrl = llmData.llm_base_url;
                        }

                    } else {
                        alert('Some settings failed to save.');
                        btn.disabled = false;
                        btn.innerHTML = originalText;
                    }
                }).catch(err => {
                    console.error(err);
                    alert('Network error saving settings.');
                    btn.disabled = false;
                    btn.innerHTML = originalText;
                });
            });
        }

        // Handle Modal Close
        const settingsModal = document.getElementById('settingsModal');
        if (settingsModal) {
            settingsModal.addEventListener('hide.bs.modal', function(e) {
                if (BenchmarkState.config.hasUnsavedChanges) {
                    if (!confirm('You have unsaved changes. Are you sure you want to close without saving?')) {
                        e.preventDefault();
                    }
                }
            });
        }


    },

    /**
     * Enable or disable configuration inputs.
     * @param {boolean} disabled - Whether to disable the inputs.
     */
    toggleConfigurationInputs: function(disabled) {
        const inputs = document.querySelectorAll('#settingsModal input, #settingsModal select, #settingsModal textarea, #dataset-selector');
        inputs.forEach(input => {
            input.disabled = disabled;
        });
        const saveBtn = document.getElementById('save-all-settings-btn');
        if (saveBtn) saveBtn.disabled = disabled;
        
        const settingsBtn = document.querySelector('button[data-bs-target="#settingsModal"]');
        if (settingsBtn) settingsBtn.disabled = disabled;
    },

    /**
     * Generate a UUID.
     * @returns {string} The UUID.
     */
    generateUUID: function() {
        if (crypto.randomUUID) {
            return crypto.randomUUID();
        }
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
            var r = Math.random() * 16 | 0, v = c == 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });
    },

    /**
     * Stop a pipeline.
     * @param {string} url - The URL to the stop pipeline view.
     * @param {string} csrfToken - The CSRF token.
     * @param {string} pipelineId - The ID of the pipeline to stop.
     */
    stopPipeline: function(url, csrfToken, pipelineId) {
        if (!pipelineId) return;
        
        const data = JSON.stringify({ pipeline_id: pipelineId });

        // Prefer fetch with keepalive
        fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: data,
            keepalive: true
        }).catch(e => console.error("Stop request failed", e));
    },

    /**
     * Sets up batch selection logic for a list of items with checkboxes.
     * @param {string} listContainerId - ID of the container holding all selectable items.
     * @param {string} selectAllCheckboxId - ID of the 'Select All' checkbox.
     * @param {string} itemCheckboxClass - Class name for individual item checkboxes.
     * @param {string} deleteButtonId - ID of the button that performs batch deletion.
     * @param {function} deleteActionCallback - Function to call when the delete button is clicked. Receives an array of selected item IDs and selected group IDs.
     * @param {string} [itemGroupIdClass] - Optional: Class name for item group checkboxes (e.g., for multi-turn sessions).
     */
    setupBatchSelection: function(listContainerId, selectAllCheckboxId, itemCheckboxClass, deleteButtonId, deleteActionCallback, itemGroupIdClass = null) {
        const listContainer = document.getElementById(listContainerId);
        const deleteSelectedBtn = document.getElementById(deleteButtonId);

        if (!listContainer || !deleteSelectedBtn) return;

        const getSelectAllCheckbox = () => document.getElementById(selectAllCheckboxId);
        const getCheckboxes = () => listContainer.querySelectorAll(`.${itemCheckboxClass}`);
        const getGroupCheckboxes = () => itemGroupIdClass ? listContainer.querySelectorAll(`.${itemGroupIdClass}`) : [];

        const toggleDeleteButton = () => {
            const anyItemChecked = Array.from(getCheckboxes()).some(cb => cb.checked);
            const anyGroupChecked = Array.from(getGroupCheckboxes()).some(cb => cb.checked);
            const anyChecked = anyItemChecked || anyGroupChecked;
            deleteSelectedBtn.style.display = anyChecked ? 'inline-block' : 'none';

            const selectAllCheckbox = getSelectAllCheckbox();
            if (selectAllCheckbox) {
                const allCheckboxes = Array.from(getCheckboxes()).concat(Array.from(getGroupCheckboxes()));
                const allChecked = allCheckboxes.length > 0 && allCheckboxes.every(cb => cb.checked);
                selectAllCheckbox.checked = anyChecked && allChecked; 
            }
        };

        const selectAllHandler = (e) => {
            const isChecked = e.target.checked;
            getCheckboxes().forEach(checkbox => checkbox.checked = isChecked);
            getGroupCheckboxes().forEach(checkbox => checkbox.checked = isChecked);
            toggleDeleteButton();
        };

        let currentSelectAllCheckbox = getSelectAllCheckbox();
        if (currentSelectAllCheckbox) {
            currentSelectAllCheckbox.addEventListener('change', selectAllHandler);
        }
        
        listContainer.addEventListener('change', function(e) {
            if (e.target.classList.contains(itemCheckboxClass) || (itemGroupIdClass && e.target.classList.contains(itemGroupIdClass))) {
                toggleDeleteButton();
            }
        });

        deleteSelectedBtn.addEventListener('click', function() {
            const selectedItemIds = Array.from(getCheckboxes())
                .filter(cb => cb.checked)
                .map(cb => cb.dataset.runId || cb.dataset.sessionId); 

            const selectedGroupIds = Array.from(getGroupCheckboxes())
                .filter(cb => cb.checked)
                .map(cb => cb.dataset.groupId);

            if (selectedItemIds.length === 0 && selectedGroupIds.length === 0) {
                return;
            }

            deleteActionCallback(selectedItemIds, selectedGroupIds);
        });

        toggleDeleteButton();

        const observer = new MutationObserver(() => {
            const allCheckboxes = Array.from(getCheckboxes()).concat(Array.from(getGroupCheckboxes()));
            
            // Check if Select All checkbox has appeared or changed
            const newSelectAllCheckbox = getSelectAllCheckbox();
            if (newSelectAllCheckbox && newSelectAllCheckbox !== currentSelectAllCheckbox) {
                newSelectAllCheckbox.addEventListener('change', selectAllHandler);
                currentSelectAllCheckbox = newSelectAllCheckbox;
            }

            if (currentSelectAllCheckbox) {
                const selectAllContainer = currentSelectAllCheckbox.closest('.list-group-item.bg-light');
                if (allCheckboxes.length > 0) {
                    if (selectAllContainer) selectAllContainer.style.display = 'flex';
                } else {
                    if (selectAllContainer) selectAllContainer.style.display = 'none';
                }
            }
            toggleDeleteButton();
        });
        observer.observe(listContainer, { childList: true, subtree: true });
    },

    /**
     * Load saved runs and populate the list.
     * @param {string} listUrl - URL to list runs.
     * @param {function} loadRunCallback - Function to call when a run is clicked.
     * @param {function} deleteRunCallback - Function to call when delete is clicked.
     * @param {string} listId - ID of the list element.
     * @param {string} noRunsId - ID of the no runs message element.
     * @param {boolean} enableSelection - Whether to render checkboxes for batch selection.
     * @param {function} onSelectionChange - Callback when selection changes (checkbox clicked).
     */
    loadSavedRuns: function(listUrl, loadRunCallback, deleteRunCallback, listId = 'saved-runs-list', noRunsId = 'no-runs-message', enableSelection = false, onSelectionChange = null) {
        const savedRunsList = document.getElementById(listId);
        const noRunsMessage = document.getElementById(noRunsId);
        savedRunsList.innerHTML = ''; 

        fetch(listUrl)
            .then(response => response.json())
            .then(data => {
                if (data.runs && data.runs.length > 0) {
                    noRunsMessage.style.display = 'none';
                    savedRunsList.style.display = 'block';

                    // Add Select All Container if enabled
                    if (enableSelection) {
                        const selectAllContainer = document.createElement('div');
                        selectAllContainer.className = 'list-group-item bg-light d-flex align-items-center';
                        selectAllContainer.innerHTML = `
                            <input class="form-check-input me-3" type="checkbox" id="select-all-checkbox">
                            <label class="form-check-label fw-bold" for="select-all-checkbox">Select All</label>
                        `;
                        savedRunsList.appendChild(selectAllContainer);
                    }

                    data.runs.forEach(run => {
                        const runItem = document.createElement('div');
                        runItem.className = 'list-group-item list-group-item-action d-flex align-items-center';
                        
                        // Checkbox (if enabled)
                        if (enableSelection) {
                            const checkbox = document.createElement('input');
                            checkbox.type = 'checkbox';
                            checkbox.className = 'form-check-input me-3 run-checkbox';
                            checkbox.value = run.id;
                            checkbox.dataset.runId = run.id;
                            checkbox.onclick = (e) => {
                                e.stopPropagation();
                                if (onSelectionChange) onSelectionChange();
                            };
                            runItem.appendChild(checkbox);
                        }

                        const runNameContainer = document.createElement('div');
                        runNameContainer.style.cursor = 'pointer';
                        runNameContainer.className = 'flex-grow-1';
                        runNameContainer.onclick = () => loadRunCallback(run.id);

                        const runName = document.createElement('span');
                        runName.textContent = run.name;
                        runNameContainer.appendChild(runName);

                        const deleteBtn = document.createElement('button');
                        deleteBtn.className = 'btn btn-sm btn-outline-danger ms-2';
                        deleteBtn.innerHTML = '<i class="bi bi-trash"></i>';
                        deleteBtn.title = 'Delete run';
                        deleteBtn.onclick = (e) => {
                            e.stopPropagation();
                            deleteRunCallback(run.id);
                        };

                        runItem.appendChild(runNameContainer);
                        runItem.appendChild(deleteBtn);
                        savedRunsList.appendChild(runItem);
                    });
                } else {
                    noRunsMessage.style.display = 'block';
                    savedRunsList.style.display = 'none';
                }
            });
    },

    /**
     * Delete a run.
     * @param {string} url - URL to delete the run.
     * @param {string} csrfToken - CSRF token.
     */
    deleteRun: function(url, csrfToken) {
        if (!confirm(`Are you sure you want to delete this run? This action cannot be undone.`)) {
            return;
        }

        fetch(url, {
            method: 'DELETE',
            headers: { 'X-CSRFToken': csrfToken }
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'ok') {
                window.location.reload();
            } else {
                alert('Error deleting run: ' + (data.message || 'Unknown error'));
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('An network error occurred while deleting the run.');
        });
    },

    /**
     * Debounce a function.
     * @param {function} func - The function to debounce.
     * @param {number} wait - The delay in milliseconds.
     * @returns {function} The debounced function.
     */
    debounce: function(func, wait) {
        let timeout;
        return function(...args) {
            const context = this;
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(context, args), wait);
        };
    },
    BenchmarkRenderer: {
        ...BenchmarkComponents,
        
        renderProcessingRow: function(item, resultsBody, colSpan = 7) {
            const rowId = `processing-row`; // Fixed ID for easier finding
            const tr = document.createElement('tr');
            tr.id = rowId;
            tr.className = 'table-light border-bottom-0 processing-row';
            
            const td = document.createElement('td');
            td.colSpan = colSpan;
            td.className = 'text-center py-4 text-muted';
            
            td.innerHTML = `
                <div class="d-flex flex-column align-items-center justify-content-center">
                    <div class="spinner-border text-primary mb-2" role="status">
                        <span class="visually-hidden">Loading...</span>
                    </div>
                    <div class="fw-medium">Processing Question:</div>
                    <div class="small text-dark fw-bold mt-1" style="max-width: 80%; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                        ${item.question || 'Unknown'}
                    </div>
                </div>
            `;
            
            tr.appendChild(td);
            resultsBody.insertAdjacentElement('afterbegin', tr); // Add to top
            return tr;
        },
        
        // This will be the new centralized render function
        renderResultRow: function(data, resultsBody, index, type = 'vanilla_adhoc', isRetry = false) {
            const rowId = `result-${Date.now()}-${Math.random()}`;
            const tr = document.createElement('tr');
            tr.dataset.id = rowId;

            if (data.error) {
                tr.className = "table-warning";
                const td = document.createElement('td');
                td.colSpan = (type === 'rag_adhoc') ? 8 : 7;
                td.textContent = `Error: ${data.error}`;
                tr.appendChild(td);
                if (!isRetry) {
                    // This 'failedItems' needs to be managed externally or passed in
                    // For now, it will remain in adhoc files.
                    // failedItems.push({ ...data, rowId }); 
                }
            } else {
                const ruleCorrect = data.hasOwnProperty('is_correct_rule') ? data.is_correct_rule : data.rule_result;
                const llmCorrect = data.hasOwnProperty('is_correct_llm') ? data.is_correct_llm : data.llm_result;
                
                // Use LLM result for styling if available, otherwise fallback to rule or neutral
                let rowClass = 'table-light';
                let textClass = 'text-dark';

                if (llmCorrect === true) {
                    rowClass = 'table-success-light';
                    textClass = 'text-success-dark';
                } else if (llmCorrect === false) {
                    rowClass = 'table-danger-light';
                    textClass = 'text-danger-dark';
                } else if (ruleCorrect === true) {
                     // Fallback to rule if LLM is null (optional, or just leave neutral)
                     // But user emphasized LLM judge. If LLM is null, maybe just keep neutral/warning.
                     // Let's stick to strict LLM judge as requested, but maybe show warning if null.
                     rowClass = 'table-warning-light'; 
                }

                tr.className = rowClass;
                const textColorClass = textClass;

                // Cell 1: Index or empty
                const td1 = document.createElement('td');
                td1.className = 'px-4 fw-bold text-muted small';
                if (index) { // Only add index if provided (e.g., for pipeline runs)
                    td1.textContent = index;
                }
                tr.appendChild(td1);

                // Cell 2: Question
                const td2 = document.createElement('td');
                td2.className = 'px-4';
                const divQuestion = this.createTextElement('div', `compact-cell fw-bold ${textColorClass}`, data.question);
                td2.appendChild(divQuestion);
                tr.appendChild(td2);

                // Cell 3: Answer (with Toggle for Reasoning)
                const td3 = document.createElement('td');
                td3.className = 'px-4';
                
                // Main parsed answer
                const divAnswer = this.createTextElement('div', `compact-cell ${textColorClass}`, data.answer);
                td3.appendChild(divAnswer);

                // If full_response is present and different from answer, show toggle
                if (data.full_response && data.full_response !== data.answer) {
                    const reasoningContainer = document.createElement('div');
                    reasoningContainer.className = 'mt-1';

                    const viewReasoningBtn = document.createElement('button');
                    viewReasoningBtn.className = 'btn btn-link btn-sm p-0 text-decoration-none small view-reasoning-btn';
                    viewReasoningBtn.dataset.reasoning = data.full_response;
                    viewReasoningBtn.type = 'button';
                    viewReasoningBtn.innerHTML = '<i class="bi bi-card-text"></i> View Reasoning';
                    viewReasoningBtn.style.fontSize = '0.9rem';
                    viewReasoningBtn.classList.add(textColorClass);

                    reasoningContainer.appendChild(viewReasoningBtn);
                    td3.appendChild(reasoningContainer);
                }
                
                tr.appendChild(td3);

                // Cell 4: Ground Truths
                const td4 = document.createElement('td');
                const groundTruthsArray = data.ground_truths || [];
                const remainingCount = groundTruthsArray.length - 3;
                const ul = document.createElement('ul');
                ul.className = 'list-unstyled mb-0';
                ul.dataset.expanded = 'false';
                ul.dataset.remaining = remainingCount.toString();

                groundTruthsArray.forEach((gt, gtIndex) => {
                    const li = document.createElement('li');
                    li.className = 'text-secondary small ground-truth-item';
                    if (gtIndex >= 3) {
                        li.style.display = 'none';
                    }
                    li.appendChild(this.createIcon('bi bi-dot me-1 text-muted'));
                    li.appendChild(document.createTextNode(gt));
                    ul.appendChild(li);
                });

                if (groundTruthsArray.length > 3) {
                    const liShowMore = document.createElement('li');
                    liShowMore.className = 'show-more-item';
                    const a = this.createLink('#', 'toggle-answers-link small text-decoration-none', `... Show ${remainingCount} more`);
                    liShowMore.appendChild(a);
                    ul.appendChild(liShowMore);
                }
                td4.appendChild(ul);
                tr.appendChild(td4);

                // Cell for Search Results (RAG Adhoc specific)
                if (type === 'rag_adhoc') {
                    const tdSearch = document.createElement('td');
                    tdSearch.className = 'px-4';
                    if (data.search_results && data.search_results.length > 0) {
                        const resultsJson = encodeURIComponent(JSON.stringify(data.search_results));
                        const count = data.search_results.length;
                        const button = document.createElement('button');
                        button.className = 'btn btn-sm btn-outline-primary view-all-results-btn';
                        button.type = 'button';
                        button.dataset.results = resultsJson;
                        button.appendChild(this.createIcon('bi bi-list-ul me-1'));
                        button.appendChild(document.createTextNode(`View ${count} Results`));
                        tdSearch.appendChild(button);
                    } else {
                        tdSearch.appendChild(this.createTextElement('span', 'text-muted fst-italic small', 'No results'));
                    }
                    tr.appendChild(tdSearch);
                }

                // Cell 5/6: Rule Badge
                const tdRuleBadge = document.createElement('td');
                tdRuleBadge.className = 'px-4 text-center align-middle';
                tdRuleBadge.appendChild(this.createBadge(null, ruleCorrect));
                tr.appendChild(tdRuleBadge);

                // Cell 6/7: LLM Badge
                const tdLlmBadge = document.createElement('td');
                tdLlmBadge.className = 'px-4 text-center align-middle';
                tdLlmBadge.appendChild(this.createBadge(null, llmCorrect, true)); // show N/A for null
                tr.appendChild(tdLlmBadge);

                // Cell 7/8: Agreement Icon
                const tdAgreement = document.createElement('td');
                tdAgreement.className = 'px-4 text-center align-middle';
                const agreementIconI = this.createIcon((llmCorrect !== null && ruleCorrect === llmCorrect)
                    ? 'bi bi-check-circle-fill text-success fs-5'
                    : 'bi bi-x-circle-fill text-danger fs-5');
                tdAgreement.appendChild(agreementIconI);
                tr.appendChild(tdAgreement);
            }

            if (isRetry && data.originalRowId) {
                const originalRow = resultsBody.querySelector(`[data-id="${data.originalRowId}"]`);
                if (originalRow) {
                    resultsBody.replaceChild(tr, originalRow);
                } else {
                     resultsBody.insertAdjacentElement('afterbegin', tr);
                }
            } else {
                resultsBody.insertAdjacentElement('afterbegin', tr);
            }
            
            const finalRuleCorrect = data.hasOwnProperty('is_correct_rule') ? data.is_correct_rule : data.rule_result;
            const finalLlmCorrect = data.hasOwnProperty('is_correct_llm') ? data.is_correct_llm : data.llm_result;
            
            return { ruleCorrect: finalRuleCorrect, llmCorrect: finalLlmCorrect, rowId: rowId };
        },

        renderSearchResults: function(results, resultsListElement) {
            resultsListElement.innerHTML = ''; // Clear previous results
            if (results && results.length > 0) {
                results.forEach((res, index) => {
                    const item = document.createElement('a');
                    item.href = res.link || '#';
                    item.target = "_blank";
                    item.className = "list-group-item list-group-item-action";

                    const divFlex = document.createElement('div');
                    divFlex.className = "d-flex w-100 justify-content-between";

                    const h6Title = document.createElement('h6');
                    h6Title.className = "mb-1 text-primary";
                    h6Title.textContent = `${index + 1}. ${res.title || 'No Title'}`;
                    divFlex.appendChild(h6Title);
                    item.appendChild(divFlex);

                    const pSnippet = document.createElement('p');
                    pSnippet.className = "mb-1 small text-muted";
                    pSnippet.textContent = res.snippet || 'No snippet available.';
                    item.appendChild(pSnippet);

                    const smallLink = document.createElement('small');
                    smallLink.className = "text-truncate d-block text-secondary";
                    smallLink.textContent = res.link || '';
                    item.appendChild(smallLink);
                    
                    resultsListElement.appendChild(item);
                });
            } else {
                this.renderNoSearchResults(resultsListElement);
            }
        },

        renderNoSearchResults: function(resultsListElement) {
            resultsListElement.innerHTML = ''; // Clear previous results
            const alertDiv = document.createElement('div');
            alertDiv.className = 'alert alert-info';
            alertDiv.textContent = 'No results found.';
            resultsListElement.appendChild(alertDiv);
        },

        renderSearchError: function(resultsListElement, errorMessage) {
            resultsListElement.innerHTML = ''; // Clear previous results
            const alertDiv = document.createElement('div');
            alertDiv.className = 'alert alert-danger';
            alertDiv.textContent = errorMessage;
            resultsListElement.appendChild(alertDiv);
        },

        renderModalSearchResults: function(results, container, modalId = 'benchmarkGenericModal') {
            const modalTitle = document.getElementById(modalId + 'Label');
            if (modalTitle) modalTitle.textContent = 'Search Results';
            container.innerHTML = ''; // Clear existing content

            if (results && results.length > 0) {
                results.forEach((res, idx) => {
                    const linkUrl = res.link || res.url || '#';
                    const linkTitle = res.title || 'No Title';
                    const snippet = res.snippet || 'No snippet available.';
                    
                    let domain = '';
                    try {
                        if (linkUrl && linkUrl !== '#') {
                            const urlObj = new URL(linkUrl);
                            domain = urlObj.hostname.replace('www.', '');
                        }
                    } catch(err) {}

                    const item = document.createElement('div');
                    item.className = 'list-group-item p-3';

                    const div1 = document.createElement('div');
                    div1.className = 'd-flex w-100 justify-content-between mb-1';
                    item.appendChild(div1);

                    const h6 = document.createElement('h6');
                    h6.className = 'mb-0 text-primary fw-bold';
                    div1.appendChild(h6);

                    const spanIdx = document.createElement('span');
                    spanIdx.className = 'text-muted fw-normal me-2';
                    spanIdx.textContent = `#${idx + 1}`;
                    h6.appendChild(spanIdx);

                    const aTitle = document.createElement('a');
                    aTitle.href = linkUrl;
                    aTitle.target = '_blank';
                    aTitle.className = 'text-decoration-none';
                    aTitle.textContent = linkTitle;
                    h6.appendChild(aTitle);

                    const smallDomain = document.createElement('small');
                    smallDomain.className = 'text-muted text-end ms-2';
                    smallDomain.textContent = domain;
                    div1.appendChild(smallDomain);

                    const pSnippet = document.createElement('p');
                    pSnippet.className = 'mb-1 text-dark';
                    pSnippet.style.fontSize = '0.95rem';
                    pSnippet.style.lineHeight = '1.4';
                    pSnippet.textContent = snippet;
                    item.appendChild(pSnippet);

                    const smallLink = document.createElement('small');
                    smallLink.className = 'text-muted font-monospace';
                    smallLink.style.fontSize = '0.75rem';
                    item.appendChild(smallLink);

                    const iLink = document.createElement('i');
                    iLink.className = 'bi bi-link-45deg';
                    smallLink.appendChild(iLink);
                    smallLink.appendChild(document.createTextNode(` ${linkUrl}`));
                    
                    container.appendChild(item);
                });
            } else {
                const noResultsDiv = document.createElement('div');
                noResultsDiv.className = 'p-3 text-center text-muted';
                noResultsDiv.textContent = 'No results data found.';
                container.appendChild(noResultsDiv);
            }
        },

        /**
         * Renders a modal with the full RAG prompt content.
         * @param {string} promptContent - The full RAG prompt text.
         * @param {string} containerId - The ID of the modal body container.
         * @param {string} modalId - The ID of the modal itself.
         * @param {string} title - The title to display in the modal header.
         */
        renderPromptModal: function(promptContent, containerId, modalId = 'benchmarkGenericModal', title = 'RAG Prompt') {
            const modalTitle = document.getElementById(modalId + 'Label');
            if (modalTitle) modalTitle.textContent = title;

            const container = document.getElementById(containerId);
            if (!container) return;

            container.innerHTML = ''; // Clear existing content

            const pre = document.createElement('pre');
            pre.className = 'p-3 bg-light border rounded small text-secondary';
            pre.style.whiteSpace = 'pre-wrap';
            pre.textContent = promptContent;
            container.appendChild(pre);

            const modal = new bootstrap.Modal(document.getElementById(modalId));
            modal.show();
        },

        renderMultiTurnResultRow: function(result, index, loadSessionCallback) {
            const row = document.createElement('tr');
            row.style.cursor = "pointer";
            if (loadSessionCallback) {
                row.onclick = () => loadSessionCallback(result.session_id);
            }

            let resultBadge;
            if (result.correct === true) {
                resultBadge = document.createElement('span');
                resultBadge.className = 'badge bg-success';
                resultBadge.textContent = 'Correct';
            } else if (result.correct === false) {
                resultBadge = document.createElement('span');
                resultBadge.className = 'badge bg-danger';
                resultBadge.textContent = 'Incorrect';
            } else {
                resultBadge = document.createElement('span');
                resultBadge.className = 'badge bg-warning text-dark';
                resultBadge.textContent = 'Error';
            }
            
            const GROUNDTRUTH_DISPLAY_LIMIT = 3; 
            const ulGroundTruths = document.createElement('ul');
            ulGroundTruths.className = 'list-unstyled mb-0';

            const initialGroundTruths = result.ground_truths.slice(0, GROUNDTRUTH_DISPLAY_LIMIT);
            initialGroundTruths.forEach(gt => {
                const li = document.createElement('li');
                li.className = 'text-secondary small';
                const icon = document.createElement('i');
                icon.className = 'bi bi-dot me-1 text-muted';
                li.appendChild(icon);
                li.appendChild(document.createTextNode(gt));
                ulGroundTruths.appendChild(li);
            });

            const fullGroundTruthsDiv = document.createElement('div');
            fullGroundTruthsDiv.style.display = 'none';
            result.ground_truths.slice(GROUNDTRUTH_DISPLAY_LIMIT).forEach(gt => {
                const li = document.createElement('li');
                li.className = 'text-secondary small';
                const icon = document.createElement('i');
                icon.className = 'bi bi-dot me-1 text-muted';
                li.appendChild(icon);
                li.appendChild(document.createTextNode(gt));
                fullGroundTruthsDiv.appendChild(li);
            });
            ulGroundTruths.appendChild(fullGroundTruthsDiv);

            let showMoreButton;
            let showLessButton;

            if (result.ground_truths.length > GROUNDTRUTH_DISPLAY_LIMIT) {
                showMoreButton = document.createElement('button');
                showMoreButton.className = 'btn btn-link btn-sm p-0 mt-1 show-more-groundtruths';
                showMoreButton.type = 'button';
                showMoreButton.textContent = `Show ${result.ground_truths.length - GROUNDTRUTH_DISPLAY_LIMIT} more`;
                
                showLessButton = document.createElement('button');
                showLessButton.className = 'btn btn-link btn-sm p-0 mt-1 show-less-groundtruths';
                showLessButton.type = 'button';
                showLessButton.style.display = 'none';
                showLessButton.textContent = 'Show less';

                showMoreButton.onclick = (e) => {
                    e.stopPropagation();
                    fullGroundTruthsDiv.style.display = 'block';
                    showMoreButton.style.display = 'none';
                    showLessButton.style.display = 'inline';
                };

                showLessButton.onclick = (e) => {
                    e.stopPropagation();
                    fullGroundTruthsDiv.style.display = 'none';
                    showMoreButton.style.display = 'inline';
                    showLessButton.style.display = 'none';
                };
            }
            
            const td1 = document.createElement('td');
            td1.className = 'px-4 fw-bold text-muted small';
            td1.textContent = index + 1;
            row.appendChild(td1);

            const td2 = document.createElement('td');
            td2.className = 'px-4';
            td2.textContent = result.question;
            row.appendChild(td2);

            const td3 = document.createElement('td');
            td3.className = 'px-4';
            const em = document.createElement('em');
            em.textContent = `“${result.final_answer || 'N/A'}”`;
            td3.appendChild(em);
            row.appendChild(td3);

            const td4 = document.createElement('td');
            td4.className = 'px-4';
            td4.appendChild(ulGroundTruths);
            if (showMoreButton) {
                td4.appendChild(showMoreButton);
                td4.appendChild(showLessButton);
            }
            row.appendChild(td4);

            const td5 = document.createElement('td');
            td5.className = 'px-4 text-center';
            td5.appendChild(resultBadge);
            row.appendChild(td5);

            const td6 = document.createElement('td');
            td6.className = 'px-4 text-center';
            td6.textContent = result.trials;
            row.appendChild(td6);
            
            return row;
        },

        renderTrial: function(trial, isCompleted, trialCount, maxRetries) {
            const trialDiv = document.createElement('div');
            trialDiv.className = 'mb-4';
            trialDiv.id = `trial-${trial.id}`;
    
            let searchSection = '';
            if (trial.search_query) {
                const resultsCount = trial.search_results ? trial.search_results.length : 0;
                const resultsJson = trial.search_results ? encodeURIComponent(JSON.stringify(trial.search_results)) : '';
                
                let resultsBadge = '';
                if (resultsCount > 0) {
                    resultsBadge = `
                        <button class="btn btn-sm btn-white bg-white border shadow-sm ms-auto view-search-results-btn d-flex align-items-center" data-results="${resultsJson}" style="font-size: 0.85rem; height: 32px;">
                            <i class="bi bi-list-task text-primary me-2"></i>
                            <span class="fw-semibold text-dark">${resultsCount}</span>
                            <span class="text-muted ms-1 small d-none d-sm-inline">results</span>
                        </button>
                    `;
                } else {
                    resultsBadge = `<span class="badge bg-secondary bg-opacity-10 text-secondary border ms-auto">No results</span>`;
                }
    
                searchSection = `
                    <div class="d-flex align-items-center bg-light bg-opacity-50 rounded p-2 mb-3 border border-light-subtle">
                        <div class="d-flex align-items-center flex-grow-1 overflow-hidden">
                            <div class="bg-white rounded-circle border d-flex align-items-center justify-content-center me-3 shadow-sm" style="width: 36px; height: 36px; min-width: 36px;">
                                <i class="bi bi-search text-primary" style="font-size: 1rem;"></i>
                            </div>
                            <div class="d-flex flex-column overflow-hidden me-3">
                                <span class="text-uppercase text-muted fw-bold" style="font-size: 0.65rem; letter-spacing: 1px;">Search Query</span>
                                <span class="text-dark fw-medium text-truncate font-monospace small" title="${trial.search_query}">${trial.search_query}</span>
                            </div>
                        </div>
                        ${resultsBadge}
                    </div>
                `;
            }
    
    
            let trialBody = '';
            if (trial.status === 'processing') {
                trialBody = `<div class="d-flex align-items-center py-3">
                                <div class="spinner-border text-primary me-3" role="status" style="width: 2rem; height: 2rem;">
                                    <span class="visually-hidden">Loading...</span>
                                </div>
                                <div>
                                    <h6 class="mb-0 text-dark">Processing...</h6>
                                    <small class="text-muted">Waiting for LLM response</small>
                                </div>
                             </div>`;
            } else if (trial.status === 'error') {
                trialBody = `<div class="alert alert-danger border-0 shadow-sm d-flex align-items-center">
                                <i class="bi bi-exclamation-triangle-fill me-3 fs-4"></i>
                                <div>
                                    <strong>Error</strong>
                                    <div class="small">An error occurred while running this trial.</div>
                                </div>
                             </div>`;
            } else { // completed
                let feedbackControls = '';
                if (!isCompleted && trialCount < maxRetries) {
                    if (trial.is_correct === false) {
                        feedbackControls = `<div class="d-flex align-items-center mt-3 text-warning bg-warning bg-opacity-10 p-2 rounded">
                                                <span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>
                                                <span class="small fw-medium">Answer was incorrect. Automatically retrying...</span>
                                             </div>`;
                    } else if (trial.is_correct === null) {
                        feedbackControls = `<p class="mt-2 text-muted small"><i class="bi bi-hourglass-split me-1"></i>Awaiting automated judgment...</p>`;
                    }
                }
    
                // Determine if we have reasoning to show
                let reasoningSection = '';
                if (trial.full_response && trial.full_response !== trial.answer) {
                    // We generate a unique ID for the collapse element
                    const collapseId = `reasoning-collapse-${trial.id || Math.random().toString(36).substr(2, 9)}`;
                    reasoningSection = `
                        <div class="mt-2">
                            <button class="btn btn-sm btn-link text-decoration-none p-0 collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#${collapseId}" aria-expanded="false" aria-controls="${collapseId}">
                                <i class="bi bi-caret-right-fill"></i> Show Chain of Thought
                            </button>
                            <div class="collapse mt-2" id="${collapseId}">
                                <div class="card card-body bg-light border-0 small text-secondary" style="white-space: pre-wrap;">${trial.full_response}</div>
                            </div>
                        </div>
                    `;
                }

                trialBody = `
                            ${searchSection}
                            <div class="p-3 bg-white rounded border-start border-4 border-primary shadow-sm mb-3">
                                <div class="d-flex align-items-start">
                                    <i class="bi bi-chat-quote text-primary opacity-50 fs-3 me-3"></i>
                                    <div class="w-100">
                                        <span class="text-uppercase text-muted fw-bold d-block mb-1" style="font-size: 0.65rem; letter-spacing: 1px;">LLM Answer</span>
                                        <p class="mb-0 fs-6 text-dark">${trial.answer}</p>
                                        ${reasoningSection}
                                    </div>
                                </div>
                            </div>`;
                if (trial.feedback) {
                    const isCorrect = trial.is_correct;
                    const alertClass = isCorrect ? 'alert-success' : 'alert-danger';
                    const icon = isCorrect ? '<i class="bi bi-check-circle-fill me-2 fs-5"></i>' : '<i class="bi bi-x-circle-fill me-2 fs-5"></i>';
                    trialBody += `<div class="alert ${alertClass} border-0 d-flex align-items-center mt-3 shadow-sm" role="alert">
                                    ${icon}
                                    <div>
                                        <strong class="d-block text-uppercase" style="font-size: 0.7rem; letter-spacing: 0.5px;">Verdict</strong>
                                        ${trial.feedback}
                                    </div>
                                  </div>`;
                }
                trialBody += feedbackControls;
            }
    
            const isLastAttempt = trialCount >= maxRetries;
            let statusBadge = '';
            if (isCompleted || isLastAttempt || trial.is_correct === true) {
                if (trial.is_correct) {
                    statusBadge = '<span class="badge bg-success rounded-pill shadow-sm"><i class="bi bi-check-lg me-1"></i>Correct</span>';
                } else if (trial.is_correct === false) {
                     statusBadge = '<span class="badge bg-danger rounded-pill shadow-sm"><i class="bi bi-x-lg me-1"></i>Incorrect</span>';
                }
            }
    
            trialDiv.innerHTML = `
                <div class="card border-0 shadow-sm overflow-hidden">
                    <div class="card-header bg-white border-bottom py-3 d-flex justify-content-between align-items-center">
                        <h6 class="mb-0 fw-bold text-secondary text-uppercase small" style="letter-spacing: 1px;">
                            <i class="bi bi-arrow-return-right me-2"></i>Trial #${trial.trial_number}
                        </h6>
                        <div>${statusBadge}</div>
                    </div>
                    <div class="card-body bg-light bg-opacity-10">
                        ${trialBody}
                    </div>
                </div>`;
            return trialDiv;
        },
    },
    displayRunResults: function(runData, updateSummaryFunc, pipelineType = 'vanilla_adhoc') {
        const resultsContainer = document.getElementById('pipeline-results-container');
        const progressContainer = document.getElementById('progress-container');
        const saveRunBtn = document.getElementById('save-run-btn');
        const resultsHeader = document.getElementById('results-header-text');
        const resultsBody = document.getElementById('pipeline-results-body');

        resultsContainer.style.display = 'block';
        if (progressContainer) progressContainer.style.display = 'none';
        if (saveRunBtn) saveRunBtn.disabled = true;

        resultsHeader.textContent = `Results for: ${runData.name}`;
        resultsBody.innerHTML = '';
        
        // Ensure status and processing rows are cleared
        const statusDiv = document.getElementById('pipeline-status');
        if (statusDiv) statusDiv.style.display = 'none';
        const processingRow = document.getElementById('processing-row');
        if (processingRow) processingRow.remove();

        let stats = {
            total: runData.results.length,
            ruleCorrect: 0,
            llmCorrect: 0,
            llmErrors: 0,
            agreements: 0,
            totalDocsUsed: 0
        };

        runData.results.forEach((result, index) => {
            const summary = BenchmarkUtils.BenchmarkRenderer.renderResultRow(result, resultsBody, index + 1, pipelineType);
            result.rowId = summary.rowId; // Attach rowId for future reference (e.g. retry)
            
            if (summary.ruleCorrect) stats.ruleCorrect++;
            if (summary.llmCorrect) stats.llmCorrect++;
            if (summary.llmCorrect === null) stats.llmErrors++;
            if (summary.llmCorrect !== null && summary.ruleCorrect === summary.llmCorrect) {
                stats.agreements++;
            }
            stats.totalDocsUsed += (result.num_docs_used || 0);
        });

        if (updateSummaryFunc) {
            updateSummaryFunc(stats);
        }

        if (saveRunBtn) saveRunBtn.disabled = true;
        const retryBtn = document.getElementById('retry-btn');
        if (retryBtn) retryBtn.style.display = 'none';
    },

    renderRunConfiguration: function(snapshot, whitelist = null) {
        const configCard = document.getElementById('run-config-card');
        const configDetails = document.getElementById('run-config-details');
        
        if (!configCard || !configDetails) return;

        snapshot = snapshot || {}; 

        configDetails.innerHTML = '';
        
        const addItem = (label, value, icon) => {
            const col = document.createElement('div');
            col.className = 'col-md-4 col-sm-6';

            const divFlex = document.createElement('div');
            divFlex.className = 'd-flex align-items-center bg-white p-2 rounded border';

            const iconElement = document.createElement('i');
            iconElement.className = `bi ${icon} text-secondary me-2 fs-5`;
            divFlex.appendChild(iconElement);

            const divOverflow = document.createElement('div');
            divOverflow.className = 'overflow-hidden';

            const divLabel = document.createElement('div');
            divLabel.className = 'text-muted text-uppercase';
            divLabel.style.fontSize = '0.65rem';
            divLabel.style.letterSpacing = '0.5px';
            divLabel.textContent = label;
            divOverflow.appendChild(divLabel);

            const divValue = document.createElement('div');
            divValue.className = 'fw-medium text-truncate';
            divValue.title = value;
            divValue.textContent = value; 
            divOverflow.appendChild(divValue);

            divFlex.appendChild(divOverflow);
            col.appendChild(divFlex);
            configDetails.appendChild(col);
        };

        const shouldShow = (key) => !whitelist || whitelist.includes(key);
        const getValue = (obj, key, domId) => {
            if (obj && (obj[key] !== undefined && obj[key] !== null && obj[key] !== '')) return obj[key];
            const el = document.getElementById(domId);
            return el ? el.value : null;
        };
        
        // Check for nested first (if full snapshot passed)
        let llmSettings = snapshot.llm_settings || snapshot; 

        if (shouldShow('llm_model')) {
            const val = getValue(llmSettings, 'llm_model', 'llm_model');
            if (val) addItem('LLM Model', val, 'bi-cpu');
        }
        if (shouldShow('max_retries')) {
            const val = getValue(llmSettings, 'max_retries', 'max_retries');
            if (val) addItem('Max Retries', val, 'bi-arrow-repeat');
        }
        if (shouldShow('allow_reasoning')) {
            let val = getValue(llmSettings, 'allow_reasoning', 'allow_reasoning');
            // If pulling from DOM checkbox
            if (val === 'on' || val === true) val = 'Enabled';
            else if (val === false) val = 'Disabled';
            
            // If pulling from snapshot (boolean)
            if (val === true) val = 'Enabled';
            if (val === false) val = 'Disabled';

            if (val) addItem('Reasoning', val, 'bi-lightbulb');
        }
        if (shouldShow('llm_base_url')) {
            const val = getValue(llmSettings, 'llm_base_url', 'llm_base_url');
            if (val) addItem('Base URL', val, 'bi-link-45deg');
        }

        if (shouldShow('rag_settings')) {
            const rs = snapshot.rag_settings || {};
            let prompt = rs.prompt_template;
            if (!prompt && document.getElementById('rag_prompt_template')) {
                prompt = document.getElementById('rag_prompt_template').value;
            }
            if (prompt) {
                const col = document.createElement('div');
                col.className = 'col-md-4 col-sm-6';

                const divFlex = document.createElement('div');
                divFlex.className = 'd-flex align-items-center bg-white p-2 rounded border';

                const iconElement = document.createElement('i');
                iconElement.className = 'bi bi-chat-text text-secondary me-2 fs-5';
                divFlex.appendChild(iconElement);

                const divOverflow = document.createElement('div');
                divOverflow.className = 'overflow-hidden flex-grow-1';

                const divLabel = document.createElement('div');
                divLabel.className = 'text-muted text-uppercase';
                divLabel.style.fontSize = '0.65rem';
                divLabel.style.letterSpacing = '0.5px';
                divLabel.textContent = 'RAG Prompt';
                divOverflow.appendChild(divLabel);

                const button = document.createElement('button');
                button.className = 'btn btn-sm btn-outline-secondary mt-1';
                button.type = 'button';
                button.textContent = 'View Full Prompt';
                button.onclick = () => {
                    BenchmarkUtils.BenchmarkRenderer.renderPromptModal(prompt, 'modal-generic-content-container', 'benchmarkGenericModal', 'RAG Prompt');
                };

                divOverflow.appendChild(button);
                divFlex.appendChild(divOverflow);
                col.appendChild(divFlex);
                configDetails.appendChild(col);
            }
        }
        
        if (shouldShow('search_settings')) {
            const ss = snapshot.search_settings || {};
            let provider = ss.search_provider;
            if (!provider && document.querySelector('input[name="search_provider"]:checked')) {
                provider = document.querySelector('input[name="search_provider"]:checked').value;
            }
            if (provider) {
                addItem('Search Provider', provider === 'mcp' ? 'MCP Server' : (provider === 'serper' ? 'Serper API' : provider), 'bi-globe');
            }
            
            // Search Limit
            let searchLimit = ss.search_limit;
            if ((searchLimit === undefined || searchLimit === '') && document.getElementById('search_limit')) {
                searchLimit = document.getElementById('search_limit').value;
            }
            if (searchLimit) {
                addItem('Top-K Limit', searchLimit, 'bi-list-ol');
            }

            // Full content
            let fullContent = ss.serper_fetch_full_content;
             if (fullContent === undefined && document.getElementById('serper_fetch_full_content')) {
                 fullContent = document.getElementById('serper_fetch_full_content').checked;
             }
            
            if (fullContent !== undefined) {
                addItem('Full Content', fullContent ? 'Enabled' : 'Disabled', 'bi-file-text');
            }
        }

        if (configDetails.children.length > 0) {
            configCard.style.display = 'block';
        } else {
            configCard.style.display = 'none';
        }
    },

    /**
     * Export data to CSV.
     * @param {Array} data - Array of data objects.
     * @param {string} filenamePrefix - Prefix for the filename.
     * @param {Array} headers - Array of header strings.
     * @param {Function} rowMapper - Function that takes a data item and index, returns an array of cell values.
     */
    exportToCSV: function(data, filenamePrefix, headers, rowMapper) {
        if (!data || data.length === 0) {
            alert("No results to export.");
            return;
        }

        const csvRows = [headers.join(',')];

        data.forEach((item, index) => {
            const rowValues = rowMapper(item, index);
            // Escape quotes and wrap in quotes
            const escapedRow = rowValues.map(val => {
                if (val === null || val === undefined) return '';
                const str = String(val);
                return `"${str.replace(/"/g, '""')}"`;
            });
            csvRows.push(escapedRow.join(','));
        });

        const csvString = csvRows.join('\n');
        const blob = new Blob([csvString], { type: 'text/csv;charset=utf-8;' });

        const link = document.createElement("a");
        if (link.download !== undefined) {
            const url = URL.createObjectURL(blob);
            
            // Try to get a meaningful name from the UI if possible, else use timestamp
            let nameSuffix = '';
            const resultsHeader = document.getElementById("results-header-text");
            if (resultsHeader && resultsHeader.textContent) {
                nameSuffix = resultsHeader.textContent.replace('Results for', '').trim();
            }
            if (!nameSuffix) {
                nameSuffix = new Date().toISOString().slice(0, 19).replace('T', '_').replace(/:/g, '-');
            }

            const filename = `${filenamePrefix}-${nameSuffix.replace(/[^a-zA-Z0-9-_]/g, '_')}.csv`;
            
            link.setAttribute("href", url);
            link.setAttribute("download", filename);
            link.style.visibility = 'hidden';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }
    },

    /**
     * Export data to JSON.
     * @param {Array} data - Array of data objects.
     * @param {string} filenamePrefix - Prefix for the filename.
     */
    exportToJSON: function(data, filenamePrefix) {
        if (!data || data.length === 0) {
            alert("No results to export.");
            return;
        }

        const jsonString = JSON.stringify(data, null, 2);
        const blob = new Blob([jsonString], { type: 'application/json;charset=utf-8;' });

        const link = document.createElement("a");
        if (link.download !== undefined) {
            const url = URL.createObjectURL(blob);
            
            let nameSuffix = '';
            const resultsHeader = document.getElementById("results-header-text");
            if (resultsHeader && resultsHeader.textContent) {
                nameSuffix = resultsHeader.textContent.replace('Results for', '').trim();
            }
            if (!nameSuffix) {
                nameSuffix = new Date().toISOString().slice(0, 19).replace('T', '_').replace(/:/g, '-');
            }

            const filename = `${filenamePrefix}-${nameSuffix.replace(/[^a-zA-Z0-9-_]/g, '_')}.json`;
            
            link.setAttribute("href", url);
            link.setAttribute("download", filename);
            link.style.visibility = 'hidden';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }
    },

    /**
     * Process a streamed JSON response (NDJSON).
     * @param {Response} response - The fetch Response object.
     * @param {Function} onData - Callback for each parsed JSON object.
     * @param {Function} onComplete - Callback when stream completes.
     * @param {Function} onError - Callback on error.
     * @param {AbortSignal} abortSignal - Signal to check for abortion.
     */
    processStreamedResponse: function(response, onData, onComplete, onError, abortSignal) {
        if (!response.ok) {
            onError(new Error(`HTTP error! status: ${response.status}`));
            return;
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        function push() {
            reader.read().then(({ done, value }) => {
                if (done) {
                    if (onComplete) onComplete();
                    return;
                }

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop(); // Keep partial line

                lines.forEach(line => {
                    if (abortSignal && abortSignal.aborted) {
                        reader.cancel();
                        return;
                    }
                    if (line.trim() === '') return;

                    try {
                        let data = JSON.parse(line);
                        // Handle double-encoded JSON if necessary (though ideally backend shouldn't do this)
                        if (typeof data === 'string') {
                            try { data = JSON.parse(data); } catch(e) {}
                        }
                        onData(data);
                    } catch (e) {
                        console.error("Failed to parse JSON chunk:", e, line);
                    }
                });
                
                if (abortSignal && abortSignal.aborted) {
                     return; // Don't continue reading
                }

                push();
            }).catch(error => {
                if (onError) onError(error);
            });
        }
        push();
    },

    /**
     * Update standard Adhoc pipeline statistics UI.
     * @param {object} stats - Stats object { total, ruleCorrect, llmCorrect, llmErrors, agreements, totalDocsUsed }.
     */
    updateAdhocStatsUI: function(stats) {
        if (document.getElementById('rule-correct-count')) {
            document.getElementById('rule-correct-count').textContent = stats.ruleCorrect;
        }
        if (document.getElementById('rule-incorrect-count')) {
            const ruleIncorrect = stats.total - stats.ruleCorrect;
            document.getElementById('rule-incorrect-count').textContent = ruleIncorrect;
        }
        if (document.getElementById('rule-accuracy-rate')) {
            const ruleAccuracy = stats.total > 0 ? (stats.ruleCorrect / stats.total) * 100 : 0;
            document.getElementById('rule-accuracy-rate').textContent = `${ruleAccuracy.toFixed(2)}%`;
        }

        if (document.getElementById('llm-correct-count')) {
            document.getElementById('llm-correct-count').textContent = stats.llmCorrect;
        }
        if (document.getElementById('llm-incorrect-count')) {
            const llmIncorrect = stats.total - stats.llmCorrect - stats.llmErrors;
            document.getElementById('llm-incorrect-count').textContent = llmIncorrect;
        }
        if (document.getElementById('llm-accuracy-rate')) {
            const llmAccuracy = stats.total > 0 ? (stats.llmCorrect / stats.total) * 100 : 0;
            document.getElementById('llm-accuracy-rate').textContent = `${llmAccuracy.toFixed(2)}%`;
        }

        if (document.getElementById('processed-count')) {
            document.getElementById('processed-count').textContent = stats.total;
        }
        
        if (document.getElementById('agreement-rate')) {
            const agreementRate = stats.total > 0 ? (stats.agreements / stats.total) * 100 : 0;
            document.getElementById('agreement-rate').textContent = `${agreementRate.toFixed(2)}%`;
        }

        if (document.getElementById('total-searches-count')) {
            document.getElementById('total-searches-count').textContent = stats.total; 
        }
        if (document.getElementById('avg-docs-count')) {
            const avgDocs = stats.total > 0 ? (stats.totalDocsUsed / stats.total) : 0;
            document.getElementById('avg-docs-count').textContent = avgDocs.toFixed(1);
        }
    },

    MultiTurnUtils: {
        /**
         * Render a multi-turn session, including question, ground truths, and trials.
         * @param {object} session - The session object.
         * @param {Array} trials - Array of trial objects for the session.
         * @param {object} [options] - Optional settings.
         * @param {Array} [options.sessionTrials] - Reference to a sessionTrials array for external updates.
         * @param {string} [options.sessionContainerId='session-container'] - ID of the main session container.
         * @param {string} [options.noSessionSelectedId='no-session-selected'] - ID of the 'no session selected' message.
         */
        renderSession: function(session, trials, options = {}) {
            const {
                sessionTrials, // Assuming this is defined in the script that calls this
                sessionContainerId = 'session-container',
                noSessionSelectedId = 'no-session-selected'
            } = options;

            // Update external sessionTrials reference if provided
            if (sessionTrials) {
                sessionTrials.length = 0; // Clear existing
                sessionTrials.push(...trials); // Add new
            }

            document.getElementById('session-header').textContent = `Session #${session.id}`;
            document.getElementById('session-question').textContent = session.question;

            const gtContainer = document.getElementById('session-ground-truths');
            gtContainer.innerHTML = '';

            const GROUNDTRUTH_DISPLAY_LIMIT = 3; 

            if (session.ground_truths.length > GROUNDTRUTH_DISPLAY_LIMIT) {
                const initialGroundTruths = session.ground_truths.slice(0, GROUNDTRUTH_DISPLAY_LIMIT);
                initialGroundTruths.forEach(gt => {
                    const el = document.createElement('span');
                    el.className = 'badge bg-secondary me-1';
                    el.textContent = gt;
                    gtContainer.appendChild(el);
                });

                const showMoreBtn = document.createElement('button');
                showMoreBtn.className = 'btn btn-link btn-sm p-0';
                showMoreBtn.textContent = `Show ${session.ground_truths.length - GROUNDTRUTH_DISPLAY_LIMIT} more`;
                showMoreBtn.setAttribute('type', 'button');
                gtContainer.appendChild(showMoreBtn);

                const fullGroundTruthsDiv = document.createElement('div');
                fullGroundTruthsDiv.style.display = 'none'; // Initially hidden
                session.ground_truths.slice(GROUNDTRUTH_DISPLAY_LIMIT).forEach(gt => {
                    const el = document.createElement('span');
                    el.className = 'badge bg-secondary me-1';
                    el.textContent = gt;
                    fullGroundTruthsDiv.appendChild(el);
                });
                gtContainer.appendChild(fullGroundTruthsDiv);

                const showLessBtn = document.createElement('button');
                showLessBtn.className = 'btn btn-link btn-sm p-0 ms-2';
                showLessBtn.textContent = `Show less`;
                showLessBtn.setAttribute('type', 'button');
                showLessBtn.style.display = 'none'; // Initially hidden
                gtContainer.appendChild(showLessBtn);


                showMoreBtn.addEventListener('click', () => {
                    fullGroundTruthsDiv.style.display = 'block';
                    showMoreBtn.style.display = 'none';
                    showLessBtn.style.display = 'inline';
                });

                showLessBtn.addEventListener('click', () => {
                    fullGroundTruthsDiv.style.display = 'none';
                    showMoreBtn.style.display = 'inline';
                    showLessBtn.style.display = 'none';
                });

            } else {
                session.ground_truths.forEach(gt => {
                    const el = document.createElement('span');
                    el.className = 'badge bg-secondary me-1';
                    el.textContent = gt;
                    gtContainer.appendChild(el);
                });
            }

            const trialsContainer = document.getElementById('trials-container');
            trialsContainer.innerHTML = '';
            trials.forEach(trial => {
                trialsContainer.appendChild(BenchmarkUtils.BenchmarkRenderer.renderTrial(trial, session.is_completed, trials.length, session.max_retries));
            });
            
            document.getElementById(sessionContainerId).style.display = 'block';
            document.getElementById(noSessionSelectedId).style.display = 'none';
        },

        /**
         * Add a new session to the session list UI.
         * @param {string} sessionListId - The ID of the session list container.
         * @param {string} sessionId - The session ID.
         * @param {object} questionData - Data about the question (e.g., {question: "..."}).
         * @param {function} selectAllHandler - Function to handle select all checkbox change.
         * @param {string} groupId - The group ID (optional).
         * @param {string} groupName - The group name (optional).
         * @param {string} statusText - The status text to display.
         */
        addNewSessionToList: function(sessionListId, sessionId, questionData, selectAllHandler, groupId = null, groupName = null, statusText = 'Now') {
            const sessionList = document.getElementById(sessionListId);
            if (!sessionList) return;

            // Check if session already exists
            const existingCheckbox = document.querySelector(`.session-checkbox[value="${sessionId}"]`);
            if (existingCheckbox) {
                const sessionDetails = document.querySelector(`.session-details[data-session-id="${sessionId}"]`);
                if (sessionDetails) {
                        const timeEl = sessionDetails.querySelector('small.text-muted');
                        if (timeEl) {
                            timeEl.textContent = statusText;
                        }
                }
                return;
            }

            // If this is the first session ever, remove "no sessions" and add select-all header
            if (document.querySelector('.no-sessions')) {
                const noSessions = document.querySelector('.no-sessions');
                if (noSessions) noSessions.remove();
                
                // Only create if it doesn't exist
                if (!document.getElementById('select-all-container')) {
                    const selectAllContainer = document.createElement('div');
                    selectAllContainer.className = 'list-group-item bg-light';
                    selectAllContainer.id = 'select-all-container';
                    selectAllContainer.innerHTML = `
                        <input class="form-check-input" type="checkbox" id="select-all-checkbox">
                        <label class="form-check-label ms-2" for="select-all-checkbox">Select All</label>`;
                    sessionList.prepend(selectAllContainer);
                    const cb = document.getElementById('select-all-checkbox');
                    if (cb && selectAllHandler) cb.addEventListener('change', selectAllHandler);
                }
            }

            const newSessionItem = document.createElement('div');
            newSessionItem.className = 'list-group-item d-flex align-items-center session-item-container';
            newSessionItem.innerHTML = `
                <input class="form-check-input session-checkbox" type="checkbox" value="${sessionId}" data-session-id="${sessionId}">
                <div class="ms-3 flex-grow-1 session-details" data-session-id="${sessionId}" style="cursor: pointer;">
                    <div class="d-flex w-100 justify-content-between">
                        <h6 class="mb-1">Session #${sessionId}</h6>
                        <small class="text-muted">${statusText}</small>
                    </div>
                    <p class="mb-1 small text-muted">${(questionData.question || '').substring(0, 100)}...</p>
                </div>`;
            
            if (groupId) {
                let groupContainer = document.getElementById(`session-group-${groupId}`);
                if (!groupContainer) {
                    // Create the group container if it doesn't exist
                    const groupEl = document.createElement('div');
                    groupEl.className = 'list-group-item';
                    groupEl.innerHTML = `
                        <details open>
                            <summary class="fw-bold" style="cursor: pointer;">
                                <i class="bi bi-collection me-1"></i>
                                ${groupName}
                                <small class="text-muted" id="group-session-count-${groupId}">(1 sessions)</small>
                            </summary>
                            <div class="list-group list-group-flush mt-2" id="session-group-${groupId}">
                            </div>
                        </details>
                    `;
                    const selectAllDiv = document.getElementById('select-all-container');
                    if (selectAllDiv) {
                        selectAllDiv.after(groupEl);
                    } else {
                        sessionList.prepend(groupEl);
                    }
                    groupContainer = document.getElementById(`session-group-${groupId}`);
                }
                newSessionItem.classList.add("ps-4");
                groupContainer.prepend(newSessionItem);
                
                // Update session count
                const countEl = document.getElementById(`group-session-count-${groupId}`);
                if (countEl) {
                    const currentCount = groupContainer.children.length;
                    countEl.textContent = `(${currentCount} sessions)`;
                }

            } else {
                const selectAllDiv = document.getElementById('select-all-container');
                if (selectAllDiv) {
                    selectAllDiv.after(newSessionItem);
                } else {
                    sessionList.appendChild(newSessionItem);
                }
            }
        },

        /**
         * Update statistics UI for multi-turn benchmarks.
         * @param {Array} results - Array of result objects.
         * @param {string} groupName - Name of the group/run.
         * @param {function} loadSessionCallback - Callback to load a session.
         */
        updateStatsUI: function(results, groupName, loadSessionCallback) {
            const statsBody = document.getElementById('stats-details-tbody');
            if (statsBody) {
                statsBody.innerHTML = '';
                results.forEach((res, idx) => {
                    const tr = BenchmarkUtils.BenchmarkRenderer.renderMultiTurnResultRow(res, idx, loadSessionCallback);
                    statsBody.appendChild(tr);
                });
            }

            const total = results.length;
            if (total === 0) return;

            const correct = results.filter(r => r.correct === true).length;
            const incorrect = results.filter(r => r.correct === false).length;
            const error = results.filter(r => r.correct !== true && r.correct !== false).length;

            const accuracy = (correct / total) * 100;

            if(document.getElementById('stats-accuracy')) document.getElementById('stats-accuracy').textContent = `${accuracy.toFixed(2)}%`;
            if(document.getElementById('stats-correct-count')) document.getElementById('stats-correct-count').textContent = correct;
            if(document.getElementById('stats-incorrect-count')) document.getElementById('stats-incorrect-count').textContent = incorrect;
            if(document.getElementById('stats-error-count')) document.getElementById('stats-error-count').textContent = error;

            // Average trials
            const totalTrials = results.reduce((sum, r) => sum + (r.trials || 0), 0);
            const avgTrials = totalTrials / total;
            if(document.getElementById('stats-avg-trials-all')) document.getElementById('stats-avg-trials-all').textContent = avgTrials.toFixed(2);

            const successResults = results.filter(r => r.correct === true);
            const successTrials = successResults.reduce((sum, r) => sum + (r.trials || 0), 0);
            const avgSuccessTrials = successResults.length > 0 ? successTrials / successResults.length : 0;
            if(document.getElementById('stats-avg-trials-success')) document.getElementById('stats-avg-trials-success').textContent = avgSuccessTrials.toFixed(2);

            // First try success
            const firstTrySuccess = results.filter(r => r.correct === true && r.trials === 1).length;
            const firstTryRate = (firstTrySuccess / total) * 100;
            if(document.getElementById('stats-first-try-success')) document.getElementById('stats-first-try-success').textContent = `${firstTryRate.toFixed(2)}%`;

            // Give up rate (max retries reached and still incorrect)
            // Assuming max retries is constant or we check if correct is false
            const giveUp = results.filter(r => r.correct === false).length; // Simple approximation
            const giveUpRate = (giveUp / total) * 100;
            if(document.getElementById('stats-give-up-rate')) document.getElementById('stats-give-up-rate').textContent = `${giveUpRate.toFixed(2)}%`;

            // Self-Correction Rate
            // initial_correct is provided by the backend. 
            // Denominator: Sessions where initial_correct is FALSE
            // Numerator: Sessions where initial_correct is FALSE AND final correct is TRUE
            const initialFailures = results.filter(r => r.initial_correct === false);
            const selfCorrected = initialFailures.filter(r => r.correct === true);
            const selfCorrectionRate = initialFailures.length > 0 ? (selfCorrected.length / initialFailures.length) * 100 : 0;
            if(document.getElementById('stats-self-correction-rate')) {
                document.getElementById('stats-self-correction-rate').textContent = `${selfCorrectionRate.toFixed(2)}%`;
                document.getElementById('stats-self-correction-rate').title = `${selfCorrected.length} corrected out of ${initialFailures.length} initial failures`;
            }

            // Avg Query Shift (RAG only)
            if(document.getElementById('stats-avg-query-shift')) {
                const shiftSessions = results.filter(r => r.query_shift !== undefined && r.query_shift !== null);
                if (shiftSessions.length > 0) {
                     const totalShift = shiftSessions.reduce((sum, r) => sum + Number(r.query_shift), 0);
                     const avgShift = totalShift / shiftSessions.length;
                     document.getElementById('stats-avg-query-shift').textContent = avgShift.toFixed(3);
                } else {
                     document.getElementById('stats-avg-query-shift').textContent = "0.00";
                }
            }
        }
    },

    PipelineRunner: {
        /**
         * Run a pipeline.
         * @param {object} options
         * @param {string} options.url - The URL to post to.
         * @param {FormData} options.formData - The form data to send.
         * @param {object} options.ui - UI elements: { runBtn, stopBtn, retryBtn, progressContainer, progressBar, resultsContainer, resultsBody, statusDiv, spinner }
         * @param {object} options.callbacks - { onData, onMeta, onComplete, onError }
         * @param {number} options.totalItems - Total items for progress calculation.
         * @returns {AbortController} - The controller to abort the request.
         */
        start: function(options) {
            let { totalItems } = options;
            const { url, formData, ui, callbacks, itemsData } = options;
            
            // UI Reset
            if (ui.runBtn) ui.runBtn.style.display = 'none';
            if (ui.stopBtn) {
                ui.stopBtn.style.display = 'block';
                ui.stopBtn.disabled = false;
            }
            if (ui.retryBtn) ui.retryBtn.style.display = 'none';
            
            if (ui.progressContainer) ui.progressContainer.style.display = 'block';
            if (ui.progressBar) {
                ui.progressBar.style.width = '0%';
                ui.progressBar.textContent = '0%';
            }
            
            if (ui.resultsContainer) ui.resultsContainer.style.display = 'block';
            if (ui.resultsBody) ui.resultsBody.innerHTML = '';
            
            if (ui.statusDiv) ui.statusDiv.textContent = 'Initializing pipeline...';
            if (ui.spinner) ui.spinner.style.display = 'inline-block';
            
            BenchmarkUtils.toggleConfigurationInputs(true);

            const controller = new AbortController();
            const signal = controller.signal;
            controller.pipelineId = formData.get('pipeline_id'); 

            let processedCount = 0;

            const updateStatus = () => {
                if (ui.statusDiv) {
                    let text = `Processed ${processedCount} / ${totalItems || '?'} items...`;
                    if (itemsData && itemsData.length > processedCount) {
                        const nextItem = itemsData[processedCount];
                        const qText = nextItem.question || 'Unknown';
                    }
                    ui.statusDiv.innerText = text;
                }
            };

            updateStatus();

            fetch(url, { method: 'POST', body: formData, signal: signal })
            .then(response => {
                BenchmarkUtils.processStreamedResponse(
                    response,
                    (data) => { // onData
                        if (data.is_meta) {
                             if (data.type === 'total_count') {
                                 totalItems = data.count;
                                 updateStatus();
                             }
                             if (callbacks.onMeta) callbacks.onMeta(data);
                             return;
                        }
                        
                        processedCount++;
                        if (callbacks.onData) callbacks.onData(data, processedCount);

                        // Update Progress
                        if (ui.progressBar && totalItems > 0) {
                            const progress = Math.round((processedCount / totalItems) * 100);
                            ui.progressBar.style.width = `${progress}%`;
                            ui.progressBar.textContent = `${progress}%`;
                        }
                        
                        updateStatus();
                    },
                    () => { // onComplete
                        BenchmarkUtils.toggleConfigurationInputs(false);
                        if (ui.runBtn) ui.runBtn.style.display = 'block';
                        if (ui.stopBtn) ui.stopBtn.style.display = 'none';
                        if (ui.spinner) ui.spinner.style.display = 'none';
                        if (ui.statusDiv) ui.statusDiv.textContent = 'Pipeline finished.';
                        
                        if (callbacks.onComplete) callbacks.onComplete(processedCount);
                    },
                    (error) => { // onError
                        if (error.name === 'AbortError') {
                            if (ui.statusDiv) ui.statusDiv.textContent = "Pipeline stopped by user.";
                            console.log('Pipeline stopped by user.');
                        } else {
                            console.error('Error during stream processing:', error);
                             if (ui.statusDiv) ui.statusDiv.textContent = `Error: ${error.message}`;
                        }
                        
                        BenchmarkUtils.toggleConfigurationInputs(false);
                        if (ui.runBtn) ui.runBtn.style.display = 'block';
                        if (ui.stopBtn) ui.stopBtn.style.display = 'none';
                        if (ui.spinner) ui.spinner.style.display = 'none';
                        
                        if (callbacks.onError) callbacks.onError(error);
                    },
                    signal
                );
            })
            .catch(error => {
                 if (error.name === 'AbortError') {
                    if (ui.statusDiv) ui.statusDiv.textContent = "Pipeline stopped by user.";
                 } else {
                    console.error('Error starting the pipeline:', error);
                    alert('Failed to start the pipeline.');
                    if (ui.statusDiv) ui.statusDiv.textContent = "Failed to start pipeline.";
                 }
                 BenchmarkUtils.toggleConfigurationInputs(false);
                 if (ui.runBtn) ui.runBtn.style.display = 'block';
                 if (ui.stopBtn) ui.stopBtn.style.display = 'none';
                 if (ui.spinner) ui.spinner.style.display = 'none';
            });
            
            return controller;
        }
    },

    AdhocPage: {
        init: function(config) {
            const { pipelineType, csvPrefix = 'adhoc-results', buildFormData } = config;
            
            const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
            if (!csrfToken) console.error("CSRF Token is missing or empty!");
            BenchmarkUtils.setupConfigurationHandlers();
            BenchmarkUtils.setupConfigurationActionHandlers(csrfToken, true, true);
            
            // questionsData removed - we now rely on backend streaming
            
            let pipelineController = null;
            let currentRunResults = [];
            let currentSettings = {};
            let failedItems = [];

            // UI Elements
            const runBtn = document.getElementById('run-pipeline-btn');
            const stopBtn = document.getElementById('stop-pipeline-btn');
            const retryBtn = document.getElementById('retry-btn');
            const resultsBody = document.getElementById('pipeline-results-body');
            const resultsHeader = document.getElementById('results-header-text');

            // --- Load Runs ---
            function loadSavedRuns() {
                const listRunsUrl = (pipelineType === 'vanilla_adhoc') ? BenchmarkUrls.vanillaLlmAdhoc.listRuns : BenchmarkUrls.ragAdhoc.listRuns;
                const deleteRunFunc = (runId) => (pipelineType === 'vanilla_adhoc') ? BenchmarkUrls.vanillaLlmAdhoc.deleteRun(runId) : BenchmarkUrls.ragAdhoc.deleteRun(runId);

                BenchmarkUtils.loadSavedRuns(
                    listRunsUrl,
                    loadRun,
                    (runId) => BenchmarkUtils.deleteRun(deleteRunFunc(runId), csrfToken),
                    'saved-runs-list',
                    'no-runs-message',
                    true
                );
                const selectAllCheckbox = document.getElementById('select-all-checkbox');
                if (selectAllCheckbox) selectAllCheckbox.checked = false;
            }

            // --- Load Single Run ---
            function loadRun(runId) {
                document.getElementById('pipeline-results-container').style.display = 'block';
                document.getElementById('progress-container').style.display = 'none';
                
                const url = (pipelineType === 'vanilla_adhoc') ? BenchmarkUrls.vanillaLlmAdhoc.getRun(runId) : BenchmarkUrls.ragAdhoc.getRun(runId);

                fetch(url)
                    .then(response => response.json())
                    .then(data => {
                        if (data.error) {
                            alert('Error loading run: ' + data.error);
                            return;
                        }
                        currentRunResults = data.results;
                        currentSettings = data.settings;
                        resultsHeader.textContent = `Results for: ${data.name}`;
                        
                        const settingsWhitelist = ['llm_model', 'llm_base_url', 'max_retries', 'allow_reasoning'];
                        if (pipelineType === 'rag_adhoc') {
                            settingsWhitelist.push('rag_settings', 'search_settings');
                        }
                        BenchmarkUtils.renderRunConfiguration(data.settings, settingsWhitelist);
                        
                        const runData = { name: data.name, results: data.results };
                        BenchmarkUtils.displayRunResults(runData, BenchmarkUtils.updateAdhocStatsUI, pipelineType);
                        
                        if (retryBtn) retryBtn.style.display = 'none';
                        failedItems = [];
                    })
                    .catch(error => {
                        console.error('Error loading run:', error);
                        alert(`Failed to load run data.`);
                    });
            }

            // --- Batch Delete ---
            BenchmarkUtils.setupBatchSelection(
                'saved-runs-list', 'select-all-checkbox', 'run-checkbox', 'delete-selected-btn',
                (selectedRunIds) => {
                    if (!confirm(`Are you sure you want to delete ${selectedRunIds.length} run(s)?`)) return;
                    fetch((pipelineType === 'vanilla_adhoc' ? BenchmarkUrls.vanillaLlmAdhoc.batchDeleteRuns : BenchmarkUrls.ragAdhoc.batchDeleteRuns), {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                        body: JSON.stringify({ run_ids: selectedRunIds })
                    })
                    .then(res => res.json())
                    .then(data => {
                        if (data.status === 'ok') loadSavedRuns();
                        else alert('Error deleting runs: ' + data.message);
                    })
                    .catch(err => alert('An error occurred during deletion.'));
                }
            );

            // --- Stop Pipeline ---
            function handleStopPipeline() {
                if (pipelineController) {
                    pipelineController.abort();
                }
                if (pipelineController && pipelineController.pipelineId) {
                    BenchmarkUtils.stopPipeline((pipelineType === 'vanilla_adhoc' ? BenchmarkUrls.vanillaLlmAdhoc.stopPipeline : BenchmarkUrls.ragAdhoc.stopPipeline), csrfToken, pipelineController.pipelineId);
                }
            }
            if (stopBtn) stopBtn.addEventListener('click', handleStopPipeline);
            window.addEventListener('beforeunload', handleStopPipeline);

            // --- Run Pipeline ---
            function runQAPipeline() {
                const currentPipelineId = BenchmarkUtils.generateUUID();
                let stats = { total: 0, ruleCorrect: 0, llmCorrect: 0, llmErrors: 0, agreements: 0, totalDocsUsed: 0 };
                
                // Collect Settings Snapshot for UI
                const currentLlmSettings = {
                    llm_base_url: document.getElementById('llm_base_url').value,
                    llm_api_key: document.getElementById('llm_api_key').value,
                    llm_model: document.getElementById('llm_model').value,
                };
                const snapshot = { llm_settings: currentLlmSettings };
                if (pipelineType === 'rag_adhoc') {
                    snapshot.rag_settings = { prompt_template: document.getElementById('rag_prompt_template').value };
                    const searchProviderEl = document.getElementById('search_provider');
                    const fullContentEl = document.getElementById('serper_fetch_full_content');
                    snapshot.search_settings = {
                        search_provider: searchProviderEl ? searchProviderEl.value : null,
                        serper_fetch_full_content: fullContentEl ? fullContentEl.checked : null,
                    };
                }
                currentSettings = snapshot;
                BenchmarkUtils.renderRunConfiguration(snapshot);

                // Prepare Form Data
                const formData = new FormData();
                formData.append('csrfmiddlewaretoken', csrfToken);
                formData.append('dataset_id', document.getElementById('dataset-selector').value);
                formData.append('pipeline_id', currentPipelineId);
                
                // Add common LLM fields
                formData.append('llm_base_url', currentLlmSettings.llm_base_url);
                formData.append('llm_api_key', currentLlmSettings.llm_api_key);
                formData.append('llm_model', currentLlmSettings.llm_model);

                // Add custom fields via callback
                if (buildFormData) buildFormData(formData);

                currentRunResults = [];
                failedItems = [];
                resultsHeader.textContent = "Pipeline Results";
                BenchmarkUtils.updateAdhocStatsUI(stats);

                let totalQuestions = 0; // Will be updated via stream meta
                
                // Ensure status div exists for Adhoc (keep existing logic)
                let statusDiv = document.getElementById('pipeline-status');
                if (!statusDiv) {
                    statusDiv = document.createElement('div');
                    statusDiv.id = 'pipeline-status';
                    statusDiv.className = 'mt-2 text-muted small';
                    statusDiv.style.display = 'none';
                    // Insert after progress container
                    const progressContainer = document.getElementById('progress-container');
                    if (progressContainer) {
                        progressContainer.parentNode.insertBefore(statusDiv, progressContainer.nextSibling);
                    }
                }
                statusDiv.style.display = 'block';
                statusDiv.innerText = 'Initializing...';

                const uiElements = {
                    runBtn: runBtn,
                    stopBtn: stopBtn,
                    retryBtn: retryBtn,
                    progressContainer: document.getElementById('progress-container'),
                    progressBar: document.getElementById('progress-bar'),
                    resultsContainer: document.getElementById('pipeline-results-container'),
                    resultsBody: resultsBody,
                    statusDiv: statusDiv, 
                    spinner: document.getElementById('running-spinner')
                };

                // Helper to update processing row
                let currentProcessingRow = null;
                const updateRunningRow = (questionItem) => {
                    // Remove existing
                    if (currentProcessingRow) {
                        currentProcessingRow.remove();
                        currentProcessingRow = null;
                    }
                    // Remove any other stray processing rows
                    const strays = resultsBody.querySelectorAll('.processing-row');
                    strays.forEach(row => row.remove());

                    if (questionItem) {
                        const colSpan = (pipelineType === 'rag_adhoc') ? 8 : 7;
                        currentProcessingRow = BenchmarkUtils.BenchmarkRenderer.renderProcessingRow(questionItem, resultsBody, colSpan);
                    }
                };

                pipelineController = BenchmarkUtils.PipelineRunner.start({
                    url: (pipelineType === 'vanilla_adhoc' ? BenchmarkUrls.vanillaLlmAdhoc.runPipeline : BenchmarkUrls.ragAdhoc.runPipeline),
                    formData: formData,
                    ui: uiElements,
                    totalItems: 0, // Will update based on meta
                    itemsData: null, // No longer used
                    callbacks: {
                        onMeta: (data) => {
                            if (data.type === 'total_count') {
                                totalQuestions = data.count;
                                // We can manually update totalItems in PipelineRunner context if needed, 
                                // but simpler to just handle progress bar update here if PipelineRunner doesn't support dynamic total.
                                // Actually PipelineRunner uses `totalItems` passed in `options`. 
                                // We can update the UI directly since PipelineRunner is simple.
                            } else if (data.type === 'processing_start') {
                                const questionItem = data.question;
                                updateRunningRow(questionItem);
                                
                                // Update status text
                                if (uiElements.statusDiv) {
                                    const qText = questionItem.question || 'Unknown';
                                    const processedCount = currentRunResults.length; // Approximate
                                    let text = `Processing ${processedCount + 1} / ${totalQuestions || '?'} items...`;
                                    uiElements.statusDiv.innerText = text;
                                }
                            }
                        },
                        onData: (data, processedCount) => {
                            // Remove processing row before adding result
                            if (currentProcessingRow) {
                                currentProcessingRow.remove();
                                currentProcessingRow = null;
                            }
                            // Clean up any strays just in case
                            resultsBody.querySelectorAll('.processing-row').forEach(r => r.remove());

                            currentRunResults.push(data);
                            const resultSummary = BenchmarkUtils.BenchmarkRenderer.renderResultRow(data, resultsBody, processedCount, pipelineType, false);
                            
                            if (resultSummary.rowId) {
                                data.rowId = resultSummary.rowId;
                            }

                            if (data.error && resultSummary.rowId) {
                                failedItems.push({ ...data, rowId: resultSummary.rowId });
                            }

                            stats.total++;
                            if (resultSummary.ruleCorrect) stats.ruleCorrect++;
                            if (resultSummary.llmCorrect) stats.llmCorrect++;
                            if (resultSummary.llmCorrect === null) stats.llmErrors++;
                            if (resultSummary.llmCorrect !== null && resultSummary.ruleCorrect === resultSummary.llmCorrect) {
                                stats.agreements++;
                            }
                            stats.totalDocsUsed += (data.num_docs_used || 0);
                            BenchmarkUtils.updateAdhocStatsUI(stats);
                            
                            // Update Progress Bar manually if totalQuestions is known
                            if (uiElements.progressBar && totalQuestions > 0) {
                                const progress = Math.round((stats.total / totalQuestions) * 100);
                                uiElements.progressBar.style.width = `${progress}%`;
                                uiElements.progressBar.textContent = `${progress}%`;
                            }
                        },
                        onComplete: (processedCount) => {
                             if (currentProcessingRow) currentProcessingRow.remove();
                             if (failedItems.length > 0 && retryBtn) {
                                retryBtn.style.display = 'block';
                                retryBtn.disabled = false;
                                retryBtn.innerHTML = `Retry ${failedItems.length} Failed`;
                            }
                        },
                        onError: (error) => {
                             if (currentProcessingRow) currentProcessingRow.remove();
                        }
                    }
                });

                // Show first item processing (Called AFTER start to avoid being cleared)
                // Use a small timeout to ensure it runs after the sync UI clear in start()
                setTimeout(() => {
                    if (totalQuestions > 0) {
                        updateRunningRow(0);
                    }
                }, 50);
            }
            if (runBtn) runBtn.addEventListener('click', runQAPipeline);

            // --- Retry Logic (Placeholder or Basic) ---
            if (retryBtn) {
                retryBtn.addEventListener('click', function() {
                    if (config.onRetry) {
                        config.onRetry(failedItems, resultsBody, currentRunResults);
                    } else {
                        alert("Retry logic is currently specialized per page. Please implement if needed.");
                    }
                });
            }

            // --- CSV Export ---
            const exportCsvBtn = document.getElementById('export-results-csv-btn');
            if (exportCsvBtn) {
                exportCsvBtn.addEventListener('click', function() {
                    const headers = ["#", "Question", "Model Answer", "Ground Truths", "Num Docs Used", "Rule-based Correct", "LLM Judge Correct", "Agreement"];
                    const rowMapper = (result, index) => {
                        const ruleCorrect = result.hasOwnProperty('is_correct_rule') ? result.is_correct_rule : result.rule_result;
                        const llmCorrect = result.hasOwnProperty('is_correct_llm') ? result.is_correct_llm : result.llm_result;
                        const agreement = (llmCorrect !== null && ruleCorrect === llmCorrect);
                        const groundTruths = result.ground_truths || result.answer || [];
                        return [
                            index + 1,
                            result.question || '',
                            result.answer || '',
                            Array.isArray(groundTruths) ? groundTruths.join('; ') : groundTruths,
                            result.num_docs_used || 0,
                            ruleCorrect ? 'Correct' : 'Incorrect',
                            llmCorrect === null ? 'Error' : (llmCorrect ? 'Correct' : 'Incorrect'),
                            agreement ? 'Yes' : 'No'
                        ];
                    };
                    BenchmarkUtils.exportToCSV(currentRunResults, csvPrefix, headers, rowMapper);
                });
            }

            // --- JSON Export ---
            const exportJsonBtn = document.getElementById('export-results-json-btn');
            if (exportJsonBtn) {
                exportJsonBtn.addEventListener('click', function() {
                    const exportData = {
                        settings: currentSettings,
                        results: currentRunResults
                    };
                    BenchmarkUtils.exportToJSON(exportData, csvPrefix); // Reusing csvPrefix as generic prefix
                });
            }

            // --- Initial Load ---
            loadSavedRuns();
            
            // --- Toggles ---
            document.getElementById('pipeline-results-body').addEventListener('click', function(e) {
                if (e.target && e.target.classList.contains('toggle-answers-link')) {
                    e.preventDefault();
                    const link = e.target;
                    const listItem = link.parentNode;
                    const list = listItem.parentNode;
                    const isExpanded = list.dataset.expanded === 'true';
                    const items = list.querySelectorAll('.ground-truth-item');
                    list.dataset.expanded = !isExpanded;
                    link.textContent = isExpanded ? `... Show ${list.dataset.remaining} more` : '... Show less';
                    items.forEach((item, index) => {
                        if (index >= 3) item.style.display = isExpanded ? 'none' : 'list-item';
                    });
                }
                
                // View Search Results Modal Trigger
                if (e.target && e.target.closest('.view-all-results-btn')) {
                    e.preventDefault();
                    const btn = e.target.closest('.view-all-results-btn');
                    try {
                        const results = JSON.parse(decodeURIComponent(btn.dataset.results));
                        const container = document.getElementById('modal-generic-content-container');
                        BenchmarkUtils.BenchmarkRenderer.renderModalSearchResults(results, container);
                        const modal = new bootstrap.Modal(document.getElementById('benchmarkGenericModal'));
                        modal.show();
                    } catch (err) { console.error(err); }
                }

                // View Reasoning Modal Trigger
                if (e.target && e.target.closest('.view-reasoning-btn')) {
                    e.preventDefault();
                    const btn = e.target.closest('.view-reasoning-btn');
                    const reasoning = btn.dataset.reasoning;
                    BenchmarkUtils.BenchmarkRenderer.renderPromptModal(reasoning, 'modal-generic-content-container', 'benchmarkGenericModal', 'Reasoning Chain');
                }
            });
        }
    },

    MultiTurnPage: {
        init: function(config) {
            const { 
                pipelineType, 
                csvPrefix = 'multiturn-results',
                questionsDataId = 'questions-data',
                buildFormData 
            } = config;
            
            const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
            if (!csrfToken) console.error("CSRF Token is missing or empty!");
            BenchmarkUtils.setupConfigurationHandlers();
            BenchmarkUtils.setupConfigurationActionHandlers(csrfToken, true, true);
            // questions data removed - parsing only on demand
            
            let activeSessionId = null;
            let currentPipelineResults = [];
            let pipelineController = null;

            // --- Batch Delete ---
            BenchmarkUtils.setupBatchSelection(
                'session-list', 'select-all-checkbox', 'session-checkbox', 'delete-selected-btn',
                (selectedSessionIds, selectedGroupIds) => {
                    if (selectedSessionIds.length === 0 && selectedGroupIds.length === 0) return;
                    if (!confirm(`Delete ${selectedSessionIds.length} sessions and ${selectedGroupIds.length} groups?`)) return;
                    
                    const promises = [];
                    if (selectedSessionIds.length > 0) {
                        promises.push(fetch(BenchmarkUrls.multiTurn.batchDeleteSessions, {
                            method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                            body: JSON.stringify({ session_ids: selectedSessionIds })
                        }).then(res => res.json()));
                    }
                    selectedGroupIds.forEach(gid => {
                        promises.push(fetch(BenchmarkUrls.multiTurn.deleteSessionGroup(gid), {
                            method: 'DELETE', headers: { 'X-CSRFToken': csrfToken }
                        }).then(res => res.json()));
                    });

                    Promise.all(promises).then(() => window.location.reload())
                        .catch(err => alert('Error during deletion.'));
                }, 'group-select-checkbox'
            );

            // --- Helper: Load Session ---
            function loadSession(sessionId, initialTrialId = null) {
                activeSessionId = sessionId;
                fetch(BenchmarkUrls.multiTurn.getSession(sessionId))
                    .then(res => res.json())
                    .then(data => {
                        BenchmarkUtils.MultiTurnUtils.renderSession(data.session, data.trials, { sessionTrials: [] }); 
                        window.sessionTrials = data.trials; 
                        
                        const settingsWhitelist = ['llm_model', 'llm_base_url', 'max_retries', 'allow_reasoning'];
                         if (pipelineType.includes('rag')) {
                            settingsWhitelist.push('rag_settings', 'search_settings');
                        }
                        BenchmarkUtils.renderRunConfiguration(data.session.settings_snapshot, settingsWhitelist);
                        
                        document.getElementById('session-container').style.display = 'block';
                        document.getElementById('no-session-selected').style.display = 'none';
                        
                        const delBtn = document.getElementById('delete-session-btn');
                        if (data.session.group_id) delBtn.style.display = 'none';
                        else delBtn.style.display = 'inline-block';

                        if (initialTrialId) executeTrial(initialTrialId, sessionId);
                        
                        const lastTrial = data.trials[data.trials.length - 1];
                         if (lastTrial && lastTrial.status === 'completed' && lastTrial.is_correct === false && !data.session.is_completed) {
                             if (data.trials.length < data.session.max_retries) {
                                 setTimeout(() => window.retryTrial(lastTrial.id), 1500);
                             }
                         }
                    });
            }

            // --- Helper: Execute Trial ---
            function executeTrial(trialId, sessionId) {
                 fetch(BenchmarkUrls.multiTurn.runTrial(trialId)).then(res => res.json()).then(data => {
                     if (data.error) alert(`Error in trial #${trialId}: ${data.error}`);
                     if (sessionId) loadSession(sessionId);
                 }).catch(() => {
                     console.error('Network error in trial.');
                     if (sessionId) loadSession(sessionId);
                 });
            }
            
            // --- Helper: Load Group/Run ---
            function loadRun(groupId) {
                 let loadRunUrl = BenchmarkUrls.vanillaLlmMultiTurn.loadRun(groupId);
                 if (pipelineType === 'browser_agent') loadRunUrl = BenchmarkUrls.browserAgent.loadRun(groupId);
                 else if (pipelineType === 'vanilla_agent') loadRunUrl = BenchmarkUrls.vanillaAgent.loadRun(groupId);
                 else if (pipelineType.includes('rag')) loadRunUrl = BenchmarkUrls.ragMultiTurn.loadRun(groupId);

                 fetch(loadRunUrl).then(res => res.json()).then(data => {
                     if (data.error) { alert(data.error); return; }
                     currentPipelineResults = data.results;
                     
                     // Show stats container first so updateStatsUI can find elements if they depend on visibility (though usually they don't)
                     const statsContainer = document.getElementById('statistics-container');
                     if (statsContainer) statsContainer.style.display = 'block';

                     BenchmarkUtils.MultiTurnUtils.updateStatsUI(data.results, data.group_name, (sid) => {
                         document.getElementById('session-container').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                         loadSession(sid);
                     });
                     
                     const settingsWhitelist = ['llm_model', 'llm_base_url', 'max_retries', 'allow_reasoning'];
                     if (pipelineType.includes('rag')) settingsWhitelist.push('rag_settings', 'search_settings');
                     BenchmarkUtils.renderRunConfiguration(data.settings, settingsWhitelist);
                     if (statsContainer) statsContainer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                 });
            }

            // --- Single Session Start ---
            document.getElementById('start-session-btn').addEventListener('click', function() {
                const questionSelect = document.getElementById('question-select');
                if (!questionSelect.value) { alert('Select a question.'); return; }
                
                let qData = null;
                try {
                     const questionsDataEl = document.getElementById(questionsDataId);
                     if (questionsDataEl) {
                         const questions = JSON.parse(questionsDataEl.textContent);
                         qData = questions[questionSelect.value];
                     }
                } catch (e) { console.error("Error parsing questions data", e); }
                
                if (!qData) { alert('Could not load question data.'); return; }
                
                const btn = this;
                btn.disabled = true;
                btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Starting...';
                
                let singleSessionPipelineType = pipelineType;
                // Only allow RAG mode override if we are on a RAG multi-turn page
                if (document.getElementById('rag_mode_select') && pipelineType.startsWith('rag_multi_turn')) {
                    singleSessionPipelineType = document.getElementById('rag_mode_select').value;
                }

                fetch(BenchmarkUrls.multiTurn.createSession, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrfToken},
                    body: JSON.stringify({
                        question: qData.question,
                        ground_truths: qData.answer,
                        pipeline_type: singleSessionPipelineType
                    })
                }).then(res => res.json()).then(data => {
                    if (data.error) alert(data.error);
                    else {
                        BenchmarkUtils.MultiTurnUtils.addNewSessionToList('session-list', data.session_id, qData, null);
                        loadSession(data.session_id, data.trial_id);
                    }
                }).finally(() => { btn.disabled = false; btn.innerHTML = 'Start'; });
            });

            // --- Pipeline Run ---
            document.getElementById('run-pipeline-btn').addEventListener('click', function() {
                const currentPipelineId = BenchmarkUtils.generateUUID();
                const ui = {
                    runBtn: this,
                    stopBtn: document.getElementById('stop-pipeline-btn'),
                    progressBar: document.getElementById('pipeline-progress-bar'),
                    statusDiv: document.getElementById('pipeline-status'),
                    resultsBody: null, 
                    spinner: null
                };
                
                document.getElementById('statistics-container').style.display = 'block';
                document.getElementById('stats-details-tbody').innerHTML = '';
                document.getElementById('pipeline-progress').style.display = 'block';
                document.getElementById('results-header-text').textContent = 'Live Pipeline Results';

                const currentLlmSettings = {
                    llm_base_url: document.getElementById('llm_base_url').value,
                    llm_api_key: document.getElementById('llm_api_key').value,
                    llm_model: document.getElementById('llm_model').value,
                    max_retries: document.getElementById('max_retries') ? document.getElementById('max_retries').value : null,
                };
                BenchmarkUtils.renderRunConfiguration({ llm_settings: currentLlmSettings });
                
                currentPipelineResults = [];
                
                const formData = new FormData();
                formData.append('csrfmiddlewaretoken', csrfToken);
                formData.append('dataset_id', document.getElementById('dataset-selector').value);
                formData.append('pipeline_id', currentPipelineId);
                formData.append('llm_base_url', currentLlmSettings.llm_base_url);
                formData.append('llm_api_key', currentLlmSettings.llm_api_key);
                formData.append('llm_model', currentLlmSettings.llm_model);
                if (currentLlmSettings.max_retries) formData.append('max_retries', currentLlmSettings.max_retries);
                
                if (buildFormData) buildFormData(formData);
                
                let runUrl = BenchmarkUrls.vanillaLlmMultiTurn.runPipeline;
                if (pipelineType === 'browser_agent') runUrl = BenchmarkUrls.browserAgent.runPipeline;
                else if (pipelineType === 'vanilla_agent') runUrl = BenchmarkUrls.vanillaAgent.runPipeline;
                else if (pipelineType.includes('rag')) runUrl = BenchmarkUrls.ragMultiTurn.runPipeline;

                pipelineController = BenchmarkUtils.PipelineRunner.start({
                    url: runUrl,
                    formData: formData,
                    ui: ui,
                    totalItems: 0, // Dynamic total items
                    callbacks: {
                        onMeta: (data) => {
                             if (data.type === 'info') ui.statusDiv.textContent = data.message;
                             if (data.type === 'session_created') {
                                 BenchmarkUtils.MultiTurnUtils.addNewSessionToList('session-list', data.session_id, { question: data.question }, null, data.group_id, data.group_name, 'Processing...');
                                 loadSession(data.session_id);
                             }
                             if (data.type === 'trial_started' || data.type === 'trial_completed') {
                                 if (activeSessionId && String(activeSessionId) === String(data.session_id)) loadSession(data.session_id);
                             }
                        },
                        onData: (data) => {
                             if (data.error) { ui.statusDiv.textContent = `Error: ${data.error}`; return; }
                             currentPipelineResults.push(data);
                             BenchmarkUtils.MultiTurnUtils.updateStatsUI(currentPipelineResults, data.group_name || "Current Run", (sid) => {
                                 document.getElementById('session-container').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                                 loadSession(sid);
                             });
                             BenchmarkUtils.MultiTurnUtils.addNewSessionToList('session-list', data.session_id, { question: data.question }, null, data.group_id, data.group_name, 'Finished');
                        }
                    }
                });
            });

            // --- Stop Pipeline ---
            function stopPipeline() {
                if (pipelineController) pipelineController.abort();
                if (pipelineController && pipelineController.pipelineId) {
                    let strategyData = { pipeline_id: pipelineController.pipelineId };
                     const pipelineTypeInput = document.getElementById('rag_mode_select');
                     if (pipelineTypeInput && pipelineType.includes('rag')) {
                         let s = 'no_reform';
                         if (pipelineTypeInput.value.includes('reform')) s = 'reform';
                         if (pipelineTypeInput.value.includes('no_reform')) s = 'no_reform';
                         strategyData.reformulation_strategy = s;
                     }

                     let stopUrl = BenchmarkUrls.vanillaLlmMultiTurn.stopPipeline;
                     if (pipelineType === 'browser_agent') stopUrl = BenchmarkUrls.browserAgent.stopPipeline;
                     else if (pipelineType === 'vanilla_agent') stopUrl = BenchmarkUrls.vanillaAgent.stopPipeline;
                     else if (pipelineType.includes('rag')) stopUrl = BenchmarkUrls.ragMultiTurn.stopPipeline;

                    fetch(stopUrl, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                        body: JSON.stringify(strategyData),
                        keepalive: true
                    }).catch(console.error);
                }
            }
            document.getElementById('stop-pipeline-btn').addEventListener('click', stopPipeline);
            window.addEventListener('beforeunload', stopPipeline);

            // --- List Click Handlers ---
            document.getElementById('session-list').addEventListener('click', function(e) {
                // Handle Delete Group Button
                const deleteGrp = e.target.closest('.delete-group-btn');
                if (deleteGrp) {
                    e.preventDefault(); 
                    e.stopPropagation();
                    if (confirm('Delete group?')) {
                         fetch(BenchmarkUrls.multiTurn.deleteSessionGroup(deleteGrp.dataset.groupId), { method: 'DELETE', headers: { 'X-CSRFToken': csrfToken } })
                         .then(res => res.json()).then(data => {
                             if (data.status === 'ok') { deleteGrp.closest('.list-group-item').remove(); window.location.reload(); }
                         });
                    }
                    return;
                }

                // Handle Checkboxes
                if (e.target.closest('input[type="checkbox"]')) {
                    return; 
                }

                // Handle Session Click
                const target = e.target.closest('.session-details');
                if (target) { 
                    e.preventDefault(); 
                    loadSession(target.dataset.sessionId); 
                    return;
                }
                
                // Handle Group Summary Click
                const groupSummary = e.target.closest('.group-summary');
                if (groupSummary) { 
                    // Do NOT preventDefault() to allow <details> toggle behavior
                    if (groupSummary.dataset && groupSummary.dataset.groupId) {
                        try {
                            loadRun(groupSummary.dataset.groupId); 
                        } catch (err) {
                            console.error("loadRun error:", err);
                        }
                    }
                }
            });
            
            // --- Global Retry Trial Hook ---
            window.retryTrial = function(trialId) {
                const trial = window.sessionTrials ? window.sessionTrials.find(t => t.id === trialId) : null;
                const feedback = trial ? trial.feedback : "";
                fetch(BenchmarkUrls.multiTurn.retrySession(trialId), {
                    method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrfToken},
                    body: JSON.stringify({ feedback: feedback, is_correct: false })
                }).then(res => res.json()).then(data => {
                    if (data.error) alert(data.error);
                    else {
                        loadSession(activeSessionId);
                        if (data.status === 'retrying') executeTrial(data.new_trial_id, activeSessionId);
                    }
                });
            };
            
            // --- Single Session Delete ---
            document.getElementById('delete-session-btn').addEventListener('click', function() {
                 if (activeSessionId && confirm('Delete session?')) {
                     fetch(BenchmarkUrls.multiTurn.deleteSession(activeSessionId), { method: 'DELETE', headers: { 'X-CSRFToken': csrfToken } })
                     .then(res => res.json()).then(data => {
                         if (data.status === 'ok') {
                             document.querySelector(`#session-list [data-session-id='${activeSessionId}']`).remove();
                             document.getElementById('session-container').style.display = 'none';
                             document.getElementById('no-session-selected').style.display = 'block';
                             activeSessionId = null;
                         }
                     });
                 }
            });
            
            // --- Exports ---
            if (document.getElementById('export-session-json-btn')) {
                document.getElementById('export-session-json-btn').addEventListener('click', () => {
                    if (activeSessionId) window.location.href = BenchmarkUrls.multiTurn.exportSession(activeSessionId) + '?format=json';
                });
            }
            if (document.getElementById('export-session-csv-btn')) {
                document.getElementById('export-session-csv-btn').addEventListener('click', () => {
                    if (activeSessionId) window.location.href = BenchmarkUrls.multiTurn.exportSession(activeSessionId) + '?format=csv';
                });
            }
            document.getElementById('export-results-btn').addEventListener('click', () => {
                const headers = ["#", "Question", "Final Answer", "Ground Truths", "Result", "Trials"];
                const rowMapper = (result, index) => {
                    return [
                        index + 1, result.question, result.final_answer || 'N/A', 
                        Array.isArray(result.ground_truths) ? result.ground_truths.join('; ') : result.ground_truths,
                        result.correct === true ? 'Correct' : (result.correct === false ? 'Incorrect' : 'Error'),
                        result.trials
                    ];
                };
                BenchmarkUtils.exportToCSV(currentPipelineResults, csvPrefix, headers, rowMapper);
            });
        }
    },

};