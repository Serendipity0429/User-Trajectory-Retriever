// Enable all accordion buttons once the script is loaded
const allAccordionButtons = document.querySelectorAll('.accordion-button');
allAccordionButtons.forEach(function(button) {
    button.disabled = false;
});

const accordions = document.querySelectorAll('.accordion-collapse');

accordions.forEach(function(collapseEl) {
    collapseEl.addEventListener('shown.bs.collapse', function () {
        // If the current accordion contains other accordions, don't load players here.
        // Let the event handlers on the nested accordions handle it.
        if (collapseEl.querySelector('.accordion-collapse')) {
            return;
        }

        const playerWrappers = collapseEl.querySelectorAll('.rrweb-player-wrapper');
        playerWrappers.forEach(function(wrapper, index) {
            setTimeout(function() {
                if (wrapper.dataset.loaded === 'true' || wrapper.childElementCount > 0) {
                    return; // Already loaded or loading
                }
                const webpageId = wrapper.dataset.webpageId;
                if (!webpageId) return;

                const parentContainer = wrapper.closest('.bg-light');
                if (parentContainer) parentContainer.classList.remove('bg-light');

                wrapper.dataset.loaded = 'true';
                wrapper.innerHTML = `
                    <style>
                        .loading-container { display: flex; flex-direction: column; justify-content: center; align-items: center; height: 200px; color: #6c757d; background-color: white !important; }
                        .loading-dots span { display: inline-block; width: 12px; height: 12px; background-color: #0d6efd; border-radius: 50%; margin: 0 4px; animation: pulsate 1.4s infinite ease-in-out both; }
                        .loading-dots span:nth-child(1) { animation-delay: -0.32s; }
                        .loading-dots span:nth-child(2) { animation-delay: -0.16s; }
                        @keyframes pulsate { 0%, 80%, 100% { transform: scale(0); } 40% { transform: scale(1.0); } }
                    </style>
                    <div class="loading-container">
                        <div class="loading-dots"><span></span><span></span><span></span></div>
                        <p class="mt-3">Loading Replay...</p>
                    </div>
                `;

                fetch(`/task/api/get_rrweb_record/${webpageId}/`)
                    .then(response => {
                        if (!response.ok) throw new Error('Network response was not ok');
                        return response.json();
                    })
                    .then(events => {
                        wrapper.innerHTML = '';
                        if (!Array.isArray(events) || events.length === 0) {
                            wrapper.innerHTML = '<p class="text-center text-muted">No recording data available.</p>';
                            return;
                        }
                        const container = wrapper.closest('.accordion-body');
                        if (container) {
                            const containerWidth = container.clientWidth * 0.9;
                            const screenRatio = window.innerHeight / window.innerWidth;
                            const calculatedHeight = containerWidth * screenRatio;
                            new rrwebPlayer({
                                target: wrapper,
                                props: {
                                    events: events,
                                    autoPlay: false,
                                    width: containerWidth,
                                    height: calculatedHeight,
                                    UNSAFE_replayCanvas: true,
                                },
                            });
                        }
                    })
                    .catch(error => {
                        console.error('Error fetching rrweb record:', error);
                        wrapper.innerHTML = '<p class="text-center text-danger">Failed to load session replay.</p>';
                    })
                    .finally(() => {
                        if (parentContainer) parentContainer.classList.add('bg-light');
                    });
            }, index * 100); // 200ms delay between each request
        });
    });
});
