/**
 * Renderer Module - Rendering orchestration
 * Composes UI modules to render benchmark results, trials, and session displays
 *
 * Dependencies (load in order):
 *   1. core.js               - Base BenchmarkUtils namespace
 *   2. ui/components.js      - Basic component creators (badges, icons)
 *   3. ui/rendering.js       - UI rendering modules (GroundTruths, SearchResults, etc.)
 */

window.BenchmarkUtils.BenchmarkRenderer = {
    // Include basic components
    ...BenchmarkComponents,

    // === Processing Row ===
    renderProcessingRow: function(item, resultsBody, colSpan = 7) {
        const rowId = 'processing-row';
        const existing = document.getElementById(rowId);
        if (existing) existing.remove();

        const tr = BenchmarkUtils.renderTemplate('tpl-processing-row', {
            'root': { attrs: { id: rowId } },
            '.processing-col': { attrs: { colspan: colSpan } },
            '.processing-question-text': { text: item.question || 'Unknown' }
        });

        resultsBody.insertAdjacentElement('afterbegin', tr);
        return tr;
    },

    // === Ground Truths (delegate to module) ===
    renderGroundTruthsList: function(groundTruthsArray, displayLimit = 3) {
        return BenchmarkUI.GroundTruths.renderList(groundTruthsArray, displayLimit);
    },

    renderGroundTruthsBadges: function(groundTruthsArray, displayLimit = 3) {
        return BenchmarkUI.GroundTruths.renderBadges(groundTruthsArray, displayLimit);
    },

    // === Search Results (delegate to module) ===
    renderSearchResults: function(results, resultsListElement) {
        BenchmarkUI.SearchResults.render(results, resultsListElement);
    },

    renderNoSearchResults: function(resultsListElement) {
        BenchmarkUI.SearchResults.renderEmpty(resultsListElement);
    },

    renderSearchError: function(resultsListElement, errorMessage) {
        BenchmarkUI.SearchResults.renderError(resultsListElement, errorMessage);
    },

    renderModalSearchResults: function(results, container, modalId = 'benchmarkGenericModal') {
        BenchmarkUI.SearchResults.renderModal(results, container, modalId);
    },

    // === Prompt Modal ===
    renderPromptModal: function(promptContent, containerId, modalId = 'benchmarkGenericModal', title = 'RAG Prompt') {
        const modalTitle = document.getElementById(modalId + 'Label');
        if (modalTitle) modalTitle.textContent = title;

        const container = document.getElementById(containerId);
        if (!container) return;

        container.innerHTML = '';
        const pre = document.createElement('pre');
        pre.className = 'p-3 bg-light border rounded small text-secondary';
        pre.style.whiteSpace = 'pre-wrap';
        pre.textContent = promptContent;
        container.appendChild(pre);

        bootstrap.Modal.getOrCreateInstance(document.getElementById(modalId)).show();
    },

    // === Multi-Turn Result Row ===
    renderMultiTurnResultRow: function(result, index, loadSessionCallback) {
        const tr = BenchmarkUtils.renderTemplate('tpl-multiturn-result-row', {
            '.result-row': {
                onclick: loadSessionCallback ? () => loadSessionCallback(result.session_id) : null
            },
            '.idx-col': { text: index + 1 },
            '.question-col': { text: result.question },
            '.answer-col': { html: `<em>"${result.final_answer || 'N/A'}"</em>` },
            '.trials-col': { text: result.trials }
        });

        // Ground Truths
        tr.querySelector('.gt-col').appendChild(this.renderGroundTruthsList(result.ground_truths));

        // Status Badges
        const statusCol = tr.querySelector('.status-col');
        const llmVerdictDiv = statusCol.querySelector('.llm-verdict');
        const ruleVerdictDiv = statusCol.querySelector('.rule-verdict');

        if (result.is_correct_llm === true) {
            llmVerdictDiv.appendChild(this.createBadge('LLM: Correct', true));
        } else if (result.is_correct_llm === false) {
            llmVerdictDiv.appendChild(this.createBadge('LLM: Incorrect', false));
        } else {
            const span = document.createElement('span');
            span.className = 'badge bg-warning text-dark';
            span.textContent = 'LLM: Error';
            llmVerdictDiv.appendChild(span);
        }

        if (result.is_correct_rule !== undefined && result.is_correct_rule !== null) {
            ruleVerdictDiv.appendChild(this.createBadge(result.is_correct_rule ? 'Rule: Correct' : 'Rule: Incorrect', result.is_correct_rule));
        }

        return tr;
    },

    // === Tool Card (delegate to module) ===
    renderToolCard: function(type, toolName, content, options = {}) {
        return BenchmarkUI.ToolCards.render(type, toolName, content, options);
    },

    // === Message Bubble (delegate to module) ===
    createMessageBubble: function(role, content, extraClass = '', iconClass = '') {
        return BenchmarkUI.MessageBubble.create(role, content, extraClass, iconClass);
    },

    // === Agent Step (delegate to module) ===
    renderAgentStep: function(step, idx, trialId, finalAnswerText) {
        return BenchmarkUI.AgentSteps.render(step, idx, trialId, finalAnswerText);
    },

    // === Trial Rendering ===
    renderTrial: function(trial, isCompleted, trialCount, maxRetries, questionText, pipelineType = 'vanilla_llm') {
        const trialDiv = BenchmarkUtils.renderTemplate('tpl-trial-wrapper', {
            'root': { attrs: { id: `trial-${trial.id}` } },
            '.turn-label': { text: `TURN ${trial.trial_number}` }
        });

        const wrapper = trialDiv.querySelector('.trial-wrapper');
        const self = this;

        // Start polling for processing trials
        if (trial.status === 'processing') {
            // Add initial loading indicator (polling will replace it with actual content)
            const config = window.BenchmarkPipelineConfig ? window.BenchmarkPipelineConfig.get(pipelineType) : { loadingText: 'Processing...', icon: 'bi-robot' };
            const initialIndicator = this.createMessageBubble('assistant',
                `<div class="d-flex align-items-center trial-processing-indicator"><span class="spinner-border spinner-border-sm text-primary me-2"></span>${config.loadingText}</div>`,
                '', config.icon);
            wrapper.appendChild(initialIndicator);

            if (window.BenchmarkUtils && window.BenchmarkUtils.MultiTurnPage && window.BenchmarkUtils.MultiTurnPage.startPolling) {
                setTimeout(() => window.BenchmarkUtils.MultiTurnPage.startPolling(trial.id, pipelineType), 100);
            }
        }

        // For completed trials, use cached trace if available, otherwise fetch
        if (trial.status === 'completed') {
            // Check cache first
            const cachedTrace = window.BenchmarkUtils?.MultiTurnPage?.getCachedTrace?.(trial.id);

            const renderTraceSteps = (traceData) => {
                if (traceData && traceData.length > 0) {
                    const verdictContainer = wrapper.querySelector('.trial-verdict-container');
                    traceData.forEach((step, idx) => {
                        const stepEl = self.renderAgentStep(step, idx, trial.id, trial.answer);
                        if (verdictContainer) {
                            verdictContainer.insertAdjacentElement('beforebegin', stepEl);
                        } else {
                            wrapper.appendChild(stepEl);
                        }
                    });
                } else {
                    wrapper.insertBefore(
                        self.createMessageBubble('system', 'No execution trace available for this trial.', 'bg-light border-secondary border-opacity-10 shadow-none'),
                        wrapper.querySelector('.trial-verdict-container')
                    );
                }
            };

            if (cachedTrace) {
                renderTraceSteps(cachedTrace);
            } else {
                // Show loading placeholder and fetch from server
                const loadingEl = this.createMessageBubble('system', '<span class="spinner-border spinner-border-sm me-2"></span>Loading trace...', 'bg-light border-secondary border-opacity-10 shadow-none');
                wrapper.appendChild(loadingEl);

                BenchmarkAPI.get(`/benchmark/api/sessions/get_trial_trace/${trial.id}/?cursor=0`)
                    .then(data => {
                        loadingEl.remove();
                        const fetchedTrace = data.trace || [];
                        // Cache the fetched trace for future use
                        if (fetchedTrace.length > 0 && window.BenchmarkUtils?.MultiTurnPage?.setCachedTrace) {
                            window.BenchmarkUtils.MultiTurnPage.setCachedTrace(trial.id, fetchedTrace);
                        }
                        renderTraceSteps(fetchedTrace);
                    })
                    .catch(err => {
                        console.error('Failed to fetch trace:', err);
                        loadingEl.remove();
                        wrapper.insertBefore(
                            self.createMessageBubble('system', 'Failed to load execution trace.', 'bg-light border-danger border-opacity-10 shadow-none'),
                            wrapper.querySelector('.trial-verdict-container')
                        );
                    });
            }

            // Add verdict after setting up the trace (it will be inserted before verdict by the render callback)
            if (trial.feedback || trial.is_correct_rule !== undefined) {
                const verdictHtml = this.renderTrialVerdict(trial);
                if (verdictHtml) wrapper.appendChild(verdictHtml);
            }
        }

        const container = document.createElement('div');
        container.appendChild(trialDiv);

        if (trial.trial_number < trialCount) {
            const divider = BenchmarkUtils.renderTemplate('tpl-turn-divider', {
                '.turn-divider-text': { text: `End of Turn ${trial.trial_number}` }
            });
            container.appendChild(divider);
        }

        return container.children.length > 1 ? container : trialDiv;
    },

    // === Trial Verdict (delegate to module) ===
    renderTrialVerdict: function(trial) {
        return BenchmarkUI.VerdictCards.render(trial);
    },

    // === Run Configuration Display ===
    renderRunConfiguration: function(snapshot, whitelist = null) {
        const configCard = document.getElementById('run-config-card');
        const configDetails = document.getElementById('run-config-details');

        if (!configCard || !configDetails) return;

        snapshot = snapshot || {};
        configDetails.innerHTML = '';

        const addItem = (label, value, icon) => {
            const item = BenchmarkUtils.renderTemplate('tpl-run-config-item', {
                '.config-icon': { addClass: icon },
                '.config-detail-label': { text: label },
                '.config-value': { text: value, attrs: { title: value } }
            });
            configDetails.appendChild(item);
        };

        // Use centralized config
        const CONFIG_GROUPS = BenchmarkSettingsConfig.groups;

        const resolveValue = (groupObj, fieldConfig) => {
            const key = fieldConfig.key;
            if (groupObj && groupObj[key] !== undefined && groupObj[key] !== null && groupObj[key] !== '') {
                return groupObj[key];
            }
            const domId = fieldConfig.domId || key;
            const el = document.getElementById(domId);
            if (el) {
                if (el.type === 'checkbox') return el.checked;
                return el.value;
            }
            return null;
        };

        const formatValue = (val, fieldConfig) => {
            if (val === null || val === undefined || val === '') return null;
            if (fieldConfig.map) return fieldConfig.map[val] || val;
            if (fieldConfig.formatter) return fieldConfig.formatter(val);
            if (fieldConfig.type === 'boolean') {
                if (val === true || val === 'on' || val === 'true') return 'Enabled';
                return 'Disabled';
            }
            return val;
        };

        Object.keys(CONFIG_GROUPS).forEach(groupName => {
            const groupConfig = CONFIG_GROUPS[groupName];
            let groupData = null;
            for (const src of groupConfig.sources) {
                if (snapshot[src]) {
                    groupData = snapshot[src];
                    break;
                }
            }
            if (!groupData && groupName === 'llm') groupData = snapshot;

            groupConfig.fields.forEach(field => {
                if (whitelist && !whitelist.includes(field.key)) return;
                const rawVal = resolveValue(groupData, field);
                const displayVal = formatValue(rawVal, field);
                if (displayVal !== null) {
                    addItem(field.label, displayVal, field.icon);
                }
            });
        });

        configCard.style.display = configDetails.children.length > 0 ? 'block' : 'none';
    }
};
