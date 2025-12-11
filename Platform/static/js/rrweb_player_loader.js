function enableAccordionButtons() {
    const allAccordionButtons = document.querySelectorAll('.accordion-button');
    allAccordionButtons.forEach(function(button) {
        button.disabled = false;
    });
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", enableAccordionButtons);
} else {
    enableAccordionButtons();
}

const loadedPlayers = new Map();

function debounce(func, delay) {
    let timeout;
    return function(...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, args), delay);
    };
}

function createPlayer(wrapper, events) {
    wrapper.innerHTML = '';
    if (!Array.isArray(events) || events.length === 0) {
        wrapper.innerHTML = '<p class="text-center text-muted">No recording data available.</p>';
        return null;
    }

    const recordedWidth = parseInt(wrapper.dataset.webpageWidth, 10);
    const recordedHeight = parseInt(wrapper.dataset.webpageHeight, 10);
    let recordedAspectRatio;

    if (recordedWidth && recordedHeight) {
        recordedAspectRatio = recordedHeight / recordedWidth;
    } else {
        const metaEvent = events.find(e => e.type === 2 && e.data.href);
        const fallbackWidth = metaEvent ? metaEvent.data.width : 1920;
        const fallbackHeight = metaEvent ? metaEvent.data.height : 1080;
        recordedAspectRatio = fallbackHeight / fallbackWidth;
    }

    const container = wrapper.closest('.accordion-body');
    if (container) {
        const containerWidth = container.clientWidth * 0.9;
        const calculatedHeight = containerWidth * recordedAspectRatio;

        const PlayerClass = (typeof rrwebPlayer === 'object' && rrwebPlayer.default) ? rrwebPlayer.default : rrwebPlayer;

        return new PlayerClass({
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
    return null;
}

const accordions = document.querySelectorAll('.accordion-collapse');
accordions.forEach(function(collapseEl) {
    collapseEl.addEventListener('shown.bs.collapse', function() {
        if (collapseEl.querySelector('.accordion-collapse')) {
            return;
        }

        const playerWrappers = collapseEl.querySelectorAll('.rrweb-player-wrapper');
        playerWrappers.forEach(function(wrapper, index) {
            setTimeout(function() {
                if (wrapper.dataset.loaded === 'true' || wrapper.childElementCount > 0) {
                    return;
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
                        const instance = createPlayer(wrapper, events);
                        if (instance) {
                            loadedPlayers.set(wrapper, { events, instance });
                        }
                    })
                    .catch(error => {
                        console.error('Error fetching rrweb record:', error);
                        wrapper.innerHTML = '<p class="text-center text-danger">Failed to load session replay.</p>';
                    })
                    .finally(() => {
                        if (parentContainer) parentContainer.classList.add('bg-light');
                    });
            }, index * 100);
        });
    });
});

window.addEventListener('resize', debounce(() => {
    loadedPlayers.forEach((data, wrapper) => {
        if (wrapper.offsetParent !== null) {
            if (data.instance && typeof data.instance.$destroy === 'function') {
                data.instance.$destroy();
            }
            const newInstance = createPlayer(wrapper, data.events);
            if (newInstance) {
                data.instance = newInstance;
            }
        }
    });
}, 250));