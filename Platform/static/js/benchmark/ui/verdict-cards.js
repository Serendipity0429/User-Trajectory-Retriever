/**
 * Verdict Cards UI Component
 * Renders trial verdict cards for LLM and Rule-based evaluation results
 */

window.BenchmarkUI.VerdictCards = {
    VERDICT_CONFIG: {
        correct: { color: 'success', icon: 'bi-check-circle-fill' },
        incorrect: { color: 'danger', icon: 'bi-x-circle-fill' }
    },

    /**
     * Render trial verdict cards for LLM and Rule verdicts
     */
    render: function(trial) {
        const isCorrectLLM = trial.is_correct_llm;
        const isCorrectRule = trial.is_correct_rule;

        if (isCorrectLLM === undefined && isCorrectRule === undefined) return null;

        const container = BenchmarkUtils.renderTemplate('tpl-trial-verdict-container');

        if (isCorrectLLM !== undefined && isCorrectLLM !== null) {
            container.appendChild(this._createVerdictCard(isCorrectLLM, 'LLM'));
        }

        if (isCorrectRule !== undefined && isCorrectRule !== null) {
            container.appendChild(this._createVerdictCard(isCorrectRule, 'Rule'));
        }

        return container;
    },

    _createVerdictCard: function(isCorrect, label) {
        const config = isCorrect ? this.VERDICT_CONFIG.correct : this.VERDICT_CONFIG.incorrect;
        const verdictText = isCorrect ? 'Correct' : 'Incorrect';

        return BenchmarkUtils.renderTemplate('tpl-trial-verdict-card', {
            '.verdict-icon': { addClass: `${config.icon} text-${config.color}` },
            '.verdict-text': { addClass: `text-${config.color}`, text: `Verdict (${label}): ${verdictText}` }
        });
    }
};
