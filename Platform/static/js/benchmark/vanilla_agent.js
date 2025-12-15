document.addEventListener('DOMContentLoaded', function() {
    window.AgentBenchmark.init({
        pipelineType: 'vanilla_agent',
        csvPrefix: 'vanilla-agent',
        title: 'Vanilla Agent Trajectory',
        mainIconClass: 'bi-robot',
        mainColorClass: 'bg-primary',
        textClass: 'text-primary',
        loadingText: 'Agent is thinking...',
        runningText: 'Agent is working...',
        stepIcons: {
            thought: 'bi-lightbulb',
            action: 'bi-terminal',
            observation: 'bi-hdd-network',
            user: 'bi-person-circle',
            system: 'bi-gear',
            response: 'bi-chat-dots'
        }
    });
});