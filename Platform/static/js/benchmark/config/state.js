/**
 * Centralized state management for Benchmark application
 */

window.BenchmarkState = {
    config: {
        lastSavedBaseUrl: '',
        settingsInitialState: {}, // Stores the initial state of settings for change detection
        hasUnsavedChanges: false,
    },
    activeRun: {
        id: null,
        type: null, // 'multi_turn'
        data: null
    },
    ui: {}
};
