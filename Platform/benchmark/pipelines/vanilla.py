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
        
    def get_settings_snapshot(self):
        return {
            'llm_settings': {
                'llm_base_url': self.llm_settings.llm_base_url,
                'llm_model': self.llm_settings.llm_model,
                'max_retries': self.llm_settings.max_retries,
                'allow_reasoning': self.llm_settings.allow_reasoning, # Reverted to use settings
                'temperature': getattr(self.llm_settings, 'temperature', 0.0),
                'top_p': getattr(self.llm_settings, 'top_p', 1.0),
                'max_tokens': getattr(self.llm_settings, 'max_tokens', None)
            }
        }
        
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

        if self.llm_settings.allow_reasoning:
            prompt = PROMPTS["adhoc_reasoning"].format(question=question)
        else:
            prompt = PROMPTS["adhoc_answer"].format(question=question)
        
        answer, full_response = self.get_llm_response([{"role": "user", "content": prompt}])

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

    def get_settings_snapshot(self):
        return {
            'llm_settings': {
                'llm_base_url': self.llm_settings.llm_base_url,
                'llm_model': self.llm_settings.llm_model,
                'max_retries': self.llm_settings.max_retries,
                'allow_reasoning': self.llm_settings.allow_reasoning, # Reverted to use settings
                'temperature': getattr(self.llm_settings, 'temperature', 0.0),
                'top_p': getattr(self.llm_settings, 'top_p', 1.0),
                'max_tokens': getattr(self.llm_settings, 'max_tokens', None)
            }
        }

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

        # 1. Initial Prompt
        if allow_reasoning:
            initial_prompt = PROMPTS["multi_turn_reasoning_initial"].format(question=session.question)
        else:
            initial_prompt = PROMPTS["multi_turn_initial"].format(question=session.question)
        
        messages.append({"role": "user", "content": initial_prompt})

        # 2. History
        for i, past_trial in enumerate(completed_trials):
            if past_trial.answer:
                messages.append({"role": "assistant", "content": past_trial.answer})
            # Only add the generic feedback if this is NOT the last completed trial.
            # The last trial's feedback is handled by the follow-up prompt.
            if i < len(completed_trials) - 1:
                messages.append({"role": "user", "content": "Your previous answer was incorrect."})

        # 3. Follow-up instructions (only if we have history)
        if completed_trials:
            if allow_reasoning:
                messages.append({"role": "user", "content": PROMPTS["multi_turn_reasoning_followup"]})
            else:
                messages.append({"role": "user", "content": PROMPTS["multi_turn_followup"]})
            
        return messages
