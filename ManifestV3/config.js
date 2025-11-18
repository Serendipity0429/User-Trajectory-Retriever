// ManifestV3/config.js

// --- Default Configuration ---
const defaultConfig = {
    serverType: 'remote', // 'local' or 'remote'
    localServerAddress: 'http://127.0.0.1:8000',
    remoteServerAddress: 'http://101.6.41.59:32904',
    isPassiveMode: true,
    cancelTrialThreshold: 999, // TODO: temporarily banned cancellation feature, restore this in the formal study
    messageBoxSize: 'medium',
    messageBoxPosition: 'top-right',
    popupScale: 1,
    colorTheme: 'tsinghua-purple',
    customColor: '#671372',
    darkMode: false,
    request_timeout: 3000,
};

// --- Global Config Variable ---
let config = null;
let configInitialized = false;

// --- Initialization Function ---
async function initializeConfig() {
    if (configInitialized) return; // Prevent re-initialization
    configInitialized = true;

    // NOTICE: manually switch the development mode
    // const IS_DEV = false; // For production use, set to false
    const IS_DEV = true; // For development purposes, set to true

    const _get_local_config = (keys) => new Promise(resolve => chrome.storage.local.get(keys, resolve));
    const _set_local_config = (kv_pairs) => new Promise(resolve => chrome.storage.local.set(kv_pairs, resolve));

    const stored = await _get_local_config(['serverType', 'localServerAddress', 'remoteServerAddress']);
    
    const serverType = stored.serverType || defaultConfig.serverType;
    const localServerAddress = stored.localServerAddress || defaultConfig.localServerAddress;
    const remoteServerAddress = stored.remoteServerAddress || defaultConfig.remoteServerAddress;

    if (!stored.serverType || !stored.localServerAddress || !stored.remoteServerAddress) {
        await _set_local_config({ serverType, localServerAddress, remoteServerAddress });
    }

    const IS_REMOTE = serverType === 'remote';
    const URL_BASE = IS_REMOTE ? remoteServerAddress : localServerAddress;

    const URLS = {
        base: URL_BASE,
        health_check: `${URL_BASE}/user/health_check/`,
        login: `${URL_BASE}/user/login/`,
        token_login: `${URL_BASE}/api/user/token_login/`,
        token_refresh: `${URL_BASE}/api/user/token/refresh/`,
        data: `${URL_BASE}/task/data/`,
        cancel: `${URL_BASE}/task/cancel_annotation/`,
        active_task: `${URL_BASE}/task/active_task/`,
        get_task_info: `${URL_BASE}/task/get_task_info/`,
        register: `${URL_BASE}/user/signup/`,
        home: `${URL_BASE}/task/home/`,
        stop_annotation: `${URL_BASE}/task/stop_annotation/`,
        add_justification: `${URL_BASE}/task/justification/add/`,
        get_justifications: `${URL_BASE}/task/justification/get`,
        check_pending_annotations: `${URL_BASE}/task/check_pending_annotations/`,
        initial_page: "https://www.bing.com/",
    };

    config = {
        is_dev: IS_DEV,
        is_remote: IS_REMOTE,
        serverType: serverType,
        localServerAddress: localServerAddress,
        remoteServerAddress: remoteServerAddress,
        is_passive_mode: defaultConfig.isPassiveMode,
        urls: URLS,
        version: chrome.runtime.getManifest().version,
        max_retries: 3,
        cancel_trial_threshold: defaultConfig.cancelTrialThreshold,
    };
}

// --- Accessor Function ---
function getConfig() {
    if (!config) {
        console.error("Configuration has not been initialized. Please call initializeConfig() first.");
        return null;
    }
    return config;
}

// --- Automatic Update Listener ---
chrome.storage.onChanged.addListener((changes, namespace) => {
    if (namespace === 'local' && config) {
        let configChanged = false;
        const newSettings = {};

        if (changes.serverType) {
            newSettings.serverType = changes.serverType.newValue;
            configChanged = true;
        }
        if (changes.localServerAddress) {
            newSettings.localServerAddress = changes.localServerAddress.newValue;
            configChanged = true;
        }
        if (changes.remoteServerAddress) {
            newSettings.remoteServerAddress = changes.remoteServerAddress.newValue;
            configChanged = true;
        }

        if (configChanged) {
            console.log("Configuration changed in storage. Updating live config...");
            
            // Update the properties on the live config object
            Object.assign(config, newSettings);

            // Recalculate dependent properties
            config.is_remote = config.serverType === 'remote';
            const URL_BASE = config.is_remote ? config.remoteServerAddress : config.localServerAddress;
            
            config.urls.base = URL_BASE;
            config.urls.health_check = `${URL_BASE}/user/health_check/`;
            config.urls.login = `${URL_BASE}/user/login/`;
            config.urls.token_login = `${URL_BASE}/api/user/token_login/`;
            config.urls.token_refresh = `${URL_BASE}/api/user/token/refresh/`;
            config.urls.data = `${URL_BASE}/task/data/`;
            config.urls.cancel = `${URL_BASE}/task/cancel_annotation/`;
            config.urls.active_task = `${URL_BASE}/task/active_task/`;
            config.urls.get_task_info = `${URL_BASE}/task/get_task_info/`;
            config.urls.register = `${URL_BASE}/user/signup/`;
            config.urls.home = `${URL_BASE}/task/home/`;
            config.urls.stop_annotation = `${URL_BASE}/task/stop_annotation/`;
            config.urls.add_justification = `${URL_BASE}/task/justification/add/`;
            config.urls.get_justifications = `${URL_BASE}/task/justification/get`;
            config.urls.check_pending_annotations = `${URL_BASE}/task/check_pending_annotations/`;
        }
    }
});
