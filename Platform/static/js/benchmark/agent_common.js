window.AgentBenchmark = (function() {
    const activePolls = {};
    let globalConfig = {};

    function init(config) {
        globalConfig = {
            pipelineType: 'agent_rag', // default
            csvPrefix: 'agent-data',
            title: 'Agent Trajectory',
            mainIconClass: 'bi-robot',
            mainColorClass: 'bg-primary',
            textClass: 'text-primary',
            loadingText: 'Agent is thinking...',
            runningText: 'Agent is working...',
            stepIcons: {
                thought: 'bi-lightbulb',
                action: 'bi-terminal',
                observation: 'bi-hdd-network',
                user: 'bi-person-circle',
                system: 'bi-gear',
                response: 'bi-chat-dots'
            },
            ...config
        };

        // Override renderTrial
        BenchmarkUtils.BenchmarkRenderer.renderTrial = function(trial, isCompleted, trialCount, maxRetries) {
            return renderAgentTrace(trial, isCompleted, trialCount, maxRetries);
        };

        // Init MultiTurnPage
        BenchmarkUtils.MultiTurnPage.init({
            pipelineType: globalConfig.pipelineType,
            csvPrefix: globalConfig.csvPrefix,
        });
    }

    function startPolling(trialId) {
        if (activePolls[trialId]) return;

        const intervalId = setInterval(() => {
            const container = document.getElementById(`live-trace-${trialId}`);
            if (!container) {
                clearInterval(intervalId);
                delete activePolls[trialId];
                return;
            }

            fetch(`/benchmark/api/multi_turn/get_trial_trace/${trialId}/`)
                .then(res => res.json())
                .then(data => {
                    const traceData = data.trace;
                    if (traceData && traceData.length > 0) {
                        let html = renderTraceTimeline(traceData);
                        html += `
                            <div class="d-flex align-items-center justify-content-center py-3 text-muted animate__animated animate__fadeIn">
                                <span class="spinner-border spinner-border-sm me-2"></span>
                                <small>${globalConfig.runningText}</small>
                            </div>
                        `;
                        container.innerHTML = html;
                    }
                })
                .catch(err => console.error("Polling error:", err));
        }, 1000); // Poll every 1s
        
        activePolls[trialId] = intervalId;
    }

    function renderAgentTrace(trial, isCompleted, trialCount, maxRetries) {
        const trialDiv = document.createElement('div');
        trialDiv.className = 'mb-5';
        trialDiv.id = `trial-${trial.id}`;

        let statusBadge = '';
        if (trial.status === 'processing') {
            statusBadge = '<span class="badge bg-primary text-light rounded-pill shadow-sm"><span class="spinner-border spinner-border-sm me-1"></span>Running</span>';
        } else if (isCompleted || trialCount >= maxRetries || trial.is_correct === true) {
            if (trial.is_correct) {
                statusBadge = '<span class="badge bg-success rounded-pill shadow-sm"><i class="bi bi-check-lg me-1"></i>Correct</span>';
            } else if (trial.is_correct === false) {
                    statusBadge = '<span class="badge bg-danger rounded-pill shadow-sm"><i class="bi bi-x-lg me-1"></i>Incorrect</span>';
            }
        } else if (trial.status === 'error') {
            statusBadge = '<span class="badge bg-danger rounded-pill shadow-sm"><i class="bi bi-exclamation-triangle me-1"></i>Error</span>';
        }

        const header = `
            <div class="card-header bg-white border-bottom py-3 d-flex justify-content-between align-items-center">
                <div class="d-flex align-items-center">
                    <div class="${globalConfig.mainColorClass} bg-opacity-10 ${globalConfig.textClass} rounded-circle p-2 me-3">
                        <i class="bi ${globalConfig.mainIconClass} fs-5 p-1"></i>
                    </div>
                    <div>
                        <h6 class="mb-0 fw-bold text-dark">${globalConfig.title} #${trial.trial_number}</h6>
                        <small class="text-muted">Execution Trace</small>
                    </div>
                </div>
                <div>${statusBadge}</div>
            </div>
        `;

        // Parse Trace
        let traceContent = '';
        if (trial.status === 'processing' && !trial.full_response) {
             traceContent = `
                <div id="live-trace-${trial.id}" class="min-vh-25">
                    <div class="text-center py-5">
                        <div class="spinner-grow ${globalConfig.textClass}" role="status" style="width: 3rem; height: 3rem;">
                            <span class="visually-hidden">Loading...</span>
                        </div>
                        <p class="mt-3 text-muted fw-bold">${globalConfig.loadingText}</p>
                        <small class="text-muted d-block">Please wait while the agent executes.</small>
                    </div>
                </div>
             `;
             // Trigger polling
             setTimeout(() => startPolling(trial.id), 100);
        } else {
             traceContent = renderTraceTimeline(trial.full_response);
        }
        
        const bodyContent = `
            <div class="card-body bg-light bg-opacity-25 p-0">
                <div class="agent-timeline p-4">
                    ${traceContent}
                </div>
                
                <div class="border-top bg-white p-4">
                    <div class="d-flex align-items-start">
                        <div class="bg-success bg-opacity-10 text-success rounded p-2 me-3">
                            <i class="bi bi-chat-square-quote fs-4"></i>
                        </div>
                        <div class="w-100">
                            <span class="text-uppercase text-muted fw-bold d-block mb-1" style="font-size: 0.7rem; letter-spacing: 1px;">Final Answer</span>
                            <div class="p-3 bg-light rounded border border-light text-dark shadow-sm">
                                ${trial.answer || (trial.status === 'processing' ? '<em class="text-muted">Waiting for answer...</em>' : '<em class="text-muted">No answer produced.</em>')}
                            </div>
                        </div>
                    </div>
                    ${renderFeedback(trial)}
                </div>
            </div>
        `;

        trialDiv.innerHTML = `
            <div class="card border-0 shadow-lg overflow-hidden" style="border-radius: 12px;">
                ${header}
                ${bodyContent}
            </div>`;
        return trialDiv;
    }

    function renderTraceTimeline(fullResponse) {
        let traceData = [];
        try {
            if (typeof fullResponse === 'string') {
                traceData = JSON.parse(fullResponse);
            } else if (Array.isArray(fullResponse)) {
                traceData = fullResponse;
            } else {
                throw new Error("Invalid format");
            }
            
            if (!Array.isArray(traceData)) throw new Error("Not an array");
        } catch (e) {
            // Fallback
            if (fullResponse) {
                 traceData = [{
                    role: 'unknown',
                    name: 'Agent Trace',
                    content: typeof fullResponse === 'string' ? fullResponse : JSON.stringify(fullResponse),
                    step_type: 'text'
                }];
            } else {
                return '<div class="text-muted fst-italic text-center py-4">No trace steps recorded.</div>';
            }
        }

        if (traceData.length === 0) {
            return '<div class="text-muted fst-italic text-center py-4">No trace steps recorded.</div>';
        }

        let html = '<div class="timeline-container d-flex flex-column gap-3">';
        traceData.forEach((step, index) => {
            html += renderStep(step, index);
        });
        html += '</div>';
        return html;
    }

    function renderStep(step, index) {
        const role = step.role || 'unknown';
        const name = step.name || role;
        let content = step.content || '';
        const stepType = step.step_type;

        if (typeof content === 'object' && content !== null) {
            if (Array.isArray(content) && content.length > 0 && (content[0].type === 'tool_use' || content[0].type === 'tool_result')) {
                // Keep
            } else {
                content = JSON.stringify(content, null, 2);
            }
        }

        let type = 'generic';
        let icon = 'bi-circle';
        let colorClass = 'secondary';
        let label = name;
        let showRoleInSmallTag = true;

        // Determine type/style
        const icons = globalConfig.stepIcons;
        
        if (stepType) {
            if (stepType === 'thought') {
                type = 'thought';
                icon = icons.thought;
                colorClass = 'info';
                label = 'Thinking';
            } else if (stepType === 'action') {
                type = 'action';
                icon = icons.action;
                colorClass = 'warning';
                label = 'Action';
                showRoleInSmallTag = false;
            } else if (stepType === 'observation') {
                type = 'observation';
                icon = icons.observation;
                colorClass = 'success';
                label = 'Observation';
                showRoleInSmallTag = false;
            }
        }
        
        if (type === 'generic' || stepType === 'text') {
             if (role === 'user') {
                type = 'user';
                icon = icons.user;
                colorClass = 'secondary';
                label = 'User Input';
            } else if (role === 'system') {
                type = 'system';
                icon = icons.system;
                colorClass = 'dark';
                label = 'System';
            } else if (role === 'model' || role === 'assistant') {
                if (typeof content === 'string' && (content.includes('Thought:') || content.includes('Reasoning:'))) {
                    type = 'thought';
                    icon = icons.thought;
                    colorClass = 'info';
                    label = 'Thinking';
                } else if (typeof content === 'string' && (content.includes('Action:') || content.includes('Tool Call:'))) {
                    type = 'action';
                    icon = icons.action;
                    colorClass = 'warning';
                    label = 'Action';
                    showRoleInSmallTag = false;
                } else {
                    type = 'response';
                    icon = icons.response;
                    colorClass = 'primary';
                    label = 'Response';
                }
            } 
        }

        let formattedContent = formatContent(content, type);
        const smallTagContent = showRoleInSmallTag ? `<small class="text-muted" style="font-size: 0.7rem;">${step.name || role}</small>` : '';

        return `
            <div class="timeline-item d-flex animate__animated animate__fadeIn" style="animation-delay: ${index * 50}ms;">
                <div class="timeline-marker me-3 d-flex flex-column align-items-center">
                    <div class="badge bg-${colorClass} rounded-circle p-2 d-flex align-items-center justify-content-center shadow-sm" style="width: 32px; height: 32px;">
                        <i class="bi ${icon}"></i>
                    </div>
                    <div class="h-100 border-start border-2 border-${colorClass} opacity-25 my-1" style="min-height: 20px;"></div>
                </div>
                <div class="timeline-content w-100 pb-3" style="min-width: 0;">
                    <div class="card border-0 shadow-sm">
                        <div class="card-header bg-white border-bottom-0 d-flex justify-content-between align-items-center py-2">
                            <span class="badge bg-${colorClass} bg-opacity-10 text-${colorClass} text-uppercase" style="font-size: 0.7rem; letter-spacing: 0.5px;">${label}</span>
                            ${smallTagContent}
                        </div>
                        <div class="card-body py-2 text-dark" style="font-size: 0.9rem;">
                            ${formattedContent}
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    function formatContent(content, type) {
        let data = null;
        
        // Helper to try parsing JSON
        const tryParse = (str) => {
            try { return JSON.parse(str); } catch (e) { return null; }
        };

        if (typeof content === 'string') {
            // 1. Try direct parse
            data = tryParse(content);

            // 2. If null, try stripping "Tool Call:" or "Tool Result:" prefixes
            if (!data) {
                const prefixes = ["Tool Call:", "Tool Result:", "Action:", "Observation:"];
                for (const prefix of prefixes) {
                    if (content.trim().toLowerCase().startsWith(prefix.toLowerCase())) {
                        const potentialJson = content.substring(content.indexOf(prefix) + prefix.length).trim();
                        data = tryParse(potentialJson);
                        if (data) break;
                    }
                }
            }
            
            // 3. Fallback: Try to find the first '{' or '[' and last '}' or ']'
            if (!data) {
                 const start = content.search(/[\{\[]/);
                 const end = content.search(/[\}\]][^\{\}\[\]]*$/);
                 if (start !== -1 && end !== -1 && end > start) {
                     data = tryParse(content.substring(start, end + 1));
                 }
            }

        } else if (typeof content === 'object' && content !== null) {
            data = content;
        }

        // 1. Observation
        if (type === 'observation' && data) {
            // Normalize to array if it's a single tool_result object
            let results = [];
            if (Array.isArray(data)) {
                if (data.length > 0 && data[0].type === 'tool_result') results = data;
            } else if (data.type === 'tool_result') {
                results = [data];
            }

            // Browser snapshot check (still possibly an object)
            if (data.title || data.url) {
                 return `
                    <div class="p-2 bg-light border rounded">
                        <div class="d-flex align-items-center mb-1">
                            <i class="bi bi-window-sidebar me-2 text-primary"></i>
                            <span class="fw-bold text-truncate" style="max-width: 300px;">${data.title || 'Untitled Page'}</span>
                        </div>
                        <a href="${data.url}" target="_blank" class="small text-muted d-block text-truncate mb-2">${data.url}</a>
                        <span class="badge bg-secondary">Content Length: ${data.body_content_length || 'N/A'}</span>
                    </div>
                 `;
            }

            // Render Tool Results
            if (results.length > 0) {
                let html = '<div class="d-flex flex-column gap-2">';
                results.forEach(result => {
                    const toolName = result.name;
                    const output = result.output;
                    
                    if (toolName === 'web_search_tool') {
                         if (Array.isArray(output)) {
                            // Generate unique ID for collapse group
                            const uniqueGroupId = `search-results-${Math.random().toString(36).substr(2, 9)}`;
                            
                            html += '<div class="card border-0 bg-white shadow-sm">';
                            html += `<div class="card-header bg-success bg-opacity-10 border-0 py-2"><span class="badge bg-success text-dark me-2">Search Result</span><span class="fw-bold font-monospace text-dark">${output.length} results from ${toolName}</span></div>`;
                            html += '<div class="list-group list-group-flush rounded w-100" style="overflow: hidden; max-width: 100%; word-break: break-word;">';
                            
                            const renderItem = (res) => {
                                const title = res.title || 'No Title';
                                const link = res.link || '#';
                                const snippet = res.snippet || res.body || '';
                                const fullContent = res.content || res.body || '';
                                const hasFullContent = fullContent && fullContent.length > (snippet.length + 50); // Heuristic
                                const itemUniqueId = `result-content-${Math.random().toString(36).substr(2, 9)}`;

                                let itemHtml = `
                                    <div class="list-group-item bg-white">
                                        <div class="d-flex w-100 justify-content-between">
                                            <h6 class="mb-1 text-primary text-truncate" style="max-width: 80%;"><a href="${link}" target="_blank" class="text-decoration-none">${title}</a></h6>
                                            <small class="text-muted"><i class="bi bi-box-arrow-up-right"></i></small>
                                        </div>
                                        <p class="mb-1 small text-secondary" style="font-size: 0.85rem;">${snippet.substring(0, 150)}${snippet.length > 150 ? '...' : ''}</p>
                                `;
                                
                                if (hasFullContent) {
                                    itemHtml += `
                                        <a class="text-decoration-none small fw-bold" data-bs-toggle="collapse" href="#${itemUniqueId}" role="button" aria-expanded="false" aria-controls="${itemUniqueId}">
                                            <i class="bi bi-caret-down-fill"></i> Show Full Content
                                        </a>
                                        <div class="collapse mt-2" id="${itemUniqueId}">
                                            <div class="card card-body bg-light small text-secondary p-2" style="max-height: 300px; overflow-y: auto; white-space: pre-wrap;">${fullContent}</div>
                                        </div>
                                    `;
                                }

                                itemHtml += `
                                        <small class="text-muted text-truncate d-block mt-1" style="font-size: 0.75rem;">${link}</small>
                                    </div>
                                `;
                                return itemHtml;
                            };

                            // Render first 3 items
                            output.slice(0, 3).forEach(res => {
                                html += renderItem(res);
                            });
                            
                            // Render remaining items in a collapse div
                            if (output.length > 3) {
                                html += `<div class="collapse" id="${uniqueGroupId}">`;
                                output.slice(3).forEach(res => {
                                    html += renderItem(res);
                                });
                                html += `</div>`;
                                
                                // Toggle button
                                html += `
                                    <button class="list-group-item list-group-item-action bg-light text-center small text-primary fw-bold" type="button" data-bs-toggle="collapse" data-bs-target="#${uniqueGroupId}" aria-expanded="false" aria-controls="${uniqueGroupId}">
                                        <i class="bi bi-chevron-down me-1"></i> Show ${output.length - 3} more results
                                    </button>
                                `;
                            }
                            html += '</div></div>';
                        } else {
                            html += `
                                <div class="card border-0 bg-white shadow-sm">
                                    <div class="card-header bg-success bg-opacity-10 border-0 py-2"><span class="badge bg-success text-dark me-2">Result</span><span class="fw-bold font-monospace text-dark">${toolName}</span></div>
                                    <div class="card-body py-2 bg-light font-monospace small text-muted">
                                        ${typeof output === 'string' ? output : JSON.stringify(output, null, 2)}
                                    </div>
                                </div>
                            `;
                        }
                    } else if (toolName === 'answer_question') {
                        html += `
                            <div class="card border-0 bg-white shadow-sm">
                                <div class="card-header bg-success bg-opacity-10 border-0 py-2"><span class="badge bg-success text-dark me-2">Answer Tool</span><span class="fw-bold font-monospace text-dark">Answer submitted</span></div>
                                <div class="card-body py-2 bg-light font-monospace small text-muted">
                                    <i class="bi bi-check-circle me-1 text-success"></i> Successfully submitted final answer.
                                </div>
                            </div>
                        `;
                    } else {
                        html += `
                            <div class="card border-0 bg-white shadow-sm">
                                <div class="card-header bg-success bg-opacity-10 border-0 py-2"><span class="badge bg-success text-dark me-2">Result</span><span class="fw-bold font-monospace text-dark">${toolName}</span></div>
                                <div class="card-body py-2 bg-light font-monospace small text-muted">
                                    ${typeof output === 'string' ? output : JSON.stringify(output, null, 2)}
                                </div>
                            </div>
                        `;
                    }
                });
                html += '</div>';
                return html;
            }
        }

        // 2. Action
        if (type === 'action' && data) {
             // Normalize to array if it's a single tool_use object
             let actions = [];
             if (Array.isArray(data)) {
                 if (data.length > 0 && data[0].type === 'tool_use') actions = data;
             } else if (data.type === 'tool_use') {
                 actions = [data];
             }

             if (actions.length > 0) {
                 let html = '<div class="d-flex flex-column gap-2">';
                 
                 // Tool Rendering Strategy Map
                 const toolRenderers = {
                     'answer_question': (input) => {
                         const answerText = input.answer || 'No answer provided.';
                         return {
                             title: 'Answer Question',
                             content: `<p class="mb-0">${answerText}</p>`
                         };
                     },
                     'web_search_tool': (input) => {
                         const query = input.query || 'No query provided.';
                         return {
                             title: 'Web Search',
                             content: `<strong>Query:</strong> <span class="text-primary">${query}</span>`
                         };
                     },
                     'navigate_to_url': (input) => {
                         return {
                             title: 'Navigate',
                             content: `<div class="d-flex align-items-center"><i class="bi bi-globe me-2 text-primary"></i> <a href="${input.url}" target="_blank">${input.url}</a></div>`
                         };
                     },
                     'click_element': (input) => {
                         return {
                             title: 'Click Element',
                             content: `<strong>Selector:</strong> <span class="font-monospace text-primary bg-light px-1 rounded">${input.selector}</span>`
                         };
                     },
                     'type_text': (input) => {
                         return {
                             title: 'Type Text',
                             content: `
                                <div><strong>Selector:</strong> <span class="font-monospace text-primary bg-light px-1 rounded">${input.selector}</span></div>
                                <div class="mt-1"><strong>Text:</strong> <span class="text-success">"${input.text}"</span></div>
                             `
                         };
                     },
                     'scroll_page': (input) => {
                         return {
                             title: 'Scroll Page',
                             content: `Direction: <strong>${input.direction || 'down'}</strong>, Amount: ${input.amount || 500}px`
                         };
                     },
                     'get_dom_snapshot': (input) => {
                         return {
                             title: 'Get DOM Snapshot',
                             content: '<em class="text-muted">Capturing current page structure...</em>'
                         };
                     },
                     'default': (name, input) => {
                         const argsContent = Object.entries(input)
                            .map(([key, value]) => `
                                <div class="d-flex text-break">
                                    <strong class="me-2" style="min-width: 80px;">${key}:</strong> 
                                    <span class="text-primary">${typeof value === 'object' ? JSON.stringify(value, null, 2) : value}</span>
                                </div>`)
                            .join('');
                         return {
                             title: name,
                             content: `<div class="p-2 bg-light rounded" style="font-size: 0.95rem; white-space: pre-wrap;">${argsContent || '<em class="text-muted">No parameters</em>'}</div>`
                         };
                     }
                 };

                 actions.forEach(action => {
                     const toolName = action.name;
                     const toolInput = action.input || {};
                     
                     // Select renderer or fallback to default
                     const renderer = toolRenderers[toolName] || ((input) => toolRenderers['default'](toolName, input));
                     const renderResult = renderer(toolInput);

                     html += `
                        <div class="card border-0 bg-white shadow-sm">
                            <div class="card-header bg-warning bg-opacity-10 border-0 py-2">
                                <span class="badge bg-warning text-dark me-2">Call</span>
                                <span class="fw-bold font-monospace text-dark">${renderResult.title}</span>
                            </div>
                            <div class="card-body py-2 bg-light small text-muted">
                                ${renderResult.content}
                            </div>
                        </div>
                     `;
                 });
                 html += '</div>';
                 return html;
             }
        }

        // 3. Fallback
        let safeContent = content.replace(/</g, "&lt;").replace(/>/g, "&gt;");
        safeContent = safeContent.replace(/(Thought:)/g, '<span class="fw-bold text-info">$1</span>')
                                 .replace(/(Action:)/g, '<span class="fw-bold text-warning">$1</span>')
                                 .replace(/(Observation:)/g, '<span class="fw-bold text-success">$1</span>');
        
        if (type === 'action' || type === 'observation' || type === 'thought') {
            return `<div class="bg-dark bg-opacity-10 p-2 rounded" style="font-family: monospace; white-space: pre-wrap; font-size: 0.85rem; overflow-x: auto;">${safeContent}</div>`;
        }
        
        return `<div style="white-space: pre-wrap;">${safeContent}</div>`;
    }

    function renderFeedback(trial) {
        if (!trial.feedback) return '';
        const isCorrect = trial.is_correct;
        const alertClass = isCorrect ? 'alert-success' : 'alert-danger';
        const icon = isCorrect ? '<i class="bi bi-check-circle-fill me-2 fs-5"></i>' : '<i class="bi bi-x-circle-fill me-2 fs-5"></i>';
        return `<div class="alert ${alertClass} border-0 d-flex align-items-center mt-3 mb-0" role="alert">
                    ${icon}
                    <div>
                        <strong class="d-block text-uppercase" style="font-size: 0.7rem; letter-spacing: 0.5px;">Verdict</strong>
                        ${trial.feedback}
                    </div>
                </div>`;
    }

    return {
        init: init
    };
})();
