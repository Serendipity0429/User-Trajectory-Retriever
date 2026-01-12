/**
 * Settings management and configuration handlers
 * Handles LLM connection testing, settings save/restore, and UI configuration
 */

window.BenchmarkSettings = window.BenchmarkSettings || {};

/**
 * Test the LLM connection.
 * @param {string} url - The URL to the test connection view.
 * @param {object} data - The data to send (llm_base_url, llm_api_key).
 * @param {string} resultDivId - The ID of the div to display results.
 * @param {string} btnId - The ID of the test button.
 */
window.BenchmarkSettings.testConnection = function(url, data, resultDivId, btnId) {
    const resultDiv = document.getElementById(resultDivId);
    const btn = document.getElementById(btnId);
    const originalText = btn.innerHTML;

    resultDiv.innerHTML = '';
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Testing...';

    BenchmarkAPI.post(url, data)
        .then(body => {
            resultDiv.innerHTML = `<span class="text-success small fw-semibold"><i class="bi bi-check-circle-fill me-1"></i>${body.message}</span>`;

            // If models are returned, enable datalist for both model inputs
            if (body.models && Array.isArray(body.models) && body.models.length > 0) {
                const modelInputIds = ['llm_model', 'llm_judge_model'];

                modelInputIds.forEach(inputId => {
                    let modelInput = document.getElementById(inputId);
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

                        const datalistId = `${inputId}_datalist`;
                        let datalist = document.getElementById(datalistId);

                        if (!datalist) {
                            datalist = document.createElement('datalist');
                            datalist.id = datalistId;
                            modelInput.parentNode.appendChild(datalist);
                            modelInput.setAttribute('list', datalistId);
                        } else {
                            datalist.innerHTML = '';
                        }

                        body.models.sort();
                        body.models.forEach(modelName => {
                            const option = document.createElement('option');
                            option.value = modelName;
                            datalist.appendChild(option);
                        });
                    }
                });
            }
        })
        .catch(error => {
            const errorMsg = error.error || 'An error occurred while testing the connection.';
            resultDiv.innerHTML = `<span class="text-danger small fw-semibold"><i class="bi bi-exclamation-circle-fill me-1"></i>${errorMsg}</span>`;
            console.error('Error:', error);
        })
        .finally(() => {
            btn.disabled = false;
            btn.innerHTML = originalText;
        });
};

/**
 * List of settings field IDs for state tracking
 */
window.BenchmarkSettings.SETTINGS_FIELDS = [
    'llm_base_url', 'llm_api_key', 'llm_model', 'llm_judge_model', 'max_retries', 'allow_reasoning',
    'temperature', 'top_p', 'max_tokens',
    'search_provider', 'search_limit', 'serper_api_key', 'serper_fetch_full_content',
    'agent_memory_type', 'embedding_model', 'agent_max_iters'
];

/**
 * Get current settings values from form inputs
 * @returns {object} Current settings state
 */
window.BenchmarkSettings.getCurrentSettings = function() {
    const settings = {};
    this.SETTINGS_FIELDS.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            settings[id] = el.type === 'checkbox' ? el.checked : el.value;
        } else {
            settings[id] = '';
        }
    });
    return settings;
};

/**
 * Captures the current state of settings inputs.
 */
window.BenchmarkSettings.saveInitialSettings = function() {
    BenchmarkState.config.settingsInitialState = this.getCurrentSettings();
    BenchmarkState.config.hasUnsavedChanges = false;
    const alertEl = document.getElementById('unsaved-changes-alert');
    if (alertEl) alertEl.style.display = 'none';
};

/**
 * Checks for unsaved changes by comparing current values with initial state.
 */
window.BenchmarkSettings.checkUnsavedChanges = function() {
    const initial = BenchmarkState.config.settingsInitialState || {};
    const current = this.getCurrentSettings();

    let hasChanges = false;
    for (const key in current) {
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
};

/**
 * Restore default settings from .env via server.
 */
window.BenchmarkSettings.restoreDefaults = function() {
    fetch(BenchmarkUrls.getDefaultSettings)
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                alert('Error loading default settings: ' + data.error);
                return;
            }

            // Apply all settings
            const fieldMappings = {
                'llm_base_url': 'llm_base_url',
                'llm_api_key': 'llm_api_key',
                'llm_model': 'llm_model',
                'llm_judge_model': 'llm_judge_model',
                'max_retries': 'max_retries',
                'allow_reasoning': 'allow_reasoning',
                'temperature': 'temperature',
                'top_p': 'top_p',
                'max_tokens': 'max_tokens',
                'search_provider': 'search_provider',
                'search_limit': 'search_limit',
                'serper_api_key': 'serper_api_key',
                'serper_fetch_full_content': 'serper_fetch_full_content',
                'agent_memory_type': 'agent_memory_type',
                'embedding_model': 'embedding_model',
                'agent_max_iters': 'agent_max_iters'
            };

            for (const [elementId, dataKey] of Object.entries(fieldMappings)) {
                const el = document.getElementById(elementId);
                if (el && data[dataKey] !== undefined) {
                    if (el.type === 'checkbox') {
                        el.checked = data[dataKey];
                    } else {
                        el.value = data[dataKey];
                    }
                }
            }

            // Trigger search provider change to update UI
            const searchProvider = document.getElementById('search_provider');
            if (searchProvider) {
                searchProvider.dispatchEvent(new Event('change'));
            }

            // Update lastSavedBaseUrl and test connection
            const baseUrlEl = document.getElementById('llm_base_url');
            if (baseUrlEl) {
                BenchmarkState.config.lastSavedBaseUrl = baseUrlEl.value;
                BenchmarkSettings.testConnection(
                    BenchmarkUrls.testLlmConnection,
                    {
                        llm_base_url: baseUrlEl.value,
                        llm_api_key: document.getElementById('llm_api_key').value,
                        llm_model: document.getElementById('llm_model').value
                    },
                    'test-connection-result',
                    'test-connection-btn'
                );
            }
            BenchmarkSettings.saveInitialSettings();
        })
        .catch(error => {
            console.error('Error restoring defaults:', error);
            alert('Failed to restore defaults.');
        });
};

/**
 * Setup common configuration UI handlers (toggles, visibility).
 */
window.BenchmarkSettings.setupConfigurationHandlers = function() {
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
            serperApiKeyContainer.style.display = this.value === 'serper' ? 'block' : 'none';
        });
        searchProvider.dispatchEvent(new Event('change'));
    }
};

/**
 * Validates the search limit input.
 * @returns {boolean} True if valid, false otherwise.
 */
window.BenchmarkSettings.validateSearchLimit = function() {
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
};

/**
 * Setup event handlers for configuration actions.
 */
window.BenchmarkSettings.setupConfigurationActionHandlers = function() {
    const self = this;

    // LLM Settings
    const testConnection = function() {
        const data = {
            llm_base_url: document.getElementById('llm_base_url').value,
            llm_api_key: document.getElementById('llm_api_key').value,
            llm_model: document.getElementById('llm_model').value
        };
        BenchmarkSettings.testConnection(BenchmarkUrls.testLlmConnection, data, 'test-connection-result', 'test-connection-btn');
    };

    const testBtn = document.getElementById('test-connection-btn');
    if (testBtn) {
        testBtn.addEventListener('click', testConnection);
    }

    // Trigger on page load
    testConnection();
    BenchmarkSettings.saveInitialSettings();

    // Search Limit Validation
    const searchLimitInput = document.getElementById('search_limit');
    if (searchLimitInput) {
        searchLimitInput.addEventListener('input', self.validateSearchLimit);
        searchLimitInput.addEventListener('change', self.validateSearchLimit);
    }

    // Check unsaved changes on input
    const checkChanges = () => self.checkUnsavedChanges();
    self.SETTINGS_FIELDS.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener('input', checkChanges);
            el.addEventListener('change', checkChanges);
        }
    });

    // Global Reset Button
    const globalRestoreBtn = document.getElementById('global-restore-btn');
    if (globalRestoreBtn) {
        globalRestoreBtn.addEventListener('click', function() {
            if (confirm('Are you sure you want to restore ALL settings to their defaults?')) {
                BenchmarkSettings.restoreDefaults();
            }
        });
    }

    // Global Save All Handler
    const saveAllBtn = document.getElementById('save-all-settings-btn');
    if (saveAllBtn) {
        saveAllBtn.addEventListener('click', function() {
            if (!self.validateSearchLimit()) {
                alert('Please correct the errors in the Search Settings tab.');
                return;
            }

            const btn = this;
            const originalText = btn.innerHTML;
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Saving...';

            // Unified settings object
            const settingsData = {
                llm_base_url: document.getElementById('llm_base_url').value,
                llm_api_key: document.getElementById('llm_api_key').value,
                llm_model: document.getElementById('llm_model').value,
                llm_judge_model: document.getElementById('llm_judge_model') ? document.getElementById('llm_judge_model').value : '',
                max_retries: document.getElementById('max_retries') ? document.getElementById('max_retries').value : 3,
                allow_reasoning: document.getElementById('allow_reasoning') ? document.getElementById('allow_reasoning').checked : false,
                temperature: document.getElementById('temperature') ? document.getElementById('temperature').value : 0.0,
                top_p: document.getElementById('top_p') ? document.getElementById('top_p').value : 1.0,
                max_tokens: document.getElementById('max_tokens') ? document.getElementById('max_tokens').value : null,
                search_provider: document.getElementById('search_provider') ? document.getElementById('search_provider').value : 'serper',
                search_limit: document.getElementById('search_limit') ? document.getElementById('search_limit').value : 5,
                serper_api_key: document.getElementById('serper_api_key') ? document.getElementById('serper_api_key').value : '',
                serper_fetch_full_content: document.getElementById('serper_fetch_full_content') ? document.getElementById('serper_fetch_full_content').checked : false,
                agent_memory_type: document.getElementById('agent_memory_type') ? document.getElementById('agent_memory_type').value : 'naive',
                embedding_model: document.getElementById('embedding_model') ? document.getElementById('embedding_model').value : '',
                agent_max_iters: document.getElementById('agent_max_iters') ? document.getElementById('agent_max_iters').value : 30
            };

            BenchmarkAPI.post(BenchmarkUrls.saveSettings, settingsData)
            .then(resData => {
                if (resData.status === 'ok') {
                    btn.innerHTML = '<i class="bi bi-check-lg me-1"></i> Saved!';
                    btn.classList.remove('btn-primary');
                    btn.classList.add('btn-success');
                    BenchmarkState.config.hasUnsavedChanges = false;
                    BenchmarkSettings.saveInitialSettings();
                    const alertEl = document.getElementById('unsaved-changes-alert');
                    if (alertEl) alertEl.style.display = 'none';

                    setTimeout(() => {
                        btn.innerHTML = originalText;
                        btn.classList.remove('btn-success');
                        btn.classList.add('btn-primary');
                        btn.disabled = false;
                    }, 1500);

                    // Re-test connection if base URL changed
                    if (settingsData.llm_base_url !== BenchmarkState.config.lastSavedBaseUrl) {
                        testConnection();
                        BenchmarkState.config.lastSavedBaseUrl = settingsData.llm_base_url;
                    }
                } else {
                    alert('Error saving settings: ' + (resData.message || 'Unknown error'));
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
};

/**
 * Enable or disable configuration inputs.
 * @param {boolean} disabled - Whether to disable the inputs.
 */
window.BenchmarkSettings.toggleConfigurationInputs = function(disabled) {
    const inputs = document.querySelectorAll('#settingsModal input, #settingsModal select, #settingsModal textarea, #dataset-selector');
    inputs.forEach(input => {
        input.disabled = disabled;
    });
    const saveBtn = document.getElementById('save-all-settings-btn');
    if (saveBtn) saveBtn.disabled = disabled;

    const settingsBtn = document.querySelector('button[data-bs-target="#settingsModal"]');
    if (settingsBtn) settingsBtn.disabled = disabled;
};
