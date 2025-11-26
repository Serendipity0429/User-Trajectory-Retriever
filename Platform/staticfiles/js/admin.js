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
        });
    };

    // User Actions (Superuser toggle, Delete)
    const initUserActions = () => {
        const userManagementContainer = document.getElementById('userManagementCollapse');
        if (!userManagementContainer) return;

        userManagementContainer.addEventListener('submit', function(event) {
            const form = event.target;
            
            if (form.matches('form[action*="toggle_superuser"]')) {
                event.preventDefault();
                handleToggleSuperuser(form);
            } else if (form.matches('form[action*="delete_user"]')) {
                event.preventDefault();
                handleDeleteUser(form);
            }
        });

        const handleToggleSuperuser = (form) => {
            const url = form.action;
            const csrfToken = getCsrfToken(form);
            const button = form.querySelector('button[type="submit"]');
            const userRow = form.closest('tr');
            const statusBadge = userRow.querySelector('.badge');

            fetch(url, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrfToken,
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                },
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    if (data.is_superuser) {
                        button.textContent = 'Demote';
                        statusBadge.textContent = 'Yes';
                        statusBadge.classList.replace('bg-secondary', 'bg-success');
                    } else {
                        button.textContent = 'Promote';
                        statusBadge.textContent = 'No';
                        statusBadge.classList.replace('bg-success', 'bg-secondary');
                    }
                } else {
                    alert(data.message || 'An error occurred during superuser toggle.');
                }
            })
            .catch(error => console.error('Error toggling superuser:', error));
        };

        const handleDeleteUser = (form) => {
            if (confirm('Are you sure you want to delete this user?')) {
                const url = form.action;
                const csrfToken = getCsrfToken(form);
                const userRow = form.closest('tr');

                fetch(url, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': csrfToken,
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                })
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success') {
                        userRow.remove();
                    } else {
                        alert(data.message || 'An error occurred while deleting the user.');
                    }
                })
                .catch(error => console.error('Error deleting user:', error));
            }
        };
    };

    // Initialize all components
    initConsentModal();
    initPartialUpdates();
    initUserActions();
});