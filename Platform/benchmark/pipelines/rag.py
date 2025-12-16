from datetime import datetime
from task_manager.utils import check_answer_rule, check_answer_llm, redis_client
from ..search_utils import get_search_engine
from ..prompts import PROMPTS
from ..models import (
    SearchSettings,
    AdhocRun, AdhocResult,
    MultiTurnSession, MultiTurnTrial
)
from ..utils import print_debug
from .base import (
    BaseAdhocPipeline, BaseMultiTurnPipeline, 
    REDIS_PREFIX_RAG_ADHOC
)
from difflib import SequenceMatcher

class RagAdhocPipeline(BaseAdhocPipeline):
    def __init__(self, base_url, api_key, model, pipeline_id=None, dataset_id=None):
        super().__init__(base_url, api_key, model, pipeline_id, dataset_id)
        self.search_engine = get_search_engine()
        self.redis_prefix = REDIS_PREFIX_RAG_ADHOC
        self.search_settings = SearchSettings.get_effective_settings()
        
    def __str__(self):
        return "RAG Ad-hoc Pipeline"

    def get_settings_snapshot(self):
        return {
            'llm_settings': {
                'llm_base_url': self.llm_settings.llm_base_url,
                'llm_model': self.llm_settings.llm_model,
                'max_retries': self.llm_settings.max_retries,
                'allow_reasoning': self.llm_settings.allow_reasoning,
                'temperature': getattr(self.llm_settings, 'temperature', 0.0),
                'top_p': getattr(self.llm_settings, 'top_p', 1.0),
                'max_tokens': getattr(self.llm_settings, 'max_tokens', None)
            },
            'search_settings': {
                'search_provider': self.search_settings.search_provider,
                'search_limit': self.search_settings.search_limit,
                'serper_fetch_full_content': self.search_settings.fetch_full_content
            }
        }

    def create_run_object(self):
        run_name = f"RAG Ad-hoc Run {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        snapshot = self.get_settings_snapshot()
        return AdhocRun.objects.create(
            name=run_name,
            settings_snapshot=snapshot,
            total_questions=0,
            correct_answers=0,
            run_type='rag'
        )

    def process_question(self, run, question, ground_truths):
        # 1. Generate Search Query (Baseline 2: Active RAG)
        query_prompt = PROMPTS["rag_query_generation"].format(question=question)
        search_query, _ = self.get_llm_response([{"role": "user", "content": query_prompt}], temperature=0.0)
        search_query = search_query.strip()
        
        # 2. Perform Search
        search_results = self.search_engine.search(search_query)
        formatted_results = self.search_engine.format_results(search_results)
        
        if self.llm_settings.allow_reasoning:
            prompt = PROMPTS["rag_adhoc_reasoning"].format(question=question, search_results=formatted_results)
        else:
            prompt = PROMPTS["rag_prompt_template"].replace('{question}', question).replace('{search_results}', formatted_results)
        
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
            is_correct_llm=llm_result,
            num_docs_used=len(search_results),
            search_results=search_results
        )

        return {
            'question': question,
            'answer': answer,
            'full_response': full_response,
            'ground_truths': ground_truths,
            'rule_result': rule_result,
            'llm_result': llm_result,
            'num_docs_used': len(search_results),
            'search_results': search_results
        }, llm_result

class RagMultiTurnPipeline(BaseMultiTurnPipeline):
    def __init__(self, base_url, api_key, model, max_retries, pipeline_id=None, dataset_id=None):
        super().__init__(base_url, api_key, model, max_retries, pipeline_id, dataset_id)
        self.search_engine = get_search_engine()
        self.redis_prefix = "rag_multi_turn_pipeline_active"
    
    def __str__(self):
        return "RAG Multi-Turn Pipeline"

    def get_settings_snapshot(self):
        search_settings = SearchSettings.get_effective_settings()
        return {
            'llm_settings': {
                'llm_base_url': self.llm_settings.llm_base_url,
                'llm_model': self.llm_settings.llm_model,
                'max_retries': self.llm_settings.max_retries,
                'allow_reasoning': self.llm_settings.allow_reasoning,
                'temperature': getattr(self.llm_settings, 'temperature', 0.0),
                'top_p': getattr(self.llm_settings, 'top_p', 1.0),
                'max_tokens': getattr(self.llm_settings, 'max_tokens', None)
            },
            'search_settings': {
                'search_provider': search_settings.search_provider,
                'search_limit': search_settings.search_limit,
                'serper_fetch_full_content': search_settings.fetch_full_content
            }
        }

    def create_session(self, settings, question_text, ground_truths, group):
        return MultiTurnSession.objects.create(
            question=question_text,
            ground_truths=ground_truths,
            run=group,
            run_tag=self.pipeline_id,
            pipeline_type='rag'
        )

    def create_trial(self, session, trial_number):
        return MultiTurnTrial.objects.create(
            session=session,
            trial_number=trial_number,
            status='processing'
        )

    def _construct_messages(self, session, trial, completed_trials):
        messages = []
        current_search_query = session.question
        search_results = None
        
        settings_snapshot = session.run.settings_snapshot
        allow_reasoning = settings_snapshot.get('llm_settings', {}).get('allow_reasoning', False)

        # Check if trial already has search results (e.g. from history reconstruction or manual run)
        if search_results is None and trial.search_results:
            search_results = trial.search_results
            current_search_query = trial.search_query

        if search_results is None:
            # Active RAG: Always generate/reformulate query
            if trial.trial_number == 1:
                # Initial Turn Query Generation
                query_prompt = PROMPTS["rag_query_generation"].format(question=session.question)
                try:
                    search_query, _ = self.get_llm_response([{"role": "user", "content": query_prompt}], temperature=0.0)
                    current_search_query = search_query.strip()
                except Exception as e:
                    print_debug(f"Initial query generation failed: {e}")
                    current_search_query = session.question # Fallback
            else:
                # Reformulation for subsequent turns
                reform_messages = [
                    {"role": "system", "content": "You are a helpful assistant that reformulates search queries based on conversation history."},
                    {"role": "user", "content": f"Original Question: {session.question}"}
                ]
                
                # Reconstruct history from previous_messages and last_trial
                for past_trial in completed_trials:
                    if past_trial.answer:
                            reform_messages.append({"role": "assistant", "content": f"Previous Answer: {past_trial.answer}"})
                    reform_messages.append({"role": "user", "content": "The previous answer was incorrect."})

                reform_messages.append({"role": "user", "content": PROMPTS["rag_reformulation"]})
                
                try:
                    reform_response = self.client.chat.completions.create(
                        model=self.model,
                        messages=reform_messages,
                        temperature=0,
                    )
                    current_search_query = reform_response.choices[0].message.content.strip()
                except Exception as e:
                    print_debug(f"Reformulation failed: {e}")
                    # current_search_query remains session.question (fallback)

            search_results = self.search_engine.search(current_search_query)

        formatted_results = self.search_engine.format_results(search_results)
        
        # Save search info to the passed trial object directly
        trial.search_query = current_search_query
        trial.search_results = search_results
        trial.save()

        # New logic: Static system instruction + Dynamic context in User prompt
        messages.append({"role": "system", "content": PROMPTS["rag_system_instruction"]})

        user_content = PROMPTS["rag_context_initial"].format(
            query=current_search_query, 
            results=formatted_results, 
            question=session.question
        )
        messages.append({"role": "user", "content": user_content})

        for i, past_trial in enumerate(completed_trials):
            if past_trial.answer:
                messages.append({"role": "assistant", "content": past_trial.answer})
            if i < len(completed_trials) - 1:
                messages.append({"role": "user", "content": "Your previous answer was incorrect."})

        # 3. Follow-up instructions
        if completed_trials:
            if allow_reasoning:
                messages.append({"role": "user", "content": PROMPTS["rag_adhoc_reasoning"].replace('{question}', "Your previous answer was incorrect. Please try again.").replace('{search_results}', formatted_results)})
            else:
                 # Re-use the system prompt context but give a specific follow-up instruction
                messages.append({"role": "user", "content": PROMPTS["multi_turn_followup"]})
        
        return messages
