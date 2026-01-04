window.AgentBenchmark = (function() {
    const activePolls = {};
    const trialState = {};
    let globalConfig = {};

    const CONFIGS = {
        'vanilla_agent': {
            pipelineType: 'vanilla_agent',
            csvPrefix: 'vanilla-agent',
            title: 'Vanilla Agent Trajectory',
            mainIconClass: 'bi-robot',
            mainColorClass: 'bg-primary',
            textClass: 'text-primary',
            loadingText: 'Agent is thinking...',
            runningText: 'Agent is working...'
        },
        'browser_agent': {
            pipelineType: 'browser_agent',
            csvPrefix: 'browser-agent',
            title: 'Browser Session',
            mainIconClass: 'bi-browser-chrome',
            mainColorClass: 'bg-info',
            textClass: 'text-info',
            loadingText: 'Agent is navigating...',
            runningText: 'Browser Agent is working...'
        }
    };

    function initWithType(type) {
        if (CONFIGS[type]) {
            init(CONFIGS[type]);
        } else {
            console.error("Unknown agent type:", type);
            // Fallback
            init(CONFIGS['vanilla_agent']);
        }
    }

    function init(config) {
        globalConfig = config;

        // Wrap renderTrial to hook in polling
        const originalRenderTrial = BenchmarkUtils.BenchmarkRenderer.renderTrial;
        BenchmarkUtils.BenchmarkRenderer.renderTrial = function(trial, isCompleted, trialCount, maxRetries, questionText, pipelineType) {
            // Call original renderer (which now handles bubbles via renderAgentStep)
            // Note: We use globalConfig.pipelineType to ensure it's treated as agent
            const trialDiv = originalRenderTrial.call(BenchmarkUtils.BenchmarkRenderer, trial, isCompleted, trialCount, maxRetries, questionText, globalConfig.pipelineType);
            
            // Trigger polling if processing
            if (trial.status === 'processing') {
                setTimeout(() => startPolling(trial.id), 100);
            }
            return trialDiv;
        };

        // Init MultiTurnPage
        BenchmarkUtils.MultiTurnPage.init({
            pipelineType: globalConfig.pipelineType,
            csvPrefix: globalConfig.csvPrefix,
        });
    }

    function startPolling(trialId) {
        if (activePolls[trialId]) return;

        // Initialize state
        if (!trialState[trialId]) {
            trialState[trialId] = { renderedCount: 0, backoffDelay: 2000, lastStepWasStreaming: false };
        }

        const poll = () => {
            const trialDiv = document.getElementById(`trial-${trialId}`);
            if (!trialDiv) {
                delete activePolls[trialId];
                delete trialState[trialId];
                return;
            }

            let currentCount = trialState[trialId].renderedCount;
            // If the last step was streaming (partial), we need to re-fetch it to get updates
            if (trialState[trialId].lastStepWasStreaming) {
                currentCount = Math.max(0, currentCount - 1);
            }
            
            fetch(`/benchmark/api/multi_turn/get_trial_trace/${trialId}/?cursor=${currentCount}`)
                .then(res => res.json())
                .then(data => {
                    const newSteps = data.trace || [];
                    const trialInfo = data.trial; 

                    // 1. Render new steps
                    if (newSteps.length > 0) {
                        trialState[trialId].backoffDelay = 2000; // Reset backoff

                        const wrapper = trialDiv.querySelector('.trial-wrapper');
                        if (wrapper) {
                            // Safety: If starting fresh (cursor=0), clear existing bubbles to prevent duplication
                            // of static content rendered by originalRenderTrial.
                            if (currentCount === 0) {
                                const existing = wrapper.querySelectorAll('.message-bubble');
                                existing.forEach(el => el.remove());
                            }

                            // If we are replacing a streaming step, remove the last bubble
                            if (trialState[trialId].lastStepWasStreaming) {
                                // Find the last message bubble and remove it
                                const bubbles = wrapper.querySelectorAll('.message-bubble');
                                if (bubbles.length > 0) {
                                    bubbles[bubbles.length - 1].remove();
                                }
                                trialState[trialId].renderedCount--; // Decrement count since we removed one
                            }

                            // Check for processing indicator
                            const processingIndicator = wrapper.querySelector('.trial-processing-indicator');
                            let indicatorParent = null;
                            if (processingIndicator) {
                                indicatorParent = processingIndicator.closest('.message-bubble');
                                if (indicatorParent) indicatorParent.remove();
                            }

                            let newStepsHtml = '';
                            newSteps.forEach((step, idx) => {
                                // Use the shared renderer from BenchmarkRenderer
                                newStepsHtml += BenchmarkUtils.BenchmarkRenderer.renderAgentStep(step, currentCount + idx, trialId);
                            });
                            
                            wrapper.insertAdjacentHTML('beforeend', newStepsHtml);
                            
                            // Re-append processing indicator if still processing
                            if (trialInfo && trialInfo.status === 'processing' && indicatorParent) {
                                wrapper.insertAdjacentElement('beforeend', indicatorParent);
                            } else if (trialInfo && trialInfo.status === 'processing') {
                                // Create new if missing
                                const indicatorHtml = BenchmarkUtils.BenchmarkRenderer.createMessageBubble('assistant', `<div class="d-flex align-items-center trial-processing-indicator"><span class="spinner-border spinner-border-sm text-primary me-2"></span>${globalConfig.loadingText}</div>`, '', 'bi-robot');
                                wrapper.insertAdjacentHTML('beforeend', indicatorHtml);
                            }
                        }
                        
                        trialState[trialId].renderedCount += newSteps.length;

                        // Check if the last received step is streaming
                        const lastStep = newSteps[newSteps.length - 1];
                        if (lastStep && lastStep.is_streaming) {
                            trialState[trialId].lastStepWasStreaming = true;
                            // Shorten polling interval for smooth streaming
                             trialState[trialId].backoffDelay = 500;
                        } else {
                            trialState[trialId].lastStepWasStreaming = false;
                        }

                    } else {
                        trialState[trialId].backoffDelay = Math.min(trialState[trialId].backoffDelay * 1.5, 10000);
                    }

                    // 2. Check for Completion
                    if (trialInfo && (trialInfo.status === 'completed' || trialInfo.status === 'error')) {
                        // Stop polling
                        clearTimeout(activePolls[trialId]);
                        delete activePolls[trialId];
                        delete trialState[trialId];

                        // Remove processing indicator
                        const wrapper = trialDiv.querySelector('.trial-wrapper');
                        if (wrapper) {
                             const processingIndicator = wrapper.querySelector('.trial-processing-indicator');
                             if (processingIndicator) {
                                 const indicatorParent = processingIndicator.closest('.message-bubble');
                                 if (indicatorParent) indicatorParent.remove();
                             }
                        }
                        
                        // Update Verdict / Status Badge logic
                        if (trialInfo.status === 'completed' && (trialInfo.feedback || trialInfo.is_correct_rule !== undefined)) {
                             // Avoid double rendering if originalRenderTrial already handled it
                             if (wrapper.querySelector('.trial-verdict-container')) return;

                             const isCorrectLLM = trialInfo.is_correct_llm !== undefined ? trialInfo.is_correct_llm : trialInfo.is_correct;
                             const isCorrectRule = trialInfo.is_correct_rule;
                             
                             let verdictHtml = '<div class="d-flex flex-column align-items-center gap-2 mt-2 mb-2 fade-in trial-verdict-container">';
                             
                             // LLM Verdict
                             if (isCorrectLLM !== undefined && isCorrectLLM !== null) {
                                 const llmColor = isCorrectLLM ? 'success' : 'danger';
                                 const llmIcon = isCorrectLLM ? 'bi-check-circle-fill' : 'bi-x-circle-fill';
                                 verdictHtml += `
                                     <div class="card border-0 shadow-sm rounded-pill px-2" style="background-color: #f8f9fa;">
                                         <div class="card-body py-2 px-4 d-flex align-items-center">
                                             <i class="bi ${llmIcon} text-${llmColor} fs-5 me-2"></i>
                                             <div class="fw-bold text-${llmColor} text-uppercase small" style="letter-spacing: 1px;">Verdict (LLM): ${isCorrectLLM ? 'Correct' : 'Incorrect'}</div>
                                         </div>
                                     </div>`;
                             }

                             // Rule Verdict
                             if (isCorrectRule !== undefined && isCorrectRule !== null) {
                                 const ruleColor = isCorrectRule ? 'success' : 'danger';
                                 const ruleIcon = isCorrectRule ? 'bi-check-circle-fill' : 'bi-x-circle-fill';
                                 verdictHtml += `
                                     <div class="card border-0 shadow-sm rounded-pill px-2" style="background-color: #f8f9fa;">
                                         <div class="card-body py-2 px-4 d-flex align-items-center">
                                             <i class="bi ${ruleIcon} text-${ruleColor} fs-5 me-2"></i>
                                             <div class="fw-bold text-${ruleColor} text-uppercase small" style="letter-spacing: 1px;">Verdict (Rule): ${isCorrectRule ? 'Correct' : 'Incorrect'}</div>
                                         </div>
                                     </div>`;
                             }
                             
                             verdictHtml += '</div>';
                             wrapper.insertAdjacentHTML('beforeend', verdictHtml);
                        }

                        return; // Exit poll loop
                    }

                })
                .catch(err => {
                    console.error("Polling error:", err);
                    trialState[trialId].backoffDelay = 10000;
                })
                .finally(() => {
                    if (activePolls[trialId]) {
                         if (document.getElementById(`trial-${trialId}`)) {
                            activePolls[trialId] = setTimeout(poll, trialState[trialId].backoffDelay);
                        } else {
                            delete activePolls[trialId];
                            delete trialState[trialId];
                        }
                    }
                });
        };

        // Start the loop
        activePolls[trialId] = setTimeout(poll, 2000);
    }

    return {
        init: init,
        initWithType: initWithType
    };
})();