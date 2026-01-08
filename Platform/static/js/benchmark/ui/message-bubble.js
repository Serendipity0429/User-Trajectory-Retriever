/**
 * Message Bubble UI Component
 * Creates chat-style message bubbles for user, system, and assistant roles
 */

window.BenchmarkUI.MessageBubble = {
    ROLE_CONFIG: {
        user: {
            alignment: 'justify-content-end',
            bubbleClass: 'bg-white shadow-sm border text-dark',
            icon: 'bi-person-fill',
            showIcon: true,
            iconSide: 'right'
        },
        system: {
            alignment: 'justify-content-center',
            bubbleClass: 'bg-light text-muted',
            icon: 'bi-gear-fill',
            showIcon: false
        },
        assistant: {
            alignment: 'justify-content-start',
            bubbleClass: 'bg-white border shadow-sm',
            icon: 'bi-robot',
            showIcon: true,
            iconSide: 'left'
        }
    },

    /**
     * Create a message bubble for chat-style display
     * @param {string} role - 'user', 'system', or 'assistant'
     * @param {string} content - HTML content for the bubble
     * @param {string} extraBubbleClass - Additional CSS classes for bubble
     * @param {string} overrideIcon - Override default icon
     * @returns {HTMLElement} Message row element
     */
    create: function(role, content, extraBubbleClass = '', overrideIcon = null) {
        const config = this.ROLE_CONFIG[role] || this.ROLE_CONFIG.assistant;
        const iconClass = overrideIcon || config.icon;

        const row = document.createElement('div');
        row.className = `d-flex ${config.alignment} mb-3 message-bubble`;

        // Icon element
        let iconEl = null;
        if (config.showIcon) {
            iconEl = document.createElement('div');
            iconEl.className = `d-flex align-items-start ${config.iconSide === 'left' ? 'me-2' : 'ms-2'}`;
            iconEl.innerHTML = `<span class="badge rounded-circle border text-secondary p-2"><i class="bi ${iconClass}"></i></span>`;
        }

        // Bubble element
        const bubble = document.createElement('div');
        bubble.className = `p-3 rounded-3 ${config.bubbleClass} ${extraBubbleClass}`.trim();
        bubble.style.maxWidth = '85%';
        bubble.innerHTML = content;

        // Assemble
        if (config.iconSide === 'left' && iconEl) row.appendChild(iconEl);
        row.appendChild(bubble);
        if (config.iconSide === 'right' && iconEl) row.appendChild(iconEl);

        return row;
    }
};
