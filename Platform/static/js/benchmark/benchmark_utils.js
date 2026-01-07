/**
 * Benchmark Utilities - Main Module
 * Refactored to use modular files for better maintainability
 * Dependencies loaded via separate script tags in proper order
 */

window.BenchmarkUtils = {
    /**
     * Renders a template by ID with data mapping.
     * @param {string} templateId - The ID of the <template> element.
     * @param {object} dataMap - Key-value pairs where keys are selectors and values are objects with text/html/src/href/class/style/attrs.
     * @returns {HTMLElement} - The rendered DOM element.
     */
    renderTemplate: function(templateId, dataMap = {}) {
        const template = document.getElementById(templateId);
        if (!template) {
            console.error(`Template not found: ${templateId}`);
            return document.createElement('div'); 
        }

        const clone = template.content.cloneNode(true);
        
        for (const [selector, actions] of Object.entries(dataMap)) {
            let elements = [];
            if (selector === 'root') {
                 // Try to find the root element(s)
                 elements = Array.from(clone.children); 
            } else {
                elements = clone.querySelectorAll(selector);
            }

            elements.forEach(el => {
                if (!el) return;
                
                if (actions.text !== undefined) el.textContent = actions.text;
                if (actions.html !== undefined) el.innerHTML = actions.html;
                if (actions.src !== undefined) el.src = actions.src;
                if (actions.href !== undefined) el.href = actions.href;
                
                if (actions.class !== undefined) el.className = actions.class;
                if (actions.addClass !== undefined) el.classList.add(...actions.addClass.split(' ').filter(c => c));
                if (actions.removeClass !== undefined) el.classList.remove(...actions.removeClass.split(' ').filter(c => c));
                
                if (actions.style !== undefined) Object.assign(el.style, actions.style);
                
                if (actions.attrs) {
                    for (const [attr, val] of Object.entries(actions.attrs)) {
                         if (val === null) el.removeAttribute(attr);
                         else el.setAttribute(attr, val);
                    }
                }
                
                // Event Handling: if 'onclick' is a function, we must attach it directly
                // Note: passing functions in dataMap works because we are in the same JS context
                if (typeof actions.onclick === 'function') {
                    el.onclick = actions.onclick;
                }
            });
        }
        
        // If the clone has multiple top-level elements, return a DocumentFragment,
        // otherwise return the single element. 
        // Most templates should have a single root for easier handling.
        return clone.children.length === 1 ? clone.firstElementChild : clone;
    },

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
            
            
            search_provider: document.getElementById('search_provider') ? document.getElementById('search_provider').value : '',
            search_limit: document.getElementById('search_limit') ? document.getElementById('search_limit').value : '',
            serper_api_key: document.getElementById('serper_api_key') ? document.getElementById('serper_api_key').value : '',
            serper_fetch_full_content: document.getElementById('serper_fetch_full_content') ? document.getElementById('serper_fetch_full_content').checked : false,
            
            agent_memory_type: document.getElementById('agent_memory_type') ? document.getElementById('agent_memory_type').value : '',
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
            
            
            search_provider: document.getElementById('search_provider') ? document.getElementById('search_provider').value : '',
            search_limit: document.getElementById('search_limit') ? document.getElementById('search_limit').value : '',
            serper_api_key: document.getElementById('serper_api_key') ? document.getElementById('serper_api_key').value : '',
            serper_fetch_full_content: document.getElementById('serper_fetch_full_content') ? document.getElementById('serper_fetch_full_content').checked : false,
            
            agent_memory_type: document.getElementById('agent_memory_type') ? document.getElementById('agent_memory_type').value : '',
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


                    
                    // Apply Search settings
                    if (document.getElementById('search_provider') && data.search_provider) {
                        document.getElementById('search_provider').value = data.search_provider;
                        // Trigger change to update UI for serper_api_key container visibility
                        document.getElementById('search_provider').dispatchEvent(new Event('change'));
                    }
                    if (document.getElementById('search_limit') && data.search_limit) document.getElementById('search_limit').value = data.search_limit;
                    if (document.getElementById('serper_api_key') && data.serper_api_key) document.getElementById('serper_api_key').value = data.serper_api_key;
                    if (document.getElementById('serper_fetch_full_content') && data.serper_fetch_full_content !== undefined) document.getElementById('serper_fetch_full_content').checked = data.serper_fetch_full_content;

                    // Apply Agent Settings
                    if (document.getElementById('agent_memory_type') && data.agent_memory_type) document.getElementById('agent_memory_type').value = data.agent_memory_type;

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
            
            'search_provider', 'search_limit', 'serper_api_key', 'serper_fetch_full_content',
            'agent_memory_type'
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

                // Unified settings object
                const settingsData = {
                    // LLM
                    llm_base_url: document.getElementById('llm_base_url').value,
                    llm_api_key: document.getElementById('llm_api_key').value,
                    llm_model: document.getElementById('llm_model').value,
                    max_retries: document.getElementById('max_retries') ? document.getElementById('max_retries').value : 3,
                    allow_reasoning: document.getElementById('allow_reasoning') ? document.getElementById('allow_reasoning').checked : false,
                    temperature: document.getElementById('temperature') ? document.getElementById('temperature').value : 0.0,
                    top_p: document.getElementById('top_p') ? document.getElementById('top_p').value : 1.0,
                    max_tokens: document.getElementById('max_tokens') ? document.getElementById('max_tokens').value : null,
                    
                    // Search
                    search_provider: document.getElementById('search_provider') ? document.getElementById('search_provider').value : 'serper',
                    search_limit: document.getElementById('search_limit') ? document.getElementById('search_limit').value : 5,
                    serper_api_key: document.getElementById('serper_api_key') ? document.getElementById('serper_api_key').value : '',
                    serper_fetch_full_content: document.getElementById('serper_fetch_full_content') ? document.getElementById('serper_fetch_full_content').checked : false,
                    
                    // Agent
                    agent_memory_type: document.getElementById('agent_memory_type') ? document.getElementById('agent_memory_type').value : 'naive'
                };

                fetch(BenchmarkUrls.saveSettings, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrfToken},
                    body: JSON.stringify(settingsData)
                })
                .then(r => r.json())
                .then(resData => {
                    if (resData.status === 'ok') {
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
        return window.BenchmarkHelpers.generateUUID();
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
     * @param {Function} func - The function to debounce.
     * @param {number} wait - The delay in milliseconds.
     * @returns {Function} The debounced function.
     */
    debounce: function(func, wait) {
        return window.BenchmarkHelpers.debounce(func, wait);
    },

    /**
     * Export data to CSV.
     * @param {Array} data - Array of data objects.
     * @param {string} filenamePrefix - Prefix for the filename.
     * @param {Array} headers - Array of header strings.
     * @param {Function} rowMapper - Function that takes a data item and index, returns an array of cell values.
     */
    exportToCSV: function(data, filenamePrefix, headers, rowMapper) {
        return window.BenchmarkExport.exportToCSV(data, filenamePrefix, headers, rowMapper);
    },

    /**
     * Export data to JSON.
     * @param {Array} data - Array of data objects.
     * @param {string} filenamePrefix - Prefix for the filename.
     */
    exportToJSON: function(data, filenamePrefix) {
        return window.BenchmarkExport.exportToJSON(data, filenamePrefix);
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
        return window.BenchmarkHelpers.processStreamedResponse(response, onData, onComplete, onError, abortSignal);
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
                noSessionSelectedId = 'no-session-selected',
                pipelineType = 'vanilla_llm'
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
            gtContainer.appendChild(BenchmarkUtils.BenchmarkRenderer.renderGroundTruthsList(session.ground_truths));

            const trialsContainer = document.getElementById('trials-container');
            trialsContainer.innerHTML = '';
            trials.forEach(trial => {
                trialsContainer.appendChild(BenchmarkUtils.BenchmarkRenderer.renderTrial(trial, session.is_completed, trials.length, session.max_retries, session.question, pipelineType));
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
            const existingDetails = document.querySelector(`.session-details[data-session-id="${sessionId}"]`);
            
            if (existingCheckbox || existingDetails) {
                const sessionDetails = existingDetails || document.querySelector(`.session-details[data-session-id="${sessionId}"]`);
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
            
            let checkboxHtml = '';
            let detailsMargin = 'ms-3';
            
            if (!groupId) {
                checkboxHtml = `<input class="form-check-input session-checkbox" type="checkbox" value="${sessionId}" data-session-id="${sessionId}">`;
            } else {
                detailsMargin = '';
            }

            newSessionItem.innerHTML = `
                ${checkboxHtml}
                <div class="${detailsMargin} flex-grow-1 session-details" data-session-id="${sessionId}" style="cursor: pointer;">
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

            // Rule-based Accuracy & Coherence
            const correctRule = results.filter(r => r.is_correct_rule === true).length;
            const ruleAccuracy = (correctRule / total) * 100;
            if(document.getElementById('stats-rule-accuracy')) document.getElementById('stats-rule-accuracy').textContent = `${ruleAccuracy.toFixed(2)}%`;

            const avgCoherence = results.reduce((sum, r) => sum + (r.coherence || 0), 0) / total;
            if(document.getElementById('stats-coherence')) document.getElementById('stats-coherence').textContent = `${(avgCoherence * 100).toFixed(2)}%`;

            // Average trials
            const totalTrials = results.reduce((sum, r) => sum + (r.trials || 0), 0);
            const avgTrials = totalTrials / total;
            if(document.getElementById('stats-avg-trials-all')) document.getElementById('stats-avg-trials-all').textContent = avgTrials.toFixed(2);

            const successResults = results.filter(r => r.correct === true);
            const successTrials = successResults.reduce((sum, r) => sum + (r.trials || 0), 0);
            const avgSuccessTrials = successResults.length > 0 ? successTrials / successResults.length : 0;
            if(document.getElementById('stats-avg-trials-success')) document.getElementById('stats-avg-trials-success').textContent = avgSuccessTrials.toFixed(2);

            // First try success
            const firstTrySuccess = results.filter(r => r.initial_correct === true).length;
            const firstTryRate = (firstTrySuccess / total) * 100;
            if(document.getElementById('stats-first-try-success')) document.getElementById('stats-first-try-success').textContent = `${firstTryRate.toFixed(2)}%`;

            // Correction Gain
            const correctionGain = accuracy - firstTryRate;
            if(document.getElementById('stats-correction-gain')) document.getElementById('stats-correction-gain').textContent = `+${correctionGain.toFixed(2)}%`;

            // Give up rate (max retries reached and still incorrect)
            const giveUp = results.filter(r => r.correct === false).length;
            const giveUpRate = (giveUp / total) * 100;
            if(document.getElementById('stats-give-up-rate')) document.getElementById('stats-give-up-rate').textContent = `${giveUpRate.toFixed(2)}%`;

            // Self-Correction Rate
            const initialFailures = results.filter(r => r.initial_correct === false);
            const selfCorrected = initialFailures.filter(r => r.correct === true);
            const selfCorrectionRate = initialFailures.length > 0 ? (selfCorrected.length / initialFailures.length) * 100 : 0;
            if(document.getElementById('stats-self-correction-rate')) {
                document.getElementById('stats-self-correction-rate').textContent = `${selfCorrectionRate.toFixed(2)}%`;
                document.getElementById('stats-self-correction-rate').title = `${selfCorrected.length} corrected out of ${initialFailures.length} initial failures`;
            }

            // Error Rate
            const errorRate = (error / total) * 100;
            if(document.getElementById('stats-error-rate')) document.getElementById('stats-error-rate').textContent = `${errorRate.toFixed(2)}%`;

            // Baseline-Specific Metrics Injection
            const specificContainer = document.getElementById('specific-metrics-container');
            const specificRow = document.getElementById('specific-metrics-row');
            if (specificContainer && specificRow) {
                specificRow.innerHTML = '';
                let hasSpecific = false;

                // Avg Search Count (RAG only)
                const searchCountSessions = results.filter(r => r.search_count !== undefined);
                if (searchCountSessions.length > 0) {
                    const totalSearch = searchCountSessions.reduce((sum, r) => sum + Number(r.search_count), 0);
                    const avgSearch = totalSearch / searchCountSessions.length;
                    
                    const col = document.createElement('div');
                    col.className = 'col-lg-3 col-md-6';
                    col.innerHTML = `
                       <div class="card text-center border-light shadow-sm h-100">
                           <div class="card-body py-3">
                               <h4 class="card-title mb-1">${avgSearch.toFixed(2)}</h4>
                               <p class="card-text small mb-0 text-muted">Avg. Search Queries</p>
                           </div>
                       </div>`;
                    specificRow.appendChild(col);
                    hasSpecific = true;
                }

                // Avg Query Shift (RAG only)
                const shiftSessions = results.filter(r => r.query_shift !== undefined && r.query_shift !== null);
                if (shiftSessions.length > 0) {
                     const totalShift = shiftSessions.reduce((sum, r) => sum + Number(r.query_shift), 0);
                     const avgShift = totalShift / shiftSessions.length;
                     
                     const col = document.createElement('div');
                     col.className = 'col-lg-3 col-md-6';
                     col.innerHTML = `
                        <div class="card text-center border-light shadow-sm h-100">
                            <div class="card-body py-3">
                                <h4 class="card-title mb-1">${avgShift.toFixed(3)}</h4>
                                <p class="card-text small mb-0 text-muted">Avg. Query Shift (Dist)</p>
                            </div>
                        </div>`;
                     specificRow.appendChild(col);
                     hasSpecific = true;
                     
                     // Keep hidden element updated for compatibility
                     if(document.getElementById('stats-avg-query-shift')) document.getElementById('stats-avg-query-shift').textContent = avgShift.toFixed(3);
                }

                // Stubbornness Score (New)
                const stubbornSessions = results.filter(r => r.stubborn_score !== undefined && r.stubborn_score !== null && r.stubborn_score > 0);
                if (stubbornSessions.length > 0) {
                     const totalStub = stubbornSessions.reduce((sum, r) => sum + Number(r.stubborn_score), 0);
                     const avgStub = totalStub / stubbornSessions.length;
                     
                     if (document.getElementById('stats-stubbornness-score')) {
                         document.getElementById('stats-stubbornness-score').textContent = `${(avgStub * 100).toFixed(2)}%`;
                     }

                     const col = document.createElement('div');
                     col.className = 'col-lg-3 col-md-6';
                     col.innerHTML = `
                        <div class="card text-center border-light shadow-sm h-100">
                            <div class="card-body py-3">
                                <h4 class="card-title mb-1">${(avgStub * 100).toFixed(2)}%</h4>
                                <p class="card-text small mb-0 text-muted">Stubbornness Index</p>
                            </div>
                        </div>`;
                     specificRow.appendChild(col);
                     hasSpecific = true;
                }

                specificContainer.style.display = hasSpecific ? 'block' : 'none';
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
            let { totalItems, initialProcessedCount = 0 } = options;
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
                // Initialize progress bar based on initial count if total is known, else 0
                const initialProgress = (totalItems > 0) ? Math.round((initialProcessedCount / totalItems) * 100) : 0;
                ui.progressBar.style.width = `${initialProgress}%`;
                ui.progressBar.textContent = `${initialProgress}%`;
            }
            
            if (ui.resultsContainer) ui.resultsContainer.style.display = 'block';
            if (ui.resultsBody) ui.resultsBody.innerHTML = '';
            
            if (ui.statusDiv) ui.statusDiv.textContent = 'Initializing pipeline...';
            if (ui.spinner) ui.spinner.style.display = 'inline-block';
            
            BenchmarkUtils.toggleConfigurationInputs(true);

            const controller = new AbortController();
            const signal = controller.signal;
            controller.pipelineId = formData.get('pipeline_id'); 

            let processedCount = initialProcessedCount;

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
    }
};
