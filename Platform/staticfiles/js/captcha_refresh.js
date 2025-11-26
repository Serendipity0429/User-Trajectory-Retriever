document.addEventListener('DOMContentLoaded', function() {
    // Function to attach click event to captcha images
    function setupCaptchaRefresh() {
        const captchaImages = document.querySelectorAll('img.captcha');

        captchaImages.forEach(function(img) {
            // Check if we already attached the event to avoid duplicates
            if (img.dataset.refreshAttached) return;

            img.style.cursor = 'pointer';
            img.title = 'Click to refresh';
            img.dataset.refreshAttached = 'true';

            img.addEventListener('click', function() {
                const form = img.closest('form');
                const refreshUrl = '/captcha/refresh/';

                // Add a loading effect if desired, or just fetch
                img.style.opacity = '0.5';

                fetch(refreshUrl, {
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                })
                .then(response => response.json())
                .then(data => {
                    img.src = data.image_url;
                    img.style.opacity = '1';
                    
                    // Find the hidden input field associated with this captcha
                    // Usually it is in the same form, name="captcha_0"
                    const hiddenInput = form.querySelector('input[name="captcha_0"]');
                    if (hiddenInput) {
                        hiddenInput.value = data.key;
                    }
                })
                .catch(error => {
                    console.error('Error refreshing captcha:', error);
                    img.style.opacity = '1';
                });
            });
        });
    }

    // Initial setup
    setupCaptchaRefresh();

    // If using HTMX or other dynamic content loading, you might need to re-run setupCaptchaRefresh()
    // For now, just running it on DOMContentLoaded is enough for standard Django views.
});
