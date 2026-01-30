document.addEventListener('DOMContentLoaded', function() {
    // Helpers
    const getCsrfToken = (form) => form.querySelector('input[name="csrfmiddlewaretoken"]').value;

    // Consent Modal
    const initConsentModal = () => {
        const viewConsentModal = document.getElementById('viewConsentModal');
        if (!viewConsentModal) return;

        const url = viewConsentModal.dataset.url;
        if (!url) {
            console.error('Consent modal URL not found.');
            return;
        }

        viewConsentModal.addEventListener('show.bs.modal', function () {
            fetch(url)
                .then(response => response.json())
                .then(data => {
                    const versionEl = document.getElementById('consent-version');
                    const dateEl = document.getElementById('consent-date');
                    const statsEl = document.getElementById('consent-stats');
                    const contentEl = document.getElementById('consent-content');

                    if (data.error) {
                        versionEl.textContent = 'N/A';
                        dateEl.textContent = 'N/A';
                        statsEl.textContent = 'N/A';
                        contentEl.innerHTML = `<div class="text-danger p-3">${data.error}</div>`;
                    } else {
                        versionEl.textContent = `v${data.version}`;
                        dateEl.textContent = data.created_at;
                        statsEl.textContent = `${data.signed_users_count} / ${data.total_users_count}`;
                        contentEl.innerHTML = data.content;
                    }
                })
                .catch(error => {
                    console.error('Error fetching consent data:', error);
                    document.getElementById('consent-content').innerHTML = `<div class="text-danger p-3">Error loading content.</div>`;
                });
        });
    };

    // Partial Table Updates
    const initPartialUpdates = () => {
        const updateContainer = (url, containerId) => {
            const container = document.getElementById(containerId);
            if (!container) return;

            const ajaxUrl = new URL(url, window.location.origin);
            ajaxUrl.searchParams.set('partial', containerId);

            fetch(ajaxUrl.toString(), {
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            })
            .then(response => response.text())
            .then(html => {
                container.innerHTML = html;
                const historyUrl = new URL(url, window.location.origin);
                window.history.pushState({ path: historyUrl.toString() }, '', historyUrl.toString());
            })
            .catch(error => console.error(`Error updating container ${containerId}:`, error));
        };

        document.body.addEventListener('submit', function(e) {
            const form = e.target;
            if (form.id === 'user-filter-form' || form.id === 'task-filter-form') {
                e.preventDefault();
                const params = new URLSearchParams(new FormData(form));
                const url = `${form.action}?${params.toString()}`;
                const containerId = form.id === 'user-filter-form' ? 'user-table-container' : 'task-table-container';
                updateContainer(url, containerId);
            }
        });

        document.body.addEventListener('click', function(e) {
            const link = e.target.closest('#user-table-container a, #task-table-container a');
            if (link && (link.classList.contains('page-link') || link.closest('thead'))) {
                e.preventDefault();
                const containerId = link.closest('#user-table-container') ? 'user-table-container' : 'task-table-container';
                updateContainer(link.href, containerId);
            }

            if (e.target.id === 'clear-task-filter-btn') {
                e.preventDefault();
                const form = document.getElementById('task-filter-form');
                // Manually clear inputs to ensure filters are removed, as reset() reverts to default values (server-rendered)
                form.querySelectorAll('input:not([type="hidden"]), select').forEach(input => {
                    input.value = '';
                });
                form.dispatchEvent(new Event('submit', { cancelable: true }));
            }
        });
    };

    // User Actions (Superuser toggle, Delete)
    const initUserActions = () => {
        const userManagementContainer = document.getElementById('userManagementCollapse');
        if (!userManagementContainer) return;

        userManagementContainer.addEventListener('click', function(event) {
            const button = event.target.closest('.user-action-btn');
            if (!button) return;

            const url = button.dataset.actionUrl;
            const method = button.dataset.actionMethod || 'POST';
            const confirmation = button.dataset.confirm;

            if (confirmation && !confirm(confirmation)) {
                return;
            }

            performUserAction(url, method, button);
        });

        const performUserAction = (url, method, button) => {
            const csrfToken = document.querySelector('input[name="csrfmiddlewaretoken"]').value;
            const userRow = button.closest('tr');

            fetch(url, {
                method: method,
                headers: {
                    'X-CSRFToken': csrfToken,
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                },
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    if (url.includes('toggle_superuser')) {
                        const statusBadge = userRow.querySelector('.badge');
                        if (data.is_superuser) {
                            button.innerHTML = '<i class="bi bi-person-dash me-2"></i>Demote';
                            statusBadge.textContent = 'Yes';
                            statusBadge.classList.replace('bg-secondary', 'bg-success');
                        } else {
                            button.innerHTML = '<i class="bi bi-person-plus me-2"></i>Promote';
                            statusBadge.textContent = 'No';
                            statusBadge.classList.replace('bg-success', 'bg-secondary');
                        }
                    } else if (url.includes('delete_user')) {
                        userRow.remove();
                    }
                } else {
                    alert(data.message || 'An error occurred.');
                }
            })
            .catch(error => console.error('Error performing user action:', error));
        };
    };

    // Data Export/Import
    const initDataExportImport = () => {
        const exportPanel = document.getElementById('export-panel');
        const importPanel = document.getElementById('import-panel');
        if (!exportPanel && !importPanel) return;

        const getCsrfToken = () => document.querySelector('input[name="csrfmiddlewaretoken"]')?.value || '';

        // === EXPORT FUNCTIONALITY ===
        if (exportPanel) {
            let availableDatasets = [];
            let availableUsers = [];
            let excludedDatasetIds = new Set();
            let selectedUserIds = new Set();

            const datasetListContainer = document.getElementById('export-dataset-list');
            const userListContainer = document.getElementById('export-user-list');
            const userListOverlay = document.getElementById('export-user-list-overlay');
            const selectAllBtn = document.getElementById('export-select-all');
            const deselectAllBtn = document.getElementById('export-deselect-all');
            const selectedCountEl = document.getElementById('export-selected-count');
            const anonymizeCheckbox = document.getElementById('export-anonymize');
            const previewBtn = document.getElementById('export-preview-btn');
            const downloadBtn = document.getElementById('export-download-btn');
            const previewSection = document.getElementById('export-preview');

            let isInitialLoad = true;

            const updateSelectedCount = () => {
                const count = selectedUserIds.size;
                selectedCountEl.textContent = `${count} user${count !== 1 ? 's' : ''} selected`;
                downloadBtn.disabled = count === 0;
            };

            const getExcludedDatasets = () => Array.from(excludedDatasetIds).join(',');

            const renderDatasetList = () => {
                if (availableDatasets.length === 0) {
                    datasetListContainer.innerHTML = '<div class="text-muted text-center py-2">No datasets found.</div>';
                    return;
                }

                let html = '';
                availableDatasets.forEach(ds => {
                    const checked = !excludedDatasetIds.has(ds.id) ? 'checked' : '';
                    const tutorialBadge = ds.is_tutorial ? '<span class="badge bg-warning text-dark ms-1">Tutorial</span>' : '';
                    html += `
                        <div class="form-check">
                            <input class="form-check-input export-dataset-checkbox" type="checkbox" data-dataset-id="${ds.id}" ${checked}>
                            <label class="form-check-label">
                                ${ds.name}${tutorialBadge}
                                <small class="text-muted">(${ds.task_count} tasks)</small>
                            </label>
                        </div>`;
                });
                datasetListContainer.innerHTML = html;

                // Attach checkbox listeners
                datasetListContainer.querySelectorAll('.export-dataset-checkbox').forEach(cb => {
                    cb.addEventListener('change', function() {
                        const datasetId = parseInt(this.dataset.datasetId);
                        if (this.checked) {
                            excludedDatasetIds.delete(datasetId);
                        } else {
                            excludedDatasetIds.add(datasetId);
                        }
                        // Reload users when dataset selection changes
                        loadUsers();
                    });
                });
            };

            const renderUserList = () => {
                if (availableUsers.length === 0) {
                    userListContainer.innerHTML = '<div class="text-muted text-center py-3">No users with finished tasks found.</div>';
                    return;
                }

                let html = '<table class="table table-sm table-hover mb-0"><thead><tr><th style="width: 40px;"></th><th>Username</th><th class="d-none d-md-table-cell">Email</th><th>Tasks</th></tr></thead><tbody>';
                availableUsers.forEach(user => {
                    const checked = selectedUserIds.has(user.id) ? 'checked' : '';
                    html += `
                        <tr>
                            <td><input type="checkbox" class="form-check-input export-user-checkbox" data-user-id="${user.id}" ${checked}></td>
                            <td>${user.username}</td>
                            <td class="d-none d-md-table-cell text-muted small">${user.email}</td>
                            <td><span class="badge bg-secondary">${user.task_count}</span></td>
                        </tr>`;
                });
                html += '</tbody></table>';
                userListContainer.innerHTML = html;

                // Attach checkbox listeners
                userListContainer.querySelectorAll('.export-user-checkbox').forEach(cb => {
                    cb.addEventListener('change', function() {
                        const userId = parseInt(this.dataset.userId);
                        if (this.checked) {
                            selectedUserIds.add(userId);
                        } else {
                            selectedUserIds.delete(userId);
                        }
                        updateSelectedCount();
                    });
                });
            };

            const loadUsers = () => {
                // Show overlay for subsequent loads, spinner for initial load
                if (isInitialLoad) {
                    userListContainer.innerHTML = '<div class="text-center py-3"><div class="spinner-border spinner-border-sm text-primary" role="status"></div><span class="ms-2">Loading users...</span></div>';
                } else {
                    userListOverlay.style.cssText = 'display: flex !important;';
                }

                const excludeParam = getExcludedDatasets();
                const url = excludeParam ? `/dashboard/export/users/?exclude_datasets=${excludeParam}` : '/dashboard/export/users/';

                fetch(url)
                    .then(res => res.json())
                    .then(data => {
                        availableUsers = data.users || [];
                        // Keep existing selections that are still valid
                        const validUserIds = new Set(availableUsers.map(u => u.id));
                        selectedUserIds = new Set([...selectedUserIds].filter(id => validUserIds.has(id)));
                        // If no selections, select all by default
                        if (selectedUserIds.size === 0) {
                            availableUsers.forEach(u => selectedUserIds.add(u.id));
                        }
                        renderUserList();
                        updateSelectedCount();
                        isInitialLoad = false;
                    })
                    .catch(err => {
                        userListContainer.innerHTML = '<div class="text-danger text-center py-3">Error loading users.</div>';
                        console.error('Error loading users:', err);
                    })
                    .finally(() => {
                        userListOverlay.style.cssText = 'display: none !important;';
                    });
            };

            // Load datasets first
            fetch('/dashboard/export/datasets/')
                .then(res => res.json())
                .then(data => {
                    availableDatasets = data.datasets || [];
                    // Exclude tutorial datasets by default
                    availableDatasets.forEach(ds => {
                        if (ds.is_tutorial) {
                            excludedDatasetIds.add(ds.id);
                        }
                    });
                    renderDatasetList();
                    // Then load users
                    loadUsers();
                })
                .catch(err => {
                    datasetListContainer.innerHTML = '<div class="text-danger text-center py-2">Error loading datasets.</div>';
                    console.error('Error loading datasets:', err);
                    // Still try to load users
                    loadUsers();
                });

            selectAllBtn.addEventListener('click', () => {
                availableUsers.forEach(u => selectedUserIds.add(u.id));
                renderUserList();
                updateSelectedCount();
            });

            deselectAllBtn.addEventListener('click', () => {
                selectedUserIds.clear();
                renderUserList();
                updateSelectedCount();
            });

            previewBtn.addEventListener('click', () => {
                const requestBody = {
                    user_ids: Array.from(selectedUserIds),
                    anonymize: anonymizeCheckbox.checked,
                    exclude_datasets: Array.from(excludedDatasetIds)
                };

                previewBtn.disabled = true;
                previewBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Loading...';

                fetch('/dashboard/export/preview/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken(),
                    },
                    body: JSON.stringify(requestBody),
                })
                    .then(res => res.json())
                    .then(data => {
                        if (data.error) {
                            alert(data.error);
                            return;
                        }
                        const p = data.preview;
                        document.getElementById('preview-participants').textContent = p.participant_count;
                        document.getElementById('preview-tasks').textContent = p.task_count;
                        document.getElementById('preview-trials').textContent = p.trial_count;
                        document.getElementById('preview-webpages').textContent = p.webpage_count;
                        previewSection.style.display = 'block';
                    })
                    .catch(err => {
                        alert('Error fetching preview.');
                        console.error(err);
                    })
                    .finally(() => {
                        previewBtn.disabled = false;
                        previewBtn.innerHTML = '<i class="bi bi-eye me-1"></i> Preview';
                    });
            });

            downloadBtn.addEventListener('click', () => {
                const requestBody = {
                    user_ids: Array.from(selectedUserIds),
                    anonymize: anonymizeCheckbox.checked,
                    exclude_datasets: Array.from(excludedDatasetIds)
                };

                downloadBtn.disabled = true;
                downloadBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Preparing...';

                // Use POST with JSON body to avoid URL length limits
                fetch('/dashboard/export/download/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken(),
                    },
                    body: JSON.stringify(requestBody),
                })
                    .then(response => {
                        if (!response.ok) {
                            throw new Error('Export failed');
                        }
                        // Get filename from Content-Disposition header or use default
                        const disposition = response.headers.get('Content-Disposition');
                        let filename = 'task_data_export.zip';
                        if (disposition && disposition.includes('filename=')) {
                            const match = disposition.match(/filename="?([^";\n]+)"?/);
                            if (match) filename = match[1];
                        }
                        return response.blob().then(blob => ({ blob, filename }));
                    })
                    .then(({ blob, filename }) => {
                        // Create blob URL and trigger download
                        const url = window.URL.createObjectURL(blob);
                        const link = document.createElement('a');
                        link.href = url;
                        link.download = filename;
                        document.body.appendChild(link);
                        link.click();
                        document.body.removeChild(link);
                        window.URL.revokeObjectURL(url);
                    })
                    .catch(err => {
                        alert('Error downloading export: ' + err.message);
                        console.error('Download error:', err);
                    })
                    .finally(() => {
                        downloadBtn.disabled = false;
                        downloadBtn.innerHTML = '<i class="bi bi-download me-1"></i> Download Export';
                    });
            });
        }

        // === IMPORT FUNCTIONALITY ===
        if (importPanel) {
            const fileInput = document.getElementById('import-file');
            const validateBtn = document.getElementById('import-validate-btn');
            const importPreview = document.getElementById('import-preview');
            const importAuth = document.getElementById('import-auth');
            const importPassword = document.getElementById('import-password');
            const executeBtn = document.getElementById('import-execute-btn');
            const importResult = document.getElementById('import-result');
            const importError = document.getElementById('import-error');

            fileInput.addEventListener('change', () => {
                validateBtn.disabled = !fileInput.files.length;
                importPreview.style.display = 'none';
                importAuth.style.display = 'none';
                importResult.style.display = 'none';
                importError.style.display = 'none';
            });

            validateBtn.addEventListener('click', () => {
                if (!fileInput.files.length) return;

                const formData = new FormData();
                formData.append('file', fileInput.files[0]);

                validateBtn.disabled = true;
                validateBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Validating...';

                fetch('/dashboard/import/preview/', {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': getCsrfToken(),
                    },
                    body: formData,
                })
                .then(res => res.json())
                .then(data => {
                    if (data.error) {
                        importError.style.display = 'block';
                        document.getElementById('import-error-message').textContent = data.error;
                        return;
                    }

                    if (!data.is_valid) {
                        importError.style.display = 'block';
                        const errors = data.errors.slice(0, 5).join('; ');
                        document.getElementById('import-error-message').textContent = errors;
                        return;
                    }

                    // Show preview
                    document.getElementById('delete-users').textContent = data.would_delete.users;
                    document.getElementById('delete-tasks').textContent = data.would_delete.tasks;
                    document.getElementById('delete-webpages').textContent = data.would_delete.webpages;
                    document.getElementById('import-participants').textContent = data.would_import.participants;
                    document.getElementById('import-tasks').textContent = data.would_import.tasks;
                    document.getElementById('import-webpages').textContent = data.would_import.webpages;

                    importPreview.style.display = 'block';
                    importAuth.style.display = 'block';
                })
                .catch(err => {
                    importError.style.display = 'block';
                    document.getElementById('import-error-message').textContent = 'Error validating file.';
                    console.error(err);
                })
                .finally(() => {
                    validateBtn.disabled = false;
                    validateBtn.innerHTML = '<i class="bi bi-check-circle me-1"></i> Validate & Preview';
                });
            });

            executeBtn.addEventListener('click', () => {
                const password = importPassword.value;
                if (!password) {
                    alert('Please enter your password.');
                    return;
                }

                if (!confirm('Are you sure you want to proceed? This will DELETE all existing data.')) {
                    return;
                }

                executeBtn.disabled = true;
                executeBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Importing...';

                fetch('/dashboard/import/execute/', {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': getCsrfToken(),
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ password }),
                })
                .then(res => res.json())
                .then(data => {
                    if (data.error) {
                        importError.style.display = 'block';
                        document.getElementById('import-error-message').textContent = data.error;
                        return;
                    }

                    if (data.success) {
                        importAuth.style.display = 'none';
                        importResult.style.display = 'block';
                        document.getElementById('result-participants').textContent = data.stats.participants_imported;
                        document.getElementById('result-tasks').textContent = data.stats.tasks_imported;
                        document.getElementById('result-trials').textContent = data.stats.trials_imported;
                        document.getElementById('result-webpages').textContent = data.stats.webpages_imported;
                    }
                })
                .catch(err => {
                    importError.style.display = 'block';
                    document.getElementById('import-error-message').textContent = 'Error during import.';
                    console.error(err);
                })
                .finally(() => {
                    executeBtn.disabled = false;
                    executeBtn.innerHTML = '<i class="bi bi-database-fill-up me-1"></i> Execute Import';
                });
            });
        }
    };

    // Initialize all components
    initConsentModal();
    initPartialUpdates();
    initUserActions();
    initDataExportImport();
});