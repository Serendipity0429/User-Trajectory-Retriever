from ..utils import PROMPTS, has_builtin_thinking
from ..models import MultiTurnSession
from .base import BaseMultiTurnPipeline, REDIS_PREFIX_VANILLA_MULTI_TURN

class VanillaLLMMultiTurnPipeline(BaseMultiTurnPipeline):
    def __init__(self, base_url, api_key, model, max_retries, pipeline_id=None, dataset_id=None, group_id=None, rerun_errors=True):
        super().__init__(base_url, api_key, model, max_retries, pipeline_id, dataset_id, group_id, rerun_errors)
        self.redis_prefix = REDIS_PREFIX_VANILLA_MULTI_TURN

    def __str__(self):
        return "Vanilla LLM Multi-Turn Pipeline"

    def create_session(self, settings, question_text, ground_truths, group):
        return MultiTurnSession.objects.create(
            question=question_text,
            ground_truths=ground_truths,
            run=group,
            run_tag=self.pipeline_id,
            pipeline_type='vanilla_llm'
        )

    def get_pipeline_type_name(self):
        return 'vanilla_llm'

    def _construct_messages(self, session, trial, completed_trials):
        messages = []

        # Get settings
        settings = session.run.settings if session.run else None
        allow_reasoning = settings.allow_reasoning if settings else False

        # 1. System prompt - add CoT instructions only for non-thinking models
        sys_prompt = PROMPTS["vanilla_system_prompt"]
        model_name = settings.llm_model if settings else ""
        if allow_reasoning and not has_builtin_thinking(model_name):
            sys_prompt += PROMPTS["shared_reasoning_instruction"]

        messages.append({"role": "system", "content": sys_prompt})
        messages.append({"role": "user", "content": PROMPTS["shared_user_question"].format(question=session.question)})

        # 2. History
        for i, past_trial in enumerate(completed_trials):
            past_log = past_trial.log or {}
            past_messages = past_log.get('messages', [])
            assistant_response = next((m.get('content') for m in reversed(past_messages) if m.get('role') == 'assistant'), None)
            if assistant_response:
                messages.append({"role": "assistant", "content": assistant_response})
            elif past_trial.answer:
                messages.append({"role": "assistant", "content": past_trial.answer})
            if i < len(completed_trials) - 1:
                messages.append({"role": "user", "content": PROMPTS["shared_retry_request"].format(question=session.question)})

        # 3. Retry prompt if we have history
        if completed_trials:
            if allow_reasoning:
                messages.append({"role": "user", "content": PROMPTS["shared_retry_reasoning_prompt"].format(question=session.question)})
            else:
                messages.append({"role": "user", "content": PROMPTS["shared_retry_request"].format(question=session.question)})

        return messages