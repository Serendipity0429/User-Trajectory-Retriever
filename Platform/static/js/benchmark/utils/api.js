/**
 * API utilities for benchmark fetch operations
 * Provides common fetch patterns with CSRF token handling
 */

window.BenchmarkAPI = window.BenchmarkAPI || {};

/**
 * Get CSRF token from meta tag
 */
window.BenchmarkAPI.getCSRFToken = function() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') : '';
};

/**
 * Make a JSON POST request
 * @param {string} url - The URL to post to
 * @param {object} data - Data to send as JSON
 * @param {object} options - Additional options (signal for abort)
 * @returns {Promise<object>} Parsed JSON response
 */
window.BenchmarkAPI.post = function(url, data = {}, options = {}) {
    return fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': this.getCSRFToken()
        },
        body: JSON.stringify(data),
        signal: options.signal,
        keepalive: options.keepalive
    }).then(res => res.json());
};

/**
 * Make a GET request
 * @param {string} url - The URL to fetch
 * @param {object} options - Additional options (signal for abort)
 * @returns {Promise<object>} Parsed JSON response
 */
window.BenchmarkAPI.get = function(url, options = {}) {
    return fetch(url, { signal: options.signal }).then(res => res.json());
};

/**
 * Make a DELETE request
 * @param {string} url - The URL to delete
 * @returns {Promise<object>} Parsed JSON response
 */
window.BenchmarkAPI.delete = function(url) {
    return fetch(url, {
        method: 'DELETE',
        headers: { 'X-CSRFToken': this.getCSRFToken() }
    }).then(res => res.json());
};

/**
 * Make a FormData POST request (for pipelines)
 * @param {string} url - The URL to post to
 * @param {FormData} formData - FormData to send
 * @param {object} options - Additional options (signal for abort)
 * @returns {Promise<Response>} Raw response for streaming
 */
window.BenchmarkAPI.postForm = function(url, formData, options = {}) {
    return fetch(url, {
        method: 'POST',
        body: formData,
        signal: options.signal
    });
};

/**
 * Make a simple POST request with only CSRF token (no body)
 * @param {string} url - The URL to post to
 * @returns {Promise<object>} Parsed JSON response
 */
window.BenchmarkAPI.postSimple = function(url) {
    return fetch(url, {
        method: 'POST',
        headers: { 'X-CSRFToken': this.getCSRFToken() }
    }).then(res => res.json());
};

/**
 * Make a FormData POST request with CSRF token
 * @param {string} url - The URL to post to
 * @param {FormData} formData - FormData to send
 * @returns {Promise<object>} Parsed JSON response
 */
window.BenchmarkAPI.postFormData = function(url, formData) {
    return fetch(url, {
        method: 'POST',
        body: formData,
        headers: { 'X-CSRFToken': this.getCSRFToken() }
    }).then(res => res.json());
};
