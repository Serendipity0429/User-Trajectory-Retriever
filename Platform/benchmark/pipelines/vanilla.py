from datetime import datetime
from task_manager.utils import check_answer_rule, check_answer_llm
from ..prompts import PROMPTS
from ..models import MultiTurnSession, MultiTurnTrial
from .base import (
    BaseMultiTurnPipeline, 
    REDIS_PREFIX_VANILLA_MULTI_TURN
)

class VanillaLLMMultiTurnPipeline(BaseMultiTurnPipeline):
    def __init__(self, base_url, api_key, model, max_retries, pipeline_id=None, dataset_id=None):
        super().__init__(base_url, api_key, model, max_retries, pipeline_id, dataset_id)
        self.redis_prefix = REDIS_PREFIX_VANILLA_MULTI_TURN
        
    def __str__(self):
        return "Vanilla LLM Multi-Turn Pipeline"

    def create_session(self, settings, question_text, ground_truths, group):
        return MultiTurnSession.objects.create(
            question=question_text,
            ground_truths=ground_truths,
            run=group, 
            run_tag=self.pipeline_id,
            pipeline_type='vanilla_llm_multi_turn'
        )

    def create_trial(self, session, trial_number):
        return MultiTurnTrial.objects.create(
            session=session,
            trial_number=trial_number,
            status='processing'
        )

    def _construct_messages(self, session, trial, completed_trials):
        messages = []
        
        # session.run is the MultiTurnRun object
        settings_snapshot = session.run.settings_snapshot
        allow_reasoning = settings_snapshot.get('llm_settings', {}).get('allow_reasoning', False) # Reverted to use settings

        # 1. System and Initial Prompt
        sys_prompt = PROMPTS["vanilla_system_prompt"]
        if allow_reasoning:
            sys_prompt += PROMPTS["shared_reasoning_instruction"]
        
        initial_user_prompt = PROMPTS["shared_user_question"].format(question=session.question)
        
        messages.append({"role": "system", "content": sys_prompt})
        messages.append({"role": "user", "content": initial_user_prompt})

        # 2. History
        for i, past_trial in enumerate(completed_trials):
            if past_trial.full_response:
                messages.append({"role": "assistant", "content": past_trial.full_response})
            elif past_trial.answer:
                messages.append({"role": "assistant", "content": past_trial.answer})
            # Only add the generic feedback if this is NOT the last completed trial.
            # The last trial's feedback is handled by the follow-up prompt.
            if i < len(completed_trials) - 1:
                messages.append({"role": "user", "content": PROMPTS["vanilla_retry_request"]})

        # 3. Follow-up instructions (only if we have history)
        if completed_trials:
            if allow_reasoning:
                messages.append({"role": "user", "content": PROMPTS["vanilla_followup_reasoning_prompt"]})
            else:
                messages.append({"role": "user", "content": PROMPTS["vanilla_followup_prompt"]})
            
        return messages