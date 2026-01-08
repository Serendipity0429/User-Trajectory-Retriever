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

        if (result.correct === true) {
            llmVerdictDiv.appendChild(this.createBadge('LLM: Correct', true));
        } else if (result.correct === false) {
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

        let trace = trial.trace || [];
        if (typeof trace === 'string') {
            try { trace = JSON.parse(trace); } catch (e) { trace = []; }
        }

        if (trace.length === 0 && trial.full_response && pipelineType.includes('agent')) {
            try { trace = JSON.parse(trial.full_response); } catch (e) { }
        }

        // Start polling for processing trials - polling will handle the indicator
        if (trial.status === 'processing') {
            if (window.BenchmarkUtils && window.BenchmarkUtils.MultiTurnPage && window.BenchmarkUtils.MultiTurnPage.startPolling) {
                setTimeout(() => window.BenchmarkUtils.MultiTurnPage.startPolling(trial.id, pipelineType), 100);
            }
        }

        if (trace && trace.length > 0) {
            trace.forEach((step, idx) => {
                const stepEl = this.renderAgentStep(step, idx, trial.id, trial.answer);
                if (typeof stepEl === 'string') {
                    wrapper.insertAdjacentHTML('beforeend', stepEl);
                } else {
                    wrapper.appendChild(stepEl);
                }
            });
        } else if (trial.status !== 'processing') {
            // Only show "no trace" message if not processing (polling will show indicator)
            wrapper.appendChild(this.createMessageBubble('system', 'No execution trace available for this trial.', 'bg-light border-secondary border-opacity-10 shadow-none'));
        }

        if (trial.status === 'completed' && (trial.feedback || trial.is_correct_rule !== undefined)) {
            const verdictHtml = this.renderTrialVerdict(trial);
            if (verdictHtml) wrapper.appendChild(verdictHtml);
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

        const CONFIG_GROUPS = {
            'llm': {
                sources: ['llm', 'llm_settings'],
                fields: [
                    { key: 'llm_model', label: 'LLM Model', icon: 'bi-cpu' },
                    { key: 'max_retries', label: 'Max Retries', icon: 'bi-arrow-repeat' },
                    { key: 'temperature', label: 'Temperature', icon: 'bi-thermometer-half' },
                    { key: 'top_p', label: 'Top P', icon: 'bi-percent' },
                    { key: 'max_tokens', label: 'Max Tokens', icon: 'bi-text-paragraph' },
                    { key: 'allow_reasoning', label: 'Reasoning', icon: 'bi-lightbulb', type: 'boolean' },
                    { key: 'llm_base_url', label: 'Base URL', icon: 'bi-link-45deg' }
                ]
            },
            'search': {
                sources: ['search', 'search_settings'],
                fields: [
                    { key: 'search_provider', label: 'Search Provider', icon: 'bi-globe', formatter: val => val === 'mcp' ? 'MCP Server' : (val === 'serper' ? 'Serper API' : val) },
                    { key: 'search_limit', label: 'Top-K Limit', icon: 'bi-list-ol' },
                    { key: 'serper_fetch_full_content', label: 'Full Content', icon: 'bi-file-text', type: 'boolean', domId: 'serper_fetch_full_content' }
                ]
            },
            'agent': {
                sources: ['agent', 'agent_config'],
                fields: [
                    { key: 'memory_type', label: 'Agent Memory', icon: 'bi-memory', map: { 'naive': 'Naive Memory', 'mem0': 'Mem0 Memory', 'reme': 'ReMe Memory' }, domId: 'agent_memory_type' },
                    { key: 'model_name', label: 'Agent Model', icon: 'bi-robot' }
                ]
            }
        };

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
