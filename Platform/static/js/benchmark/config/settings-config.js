/**
 * Settings Configuration
 * Defines configuration groups for run configuration display
 * Single source of truth for settings field definitions
 */

window.BenchmarkSettingsConfig = {
    groups: {
        'llm': {
            label: 'LLM Settings',
            sources: ['llm'],
            fields: [
                { key: 'llm_model', label: 'LLM Model', icon: 'bi-cpu' },
                { key: 'llm_judge_model', label: 'Judge Model', icon: 'bi-clipboard-check' },
                { key: 'max_retries', label: 'Max Retries', icon: 'bi-arrow-repeat' },
                { key: 'temperature', label: 'Temperature', icon: 'bi-thermometer-half' },
                { key: 'top_p', label: 'Top P', icon: 'bi-percent' },
                { key: 'top_k', label: 'Top K', icon: 'bi-sort-numeric-down' },
                { key: 'max_tokens', label: 'Max Tokens', icon: 'bi-text-paragraph' },
                { key: 'allow_reasoning', label: 'Reasoning', icon: 'bi-lightbulb', type: 'boolean' },
                { key: 'llm_base_url', label: 'Base URL', icon: 'bi-link-45deg' }
            ]
        },
        'search': {
            label: 'Search Settings',
            sources: ['search'],
            fields: [
                { key: 'search_provider', label: 'Search Provider', icon: 'bi-globe', formatter: function(val) { return val === 'mcp' ? 'MCP Server' : (val === 'serper' ? 'Serper API' : val); } },
                { key: 'search_limit', label: 'Top-K Limit', icon: 'bi-list-ol' },
                { key: 'serper_fetch_full_content', label: 'Full Content', icon: 'bi-file-text', type: 'boolean', domId: 'serper_fetch_full_content' }
            ]
        },
        'agent': {
            label: 'Agent Settings',
            sources: ['agent'],
            fields: [
                { key: 'memory_type', label: 'Agent Memory', icon: 'bi-memory', map: { 'naive': 'Naive Memory', 'mem0': 'Mem0 Memory', 'reme': 'ReMe Memory' }, domId: 'agent_memory_type' },
                { key: 'max_iters', label: 'Max Iterations', icon: 'bi-arrow-repeat', domId: 'agent_max_iters' },
                { key: 'model_name', label: 'Agent Model', icon: 'bi-robot' }
            ]
        }
    },

    /**
     * Get field keys for a specific group
     * @param {string} groupName - The group name ('llm', 'search', 'agent')
     * @returns {string[]} Array of field keys
     */
    getFieldKeys: function(groupName) {
        const group = this.groups[groupName];
        if (!group) return [];
        return group.fields.map(f => f.key);
    },

    /**
     * Get all field keys across all groups
     * @returns {string[]} Array of all field keys
     */
    getAllFieldKeys: function() {
        const keys = [];
        Object.values(this.groups).forEach(group => {
            group.fields.forEach(f => keys.push(f.key));
        });
        return keys;
    },

    /**
     * Build a whitelist for specific pipeline type
     * @param {string} pipelineType - The pipeline type
     * @returns {string[]} Whitelist of field keys to display
     */
    buildWhitelist: function(pipelineType) {
        // Always include LLM settings
        const whitelist = this.getFieldKeys('llm');

        // Add search settings for RAG pipelines
        if (pipelineType && pipelineType.includes('rag')) {
            whitelist.push(...this.getFieldKeys('search'));
        }

        // Add agent settings for agent pipelines
        if (pipelineType && pipelineType.includes('agent')) {
            whitelist.push(...this.getFieldKeys('agent'));
        }

        return whitelist;
    }
};
