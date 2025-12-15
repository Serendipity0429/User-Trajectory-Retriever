document.addEventListener('DOMContentLoaded', function() {
    window.AgentBenchmark.init({
        pipelineType: 'browser_agent',
        csvPrefix: 'browser-agent',
        title: 'Browser Session',
        mainIconClass: 'bi-browser-chrome',
        mainColorClass: 'bg-info',
        textClass: 'text-info',
        loadingText: 'Agent is navigating...',
        runningText: 'Browser Agent is working...',
        stepIcons: {
            thought: 'bi-lightbulb',
            action: 'bi-mouse',
            observation: 'bi-eye',
            user: 'bi-person-circle',
            system: 'bi-gear',
            response: 'bi-chat-dots'
        }
    });
});