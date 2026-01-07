/**
 * Data export utilities for CSV and JSON formats
 */

window.BenchmarkExport = window.BenchmarkExport || {};

/**
 * Generate a filename suffix from UI or timestamp
 * @param {string} filenamePrefix - Prefix for the filename
 * @returns {string} Complete filename with suffix
 */
function _generateFilename(filenamePrefix) {
    let nameSuffix = '';
    const resultsHeader = document.getElementById("results-header-text");
    if (resultsHeader && resultsHeader.textContent) {
        nameSuffix = resultsHeader.textContent.replace('Results for', '').trim();
    }
    if (!nameSuffix) {
        nameSuffix = new Date().toISOString().slice(0, 19).replace('T', '_').replace(/:/g, '-');
    }
    return `${filenamePrefix}-${nameSuffix.replace(/[^a-zA-Z0-9-_]/g, '_')}`;
}

/**
 * Download a blob as a file
 * @param {Blob} blob - The blob to download
 * @param {string} filename - The filename to save as
 */
function _downloadBlob(blob, filename) {
    const link = document.createElement("a");
    if (link.download !== undefined) {
        const url = URL.createObjectURL(blob);
        link.setAttribute("href", url);
        link.setAttribute("download", filename);
        link.style.visibility = 'hidden';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }
}

/**
 * Export data to CSV
 * @param {Array} data - Array of data objects
 * @param {string} filenamePrefix - Prefix for the filename
 * @param {Array} headers - Array of header strings
 * @param {Function} rowMapper - Function that takes a data item and index, returns an array of cell values
 */
window.BenchmarkExport.exportToCSV = function(data, filenamePrefix, headers, rowMapper) {
    if (!data || data.length === 0) {
        alert("No results to export.");
        return;
    }

    const csvRows = [headers.join(',')];

    data.forEach((item, index) => {
        const rowValues = rowMapper(item, index);
        // Escape quotes and wrap in quotes
        const escapedRow = rowValues.map(val => {
            if (val === null || val === undefined) return '';
            const str = String(val);
            return `"${str.replace(/"/g, '""')}"`;
        });
        csvRows.push(escapedRow.join(','));
    });

    const csvString = csvRows.join('\n');
    const blob = new Blob([csvString], { type: 'text/csv;charset=utf-8;' });
    const filename = _generateFilename(filenamePrefix) + '.csv';

    _downloadBlob(blob, filename);
}

/**
 * Export data to JSON
 * @param {Array} data - Array of data objects
 * @param {string} filenamePrefix - Prefix for the filename
 */
window.BenchmarkExport.exportToJSON = function(data, filenamePrefix) {
    if (!data || data.length === 0) {
        alert("No results to export.");
        return;
    }

    const jsonString = JSON.stringify(data, null, 2);
    const blob = new Blob([jsonString], { type: 'application/json;charset=utf-8;' });
    const filename = _generateFilename(filenamePrefix) + '.json';

    _downloadBlob(blob, filename);
}
