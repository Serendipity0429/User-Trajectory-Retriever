from datetime import datetime
from task_manager.utils import check_answer_rule, check_answer_llm
from ..prompts import PROMPTS
from ..models import AdhocRun, AdhocResult, MultiTurnSession, MultiTurnTrial
from .base import (
    BaseAdhocPipeline, BaseMultiTurnPipeline, 
    REDIS_PREFIX_VANILLA_ADHOC, REDIS_PREFIX_VANILLA_MULTI_TURN
)

class VanillaLLMAdhocPipeline(BaseAdhocPipeline):
    def __init__(self, base_url, api_key, model, pipeline_id=None, dataset_id=None):
        super().__init__(base_url, api_key, model, pipeline_id, dataset_id)
        self.redis_prefix = REDIS_PREFIX_VANILLA_ADHOC
        
    def __str__(self):
        return "Vanilla LLM Ad-hoc Pipeline"
        
    def create_run_object(self):
        run_name = f"{str(self)} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        snapshot = self.get_settings_snapshot()
        return AdhocRun.objects.create(
            name=run_name,
            settings_snapshot=snapshot,
            total_questions=0,
            correct_answers=0,
            run_type='vanilla'
        )

    def process_question(self, run, question, ground_truths):

        sys_prompt = PROMPTS["vanilla_system"]
        if self.llm_settings.allow_reasoning:
            sys_prompt += PROMPTS["reasoning_instruction"]
        
        user_prompt = PROMPTS["adhoc_user_question"].format(question=question)
        
        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt}
        ]
        answer, full_response = self.get_llm_response(messages)

        rule_result = check_answer_rule(question, ground_truths, answer)
        llm_result = check_answer_llm(question, ground_truths, answer, client=self.client, model=self.model)

        AdhocResult.objects.create(
            run=run,
            question=question,
            ground_truths=ground_truths,
            answer=answer,
            full_response=full_response,
            is_correct_rule=rule_result,
            is_correct_llm=llm_result
        )

        return {
            'question': question,
            'answer': answer,
            'full_response': full_response,
            'ground_truths': ground_truths,
            'rule_result': rule_result,
            'llm_result': llm_result
        }, llm_result

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
            pipeline_type='vanilla'
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
        sys_prompt = PROMPTS["vanilla_system"]
        if allow_reasoning:
            sys_prompt += PROMPTS["reasoning_instruction"]
        
        initial_user_prompt = PROMPTS["adhoc_user_question"].format(question=session.question)
        
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
                messages.append({"role": "user", "content": "Your previous answer was incorrect. Please re-examine the question and try again."})

        # 3. Follow-up instructions (only if we have history)
        if completed_trials:
            if allow_reasoning:
                messages.append({"role": "user", "content": PROMPTS["multi_turn_reasoning_followup"]})
            else:
                messages.append({"role": "user", "content": PROMPTS["multi_turn_followup"]})
            
        return messages
