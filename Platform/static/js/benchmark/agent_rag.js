document.addEventListener('DOMContentLoaded', function() {
    
    // Override renderTrial for Agent visualization
    const originalRenderTrial = BenchmarkUtils.BenchmarkRenderer.renderTrial;
    const activePolls = {};

    BenchmarkUtils.BenchmarkRenderer.renderTrial = function(trial, isCompleted, trialCount, maxRetries) {
        // Always use Agent Renderer on this page
        return renderAgentTrace(trial, isCompleted, trialCount, maxRetries);
    };

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
                        // Append running indicator since we are in polling (processing) state
                        html += `
                            <div class="d-flex align-items-center justify-content-center py-3 text-muted animate__animated animate__fadeIn">
                                <span class="spinner-border spinner-border-sm me-2"></span>
                                <small>Agent is working...</small>
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
            statusBadge = '<span class="badge bg-warning text-dark rounded-pill shadow-sm"><span class="spinner-border spinner-border-sm me-1"></span>Running</span>';
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
                    <div class="bg-primary bg-opacity-10 text-primary rounded-circle p-2 me-3">
                        <i class="bi bi-robot fs-5 p-1"></i>
                    </div>
                    <div>
                        <h6 class="mb-0 fw-bold text-dark">Agent Trajectory #${trial.trial_number}</h6>
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
                        <div class="spinner-grow text-primary" role="status" style="width: 3rem; height: 3rem;">
                            <span class="visually-hidden">Loading...</span>
                        </div>
                        <p class="mt-3 text-muted fw-bold">Agent is thinking...</p>
                        <small class="text-muted d-block">Executing reasoning steps and tool calls.</small>
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
            // Fallback: wrap raw text in a single step
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
        const stepType = step.step_type; // From backend
        
        // Handle content if it's an object (e.g. multimodal or structured)
        if (typeof content === 'object') {
            content = JSON.stringify(content, null, 2);
        }

        let type = 'generic';
        let icon = 'bi-circle';
        let colorClass = 'secondary';
        let label = name;

        // Logic to determine type/style
        if (stepType) {
            // Use explicit type from backend
            if (stepType === 'thought') {
                type = 'thought';
                icon = 'bi-lightbulb';
                colorClass = 'info';
                label = 'Thinking';
            } else if (stepType === 'action') {
                type = 'action';
                icon = 'bi-terminal';
                colorClass = 'warning';
                label = 'Tool Invocation';
            } else if (stepType === 'observation') {
                type = 'observation';
                icon = 'bi-hdd-network';
                colorClass = 'success';
                label = 'Observation';
            } else if (stepType === 'text') {
                 // Fallback to role-based
            }
        }
        
        if (type === 'generic' || stepType === 'text') {
             if (role === 'user') {
                type = 'user';
                icon = 'bi-person-circle';
                colorClass = 'secondary';
                label = 'User Input';
            } else if (role === 'system') {
                type = 'system';
                icon = 'bi-gear';
                colorClass = 'dark';
                label = 'System';
            } else if (role === 'model' || role === 'assistant') {
                 // Even if step_type is text, check for markers just in case
                if (content.includes('Thought:') || content.includes('Reasoning:')) {
                    type = 'thought';
                    icon = 'bi-lightbulb';
                    colorClass = 'info';
                    label = 'Thinking';
                } else if (content.includes('Action:') || content.includes('Tool Call:')) {
                    type = 'action';
                    icon = 'bi-terminal';
                    colorClass = 'warning';
                    label = 'Tool Invocation';
                } else {
                    type = 'response';
                    icon = 'bi-chat-dots';
                    colorClass = 'primary';
                    label = 'Response';
                }
            } 
        }
        
        // Final Answer check
        if (content.includes('Final Answer:') || (type === 'action' && content.includes('answer_question'))) {
             // Maybe highlight specifically?
        }

        // Specific formatting for the content
        let formattedContent = formatContent(content, type);

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
                            <small class="text-muted" style="font-size: 0.7rem;">${step.name || role}</small>
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
        // Try to parse structured content
        let data = null;
        try {
            if (typeof content === 'string' && (content.trim().startsWith('[') || content.trim().startsWith('{'))) {
                data = JSON.parse(content);
            }
        } catch (e) {}

        // 1. Handle Tool Results (Observation) - Search Results or structured output
        if (type === 'observation' && data) {
            // Normalize if data is list of tool_results
            if (Array.isArray(data) && data.length > 0 && data[0].type === 'tool_result') {
                // Extract actual output from tool_result wrapper
                const outputs = data.map(d => d.output);
                // If single output is a list (search results), use it.
                if (outputs.length === 1 && Array.isArray(outputs[0])) {
                    data = outputs[0]; // Treat as search results list
                } else if (outputs.length === 1 && typeof outputs[0] === 'string') {
                     // Try to parse string output if it looks like JSON
                     try { data = JSON.parse(outputs[0]); } 
                     catch(e) { data = outputs[0]; } // Use string if parse fails
                }
            }

            // Render Search Results List
            if (Array.isArray(data) && data.length > 0 && (data[0].title || data[0].link)) {
                let html = '<div class="list-group list-group-flush rounded border w-100" style="overflow: hidden; max-width: 100%; word-break: break-word;">';
                data.forEach(res => {
                    const title = res.title || 'No Title';
                    const link = res.link || '#';
                    const snippet = res.snippet || res.body || '';
                    html += `
                        <div class="list-group-item bg-white">
                            <div class="d-flex w-100 justify-content-between">
                                <h6 class="mb-1 text-primary text-truncate" style="max-width: 80%;"><a href="${link}" target="_blank" class="text-decoration-none">${title}</a></h6>
                                <small class="text-muted"><i class="bi bi-box-arrow-up-right"></i></small>
                            </div>
                            <p class="mb-1 small text-secondary" style="font-size: 0.85rem;">${snippet}</p>
                            <small class="text-muted text-truncate d-block" style="font-size: 0.75rem;">${link}</small>
                        </div>
                    `;
                });
                html += '</div>';
                return html;
            }
        }

        // 2. Handle Tool Use (Action)
        if (type === 'action' && data) {
             if (Array.isArray(data) && data.length > 0 && data[0].type === 'tool_use') {
                 let html = '<div class="d-flex flex-column gap-2">';
                 data.forEach(action => {
                     html += `
                        <div class="card border-0 bg-white shadow-sm">
                            <div class="card-header bg-warning bg-opacity-10 border-0 py-2">
                                <span class="badge bg-warning text-dark me-2">Call</span>
                                <span class="fw-bold font-monospace text-dark">${action.name}</span>
                            </div>
                            <div class="card-body py-2 bg-light font-monospace small text-muted">
                                ${JSON.stringify(action.input || {}, null, 2)}
                            </div>
                        </div>
                     `;
                 });
                 html += '</div>';
                 return html;
             }
        }

        // 3. Fallback / Standard Text
        // Escape HTML
        let safeContent = content.replace(/</g, "&lt;").replace(/>/g, "&gt;");

        // Highlighting for ReAct keywords
        safeContent = safeContent.replace(/(Thought:)/g, '<span class="fw-bold text-info">$1</span>')
                                 .replace(/(Action:)/g, '<span class="fw-bold text-warning">$1</span>')
                                 .replace(/(Observation:)/g, '<span class="fw-bold text-success">$1</span>');
        
        if (type === 'action' || type === 'observation') {
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

    BenchmarkUtils.MultiTurnPage.init({
        pipelineType: 'agent_rag',
        csvPrefix: 'agent-rag',
    });
});
