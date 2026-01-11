/**
 * Centralized URL configuration for Benchmark API endpoints
 */

const API_PREFIX = '/benchmark/api';

window.BenchmarkUrls = {
    // LLM & Settings
    saveSettings: `${API_PREFIX}/settings/save/`,
    getDefaultSettings: `${API_PREFIX}/get_default_settings/`,
    testLlmConnection: `${API_PREFIX}/test_llm_connection/`,

    // API - Common / General
    webSearch: `${API_PREFIX}/web_search/`,

    // Metrics
    metrics: {
        calculate: `${API_PREFIX}/metrics/calculate/`,
        colors: `${API_PREFIX}/metrics/colors/`,
        schema: `${API_PREFIX}/metrics/schema/`
    },

    // Leaderboard
    leaderboard: {
        get: `${API_PREFIX}/leaderboard/`,
        getFiltered: (params) => {
            const queryString = new URLSearchParams(params).toString();
            return `${API_PREFIX}/leaderboard/${queryString ? '?' + queryString : ''}`;
        }
    },

    // Datasets
    datasets: {
        sync: `${API_PREFIX}/datasets/sync/`,
        upload: `${API_PREFIX}/datasets/upload/`,
        delete: (id) => `${API_PREFIX}/datasets/delete/${id}/`,
        activate: (id) => `${API_PREFIX}/datasets/activate/${id}/`
    },

    // Multi-turn Common
    multiTurn: {
        createSession: `${API_PREFIX}/sessions/create_session/`,
        createSessionGroup: `${API_PREFIX}/sessions/create_session_group/`,
        batchDeleteSessions: `${API_PREFIX}/sessions/batch_delete_sessions/`,
        deleteSessionGroup: (id) => `${API_PREFIX}/sessions/delete_session_group/${id}/`,
        renameSessionGroup: (id) => `${API_PREFIX}/sessions/rename_session_group/${id}/`,
        getSession: (id) => `${API_PREFIX}/sessions/get_session/${id}/`,
        runTrial: (id) => `${API_PREFIX}/sessions/run_trial/${id}/`,
        retrySession: (id) => `${API_PREFIX}/sessions/retry_session/${id}/`,
        deleteSession: (id) => `${API_PREFIX}/sessions/delete_session/${id}/`,
        stopSession: `${API_PREFIX}/sessions/stop_session/`,
        exportSession: (id) => `${API_PREFIX}/sessions/export_session/${id}/`,
        exportRun: (id) => `${API_PREFIX}/sessions/export_run/${id}/`,
        getTrialPrompt: (id) => `${API_PREFIX}/sessions/get_trial_prompt/${id}/`,
    },

    // Pipelines (Unified)
    pipeline: {
        start: (type) => `${API_PREFIX}/pipeline/start/${type}/`,
        stop: (type) => `${API_PREFIX}/pipeline/stop/${type}/`,
        loadRun: (type, id) => {
            const map = {
                'vanilla_llm': 'load_vanilla_run',
                'rag': 'load_rag_run',
                'vanilla_agent': 'load_agent_run',
                'browser_agent': 'load_agent_run'
            };
            return `${API_PREFIX}/sessions/${map[type] || 'load_vanilla_run'}/${id}/`;
        }
    },

    // Compatibility (Mapping to unified)
    vanillaLlmMultiTurn: {
        loadRun: (id) => `${API_PREFIX}/sessions/load_vanilla_run/${id}/`,
        runPipeline: `${API_PREFIX}/pipeline/start/vanilla_llm/`,
        stopPipeline: `${API_PREFIX}/pipeline/stop/vanilla_llm/`
    },
    ragMultiTurn: {
        loadRun: (id) => `${API_PREFIX}/sessions/load_rag_run/${id}/`,
        runPipeline: `${API_PREFIX}/pipeline/start/rag/`,
        stopPipeline: `${API_PREFIX}/pipeline/stop/rag/`
    },
    vanillaAgent: {
        loadRun: (id) => `${API_PREFIX}/sessions/load_agent_run/${id}/`,
        runPipeline: `${API_PREFIX}/pipeline/start/vanilla_agent/`,
        stopPipeline: `${API_PREFIX}/pipeline/stop/vanilla_agent/`
    },
    browserAgent: {
        loadRun: (id) => `${API_PREFIX}/sessions/load_agent_run/${id}/`,
        runPipeline: `${API_PREFIX}/pipeline/start/browser_agent/`,
        stopPipeline: `${API_PREFIX}/pipeline/stop/browser_agent/`
    }
};
