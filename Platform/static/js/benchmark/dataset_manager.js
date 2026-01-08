document.addEventListener('DOMContentLoaded', function() {
    const datasetTableBody = document.getElementById('dataset-table-body');

    if (!datasetTableBody) {
        console.error("Dataset table body not found. Exiting dataset_manager.js");
        return;
    }

    const datasetCount = parseInt(datasetTableBody.dataset.count);

    function scanDatasets(silent = false) {
        const scanBtn = document.getElementById('scan-datasets-btn');
        let originalBtnHTML;

        if (scanBtn) {
            originalBtnHTML = scanBtn.innerHTML;
            if (!silent) {
                scanBtn.disabled = true;
                scanBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Scanning...';
            }
        }

        if (silent) {
            const spinner = document.getElementById('auto-scan-spinner');
            const emptyText = document.getElementById('empty-text');
            if (spinner && emptyText) {
                spinner.style.display = 'inline-block';
                emptyText.textContent = 'Auto-scanning data folder...';
            }
        }

        BenchmarkAPI.postSimple(BenchmarkUrls.datasets.sync)
            .then(data => {
                if (data.status === 'ok') {
                    if (data.added > 0) {
                        if (!silent) alert(`Successfully synced! Added ${data.added} new dataset(s).`);
                        window.location.reload();
                    } else {
                        if (!silent) alert('No new datasets found in the data/ folder.');
                        if (silent) {
                            const spinner = document.getElementById('auto-scan-spinner');
                            const emptyText = document.getElementById('empty-text');
                            if (spinner && emptyText) {
                                spinner.style.display = 'none';
                                emptyText.innerHTML = '<i class="bi bi-inbox fs-3 d-block mb-2 opacity-50"></i>No datasets available.';
                            }
                        }
                    }
                } else {
                    console.error('Sync failed:', data.message);
                    if (!silent) alert('Sync failed: ' + data.message);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                if (!silent) alert('An error occurred during sync.');
            })
            .finally(() => {
                if (scanBtn && !silent) {
                    scanBtn.disabled = false;
                    scanBtn.innerHTML = originalBtnHTML;
                }
            });
    }

    const uploadForm = document.getElementById('dataset-upload-form');
    if (uploadForm) {
        uploadForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const formData = new FormData(this);
            const btn = this.querySelector('button[type="submit"]');
            const originalHTML = btn.innerHTML;

            btn.disabled = true;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span> Uploading...';

            BenchmarkAPI.postFormData(BenchmarkUrls.datasets.upload, formData)
                .then(data => {
                    if (data.status === 'ok') {
                        window.location.reload();
                    } else {
                        alert('Upload failed: ' + JSON.stringify(data.errors));
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert('An error occurred during upload.');
                })
                .finally(() => {
                    btn.disabled = false;
                    btn.innerHTML = originalHTML;
                });
        });
    }

    document.querySelectorAll('.delete-dataset-btn').forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.stopPropagation();
            if (confirm('Are you sure you want to delete this dataset? This cannot be undone.')) {
                const datasetId = this.dataset.id;
                const row = this.closest('tr');
                const self = this;

                this.disabled = true;

                BenchmarkAPI.delete(BenchmarkUrls.datasets.delete(datasetId))
                    .then(data => {
                        if (data.status === 'ok') {
                            row.remove();
                            if (document.getElementById('dataset-table-body').children.length === 0) {
                                window.location.reload();
                            }
                        } else {
                            alert('Error deleting dataset: ' + data.message);
                            self.disabled = false;
                        }
                    })
                    .catch(error => {
                        console.error('Error:', error);
                        alert('An error occurred.');
                        self.disabled = false;
                    });
            }
        });
    });

    const scanBtn = document.getElementById('scan-datasets-btn');
    if (scanBtn) {
        scanBtn.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            scanDatasets(false);
        });
    }


    document.querySelectorAll('.activate-dataset-radio').forEach(radio => {
        radio.addEventListener('change', function(e) {
            e.stopPropagation();
            if (this.checked) {
                const datasetId = this.value;

                document.querySelectorAll('#dataset-table-body tr').forEach(row => row.classList.remove('table-primary'));
                this.closest('tr').classList.add('table-primary');

                BenchmarkAPI.postSimple(BenchmarkUrls.datasets.activate(datasetId))
                    .then(data => {
                        if (data.status !== 'ok') {
                            alert('Error activating dataset: ' + data.message);
                        }
                    })
                    .catch(error => {
                        console.error('Error:', error);
                        alert('An error occurred while activating the dataset.');
                    });
            }
        });
    });

    // Add click listener to table rows to activate the radio button
    document.querySelectorAll('.dataset-row').forEach(row => {
        row.addEventListener('click', function() {
            const radio = this.querySelector('.activate-dataset-radio');
            if (radio && !radio.checked) {
                radio.checked = true;
                // Manually trigger the change event as setting .checked = true doesn't always do it
                const changeEvent = new Event('change');
                radio.dispatchEvent(changeEvent);
            }
        });
    });

    if (datasetCount === 0) {
        scanDatasets(true);
    }
});
