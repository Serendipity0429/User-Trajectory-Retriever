from ..utils import PROMPTS
from .base import BaseMultiTurnPipeline, REDIS_PREFIX_VANILLA_MULTI_TURN

class VanillaLLMMultiTurnPipeline(BaseMultiTurnPipeline):
    def __init__(self, base_url, api_key, model, max_retries, pipeline_id=None, dataset_id=None, group_id=None):
        super().__init__(base_url, api_key, model, max_retries, pipeline_id, dataset_id, group_id)
        self.redis_prefix = REDIS_PREFIX_VANILLA_MULTI_TURN
        
    def __str__(self):
        return "Vanilla LLM Multi-Turn Pipeline"

    def get_pipeline_type_name(self):
        return 'vanilla_llm'

    def _construct_messages(self, session, trial, completed_trials):
        messages = []
        
        # session.run is the MultiTurnRun object
        allow_reasoning = session.run.settings.allow_reasoning if session.run and session.run.settings else False

        # 1. System and Initial Prompt
        sys_prompt = PROMPTS["vanilla_system_prompt"]
        if allow_reasoning:
            sys_prompt += PROMPTS["shared_reasoning_instruction_no_agent"]

        initial_user_prompt = PROMPTS["shared_user_question"].format(question=session.question)
        
        messages.append({"role": "system", "content": sys_prompt})
        messages.append({"role": "user", "content": initial_user_prompt})

        # 2. History - get assistant response from stored messages
        for i, past_trial in enumerate(completed_trials):
            past_log = past_trial.log or {}
            past_messages = past_log.get('messages', [])
            # Find the assistant's response from stored messages
            assistant_response = None
            for m in reversed(past_messages):
                if m.get('role') == 'assistant':
                    assistant_response = m.get('content')
                    break
            if assistant_response:
                messages.append({"role": "assistant", "content": assistant_response})
            elif past_trial.answer:
                messages.append({"role": "assistant", "content": past_trial.answer})
            # Only add the generic feedback if this is NOT the last completed trial.
            # The last trial's feedback is handled by the follow-up prompt.
            if i < len(completed_trials) - 1:
                messages.append({"role": "user", "content": PROMPTS["shared_retry_request"].format(question=session.question)})

        # 3. Follow-up instructions (only if we have history)
        if completed_trials:
            if allow_reasoning:
                messages.append({"role": "user", "content": PROMPTS["shared_retry_reasoning_prompt"].format(question=session.question)})
            else:
                messages.append({"role": "user", "content": PROMPTS["shared_retry_request"].format(question=session.question)})
            
        return messages