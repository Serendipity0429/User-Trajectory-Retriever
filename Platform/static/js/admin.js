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
                form.reset();
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

    // Initialize all components
    initConsentModal();
    initPartialUpdates();
    initUserActions();
});