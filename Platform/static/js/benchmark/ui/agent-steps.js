/**
 * Agent Steps UI Component
 * Renders agent execution steps: thoughts, actions, observations, system prompts, user inputs
 */

window.BenchmarkUI.AgentSteps = {
    _parseContent: function(str) {
        if (typeof str !== 'string') return str;
        try { return JSON.parse(str); } catch (e) { return null; }
    },

    /**
     * Render a single agent step based on its type
     */
    render: function(step, idx, trialId, finalAnswerText) {
        const role = step.role || 'assistant';
        const type = step.step_type || 'text';
        let content = step.content || '';
        const name = step.name || '';

        if (type === 'thought') return this._renderThought(content, trialId, idx);
        if (type === 'action') return this._renderAction(content);
        if (type === 'observation') return this._renderObservation(content, name, finalAnswerText);
        if (role === 'system') return this._renderSystemPrompt(content);
        if (role === 'user') return this._renderUserInput(content);

        if (typeof content === 'string') {
            content = BenchmarkHelpers.escapeHtml(content).replace(/\n/g, '<br>');
        }
        return BenchmarkUI.MessageBubble.create('assistant', content, '', 'bi-chat-left-dots');
    },

    _renderThought: function(content, trialId, idx) {
        const tId = `thought-${trialId}-${idx}`;
        const thoughtElement = BenchmarkUtils.renderTemplate('tpl-agent-thought', {
            '.collapse-btn': { attrs: { 'data-bs-target': `#${tId}` } },
            '.collapse-target': { attrs: { id: tId } },
            '.thinking-content': { text: content }
        });
        return BenchmarkUI.MessageBubble.create('assistant', thoughtElement.outerHTML, 'bg-transparent border-0 shadow-none p-0', 'bi-robot');
    },

    _renderAction: function(content) {
        // Special case: Search Query text format
        if (typeof content === 'string' && content.trim().startsWith('Search Query:')) {
            const element = BenchmarkUtils.renderTemplate('tpl-agent-action', {
                '.agent-badge-text': { addClass: 'bg-info bg-opacity-10 text-info border-info border-opacity-25' },
                '.badge-icon': { addClass: 'bi-search' },
                '.badge-label': { text: 'Search Query' },
                '.tool-content': { text: content }
            });
            return BenchmarkUI.MessageBubble.create('assistant', element.outerHTML, 'bg-transparent border-0 shadow-none p-0', 'bi-gear');
        }

        // Parse structured tool data
        let toolName = null;
        let toolInput = null;
        try {
            const toolData = (typeof content === 'string') ? JSON.parse(content) : content;
            if (toolData && toolData.name && toolData.input) {
                toolName = toolData.name;
                toolInput = toolData.input;
            }
        } catch (e) { }

        return BenchmarkUI.ToolCards.render('action', toolName, toolInput || content);
    },

    _renderObservation: function(content, name, finalAnswerText) {
        let parsedData = null;
        let isSearch = false;
        let isFinalAnswer = false;
        let displayContent = content;
        let toolName = '';

        // Step 1: Parse content - handle both string and object inputs
        if (typeof content === 'string') {
            parsedData = this._parseContent(content);
        } else if (content && typeof content === 'object') {
            parsedData = content;
        }

        // Step 2: Extract tool name and output from structured JSON {name, output}
        if (parsedData && typeof parsedData === 'object' && !Array.isArray(parsedData)) {
            if (parsedData.name) {
                toolName = parsedData.name;
            }
            if (parsedData.output !== undefined) {
                displayContent = parsedData.output;
                if (typeof displayContent === 'string') {
                    const outputParsed = this._parseContent(displayContent);
                    if (outputParsed) parsedData = outputParsed;
                } else {
                    parsedData = displayContent;
                }
            }
        }

        // Step 3: Fallback to step.name if no tool name extracted
        if (!toolName && name) {
            toolName = name;
        }

        // Step 4: Detect search results
        if (toolName === 'web_search_tool' || (parsedData && Array.isArray(parsedData) && parsedData.length > 0 && parsedData[0].title)) {
            isSearch = true;
        }

        // Handle "Search Results:" prefix format
        if (typeof content === 'string' && content.startsWith('Search Results:')) {
            isSearch = true;
            displayContent = content.replace('Search Results:', '').trim();
            parsedData = this._parseSearchResults(displayContent);
        }

        // Step 5: Detect final answer
        if (toolName === 'answer_question' ||
            (typeof displayContent === 'string' && displayContent.includes('Answer submitted successfully'))) {
            isFinalAnswer = true;
        }

        // Handle Final Answer
        if (isFinalAnswer) {
            const finalAnswer = BenchmarkUtils.renderTemplate('tpl-agent-final-answer', {
                '.response-text': { text: finalAnswerText || '' }
            });
            return BenchmarkUI.MessageBubble.create('assistant', finalAnswer.outerHTML, '', 'bi-chat-left-dots');
        }

        // Step 6: Ensure observation has a meaningful tool name
        const genericNames = ['', 'undefined', 'system', 'assistant', 'user'];
        if (!toolName || genericNames.includes(toolName.toLowerCase())) {
            toolName = isSearch ? 'web_search_tool' : 'Tool Result';
        }

        return BenchmarkUI.ToolCards.render('observation', toolName, displayContent, {
            isSearch: isSearch,
            parsedData: parsedData
        });
    },

    _parseSearchResults: function(displayContent) {
        try {
            const jsonMatch = displayContent.match(/<!-- JSON_DATA_FOR_UI: (.*?) -->/s);
            if (jsonMatch && jsonMatch[1]) return JSON.parse(jsonMatch[1]);

            const extractedJson = JSON.parse(displayContent);
            if (Array.isArray(extractedJson)) return extractedJson;
        } catch (e) {
            const sourceRegex = /<source (\d+)>\s*(.*?)\n([\s\S]*?)<\/source \1>/g;
            let match;
            const extractedResults = [];
            while ((match = sourceRegex.exec(displayContent)) !== null) {
                extractedResults.push({
                    title: match[2].trim(),
                    snippet: match[3].trim().substring(0, 300) + (match[3].length > 300 ? '...' : ''),
                    content: match[3].trim()
                });
            }
            if (extractedResults.length > 0) return extractedResults;
        }
        return null;
    },

    _renderSystemPrompt: function(content) {
        const systemPrompt = BenchmarkUtils.renderTemplate('tpl-system-prompt', {
            '.system-config-content': { text: content }
        });
        return BenchmarkUI.MessageBubble.create('system', systemPrompt.outerHTML, 'bg-light border-secondary border-opacity-10 shadow-none');
    },

    _renderUserInput: function(content) {
        if (typeof content === 'string' && content.includes('<source')) {
            const sourceRegex = /<source (\d+)>\s*(.*?)\n([\s\S]*?)<\/source \1>/g;
            let match;
            const extractedResults = [];
            while ((match = sourceRegex.exec(content)) !== null) {
                extractedResults.push({
                    title: match[2].trim(),
                    snippet: match[3].trim().substring(0, 300) + (match[3].length > 300 ? '...' : ''),
                    content: match[3].trim()
                });
            }

            if (extractedResults.length > 0) {
                const resultsJson = encodeURIComponent(JSON.stringify(extractedResults));
                const injection = BenchmarkUtils.renderTemplate('tpl-user-search-injection', {
                    '.docs-count-text': { text: `${extractedResults.length} documents provided in context` }
                });

                // Set inline onclick to preserve handler after outerHTML serialization
                const viewBtn = injection.querySelector('.view-search-results-btn');
                if (viewBtn) {
                    viewBtn.setAttribute('onclick', `
                        const data = JSON.parse(decodeURIComponent('${resultsJson}'));
                        window.BenchmarkUI.SearchResults.showInModal(data);
                    `);
                }

                let displayContent = BenchmarkHelpers.escapeHtml(content);
                const placeholder = "<!--___RESULTS_CARD_PLACEHOLDER___-->";
                const escapedSourceBlockRegex = /(?:&lt;source \d+&gt;[\s\S]*?&lt;\/source \d+&gt;\s*)+/;
                const blockMatch = displayContent.match(escapedSourceBlockRegex);

                if (blockMatch) {
                    const rawSourceBlock = blockMatch[0];
                    displayContent = displayContent.replace(escapedSourceBlockRegex, placeholder);
                    displayContent = displayContent.replace(/\n/g, '<br>');

                    const collapseId = `raw-source-${extractedResults.length}-${Math.random().toString(36).substr(2, 5)}`;
                    injection.querySelector('.raw-source-toggle').setAttribute('data-bs-target', `#${collapseId}`);
                    injection.querySelector('.raw-source-collapse').id = collapseId;
                    injection.querySelector('.raw-source-pre').textContent = rawSourceBlock;

                    displayContent = displayContent.replace(placeholder, injection.outerHTML);
                    return BenchmarkUI.MessageBubble.create('user', displayContent);
                }
            }
        }
        return BenchmarkUI.MessageBubble.create('user', BenchmarkHelpers.escapeHtml(content).replace(/\n/g, '<br>'));
    }
};
