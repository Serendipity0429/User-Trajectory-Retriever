/**
 * Unified Pipeline Configuration
 * Single source of truth for pipeline types, icons, colors, and labels
 */

window.BenchmarkPipelineConfig = {
    'vanilla_llm': {
        icon: 'bi-chat-square-text',
        color: 'primary',
        textClass: 'text-primary',
        label: 'Vanilla',
        loadingText: 'Thinking...'
    },
    'rag': {
        icon: 'bi-database-gear',
        color: 'warning',
        textClass: 'text-warning',
        label: 'RAG',
        loadingText: 'Thinking...'
    },
    'vanilla_agent': {
        icon: 'bi-robot',
        color: 'info',
        textClass: 'text-info',
        label: 'Agent',
        loadingText: 'Thinking...'
    },
    'browser_agent': {
        icon: 'bi-browser-chrome',
        color: 'success',
        textClass: 'text-success',
        label: 'Browser',
        loadingText: 'Thinking...'
    }
};

/**
 * Get pipeline configuration with fallback defaults
 * @param {string} pipelineType - The pipeline type key
 * @returns {object} Pipeline configuration
 */
window.BenchmarkPipelineConfig.get = function(pipelineType) {
    return this[pipelineType] || {
        icon: 'bi-question-circle',
        color: 'secondary',
        textClass: 'text-secondary',
        label: pipelineType || 'Unknown',
        loadingText: 'Processing...'
    };
};
