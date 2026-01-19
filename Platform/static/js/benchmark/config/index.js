/**
 * Benchmark Configuration - Unified Entry Point
 *
 * This file consolidates all configuration into a single namespace while
 * maintaining backward compatibility with existing code.
 *
 * Usage:
 *   BenchmarkConfig.urls.multiTurn.createSession
 *   BenchmarkConfig.pipelines.get('vanilla_llm')
 *   BenchmarkConfig.settings.groups.llm
 *   BenchmarkConfig.state.activeRun
 *
 * Legacy aliases (still work):
 *   BenchmarkUrls, BenchmarkState, BenchmarkPipelineConfig, BenchmarkSettingsConfig
 */

window.BenchmarkConfig = {
    // Re-export all sub-configs
    get urls() { return window.BenchmarkUrls; },
    get pipelines() { return window.BenchmarkPipelineConfig; },
    get settings() { return window.BenchmarkSettingsConfig; },
    get state() { return window.BenchmarkState; },

    // Convenience methods
    getPipelineUrl(type, action, id) {
        const urls = window.BenchmarkUrls;
        switch (action) {
            case 'start': return urls.pipeline.start(type);
            case 'stop': return urls.pipeline.stop(type);
            case 'load': return urls.pipeline.loadRun(type, id);
            default: return null;
        }
    },

    getPipelineStyle(type) {
        return window.BenchmarkPipelineConfig.get(type);
    },

    getSettingsWhitelist(pipelineType) {
        return window.BenchmarkSettingsConfig.buildWhitelist(pipelineType);
    }
};
