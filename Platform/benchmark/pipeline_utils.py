import json
import os
import openai
import logging
from datetime import datetime
from task_manager.utils import check_answer_rule, check_answer_llm, redis_client
from .search_utils import get_search_engine
from .models import (
    LLMSettings, RagSettings, BenchmarkDataset, SearchSettings,
    VanillaLLMAdhocRun, VanillaLLMAdhocResult,
    RagAdhocRun, RagAdhocResult,
    MultiTurnSessionGroup, VanillaLLMMultiTurnSession, VanillaLLMMultiTurnTrial,
    RAGMultiTurnSession, RAGMultiTurnTrial
)
from .utils import print_debug


HARD_QUESTIONS_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'hard_questions_refined.jsonl')

PROMPTS = {
    "adhoc_answer": """Your task is to answer the following question. Follow these rules strictly:
1.  Your answer must be an exact match to the correct answer.
2.  Do not include any punctuation.
3.  Do not include any extra words or sentences.

For example:
Question: What is the capital of France?
Correct Answer: Paris

Incorrect Answers:
- "The capital of France is Paris." (contains extra words)
- "Paris is the capital of France." (contains extra words)
- "Paris." (contains a period)

Now, answer the following question:
Question: {question}
Answer:""",
    "multi_turn_initial": """Your task is to answer the following question. Follow these rules strictly:
1.  Your answer must be an exact match to the correct answer.
2.  Do not include any punctuation.
3.  Do not include any extra words or sentences.
Question: {question}
Answer:""",
    "multi_turn_followup": """Your task is to answer the question again. Follow these rules strictly:
1.  Your answer must be an exact match to the correct answer.
2.  Do not include any punctuation.
3.  Do not include any extra words or sentences.
Answer:""",
    "rag_system_context": "Context from web search (Query: {query}):\n{results}\n\n",
    "rag_reformulation": "Based on the history, provide a better search query to find the correct answer. Output ONLY the query."
}

class BasePipeline:
    def __init__(self, base_url, api_key, model, pipeline_id=None, dataset_id=None):
        self.client = openai.OpenAI(base_url=base_url, api_key=api_key)
        self.model = model
        self.pipeline_id = pipeline_id
        self.dataset_id = dataset_id
        self.redis_prefix = "pipeline_active"

    def check_active(self):
        if not self.pipeline_id:
            return True
        return redis_client.get(f"{self.redis_prefix}:{self.pipeline_id}")

    def stop_token(self):
        if self.pipeline_id:
            redis_client.delete(f"{self.redis_prefix}:{self.pipeline_id}")

    def load_questions(self):
        file_path = None
        if self.dataset_id:
            try:
                dataset = BenchmarkDataset.objects.get(pk=self.dataset_id)
                if dataset.file and os.path.exists(dataset.file.path):
                    file_path = dataset.file.path
            except BenchmarkDataset.DoesNotExist:
                pass
                
        if file_path is None:
            file_path = HARD_QUESTIONS_PATH
            
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                for line in f:
                    try:
                        data = json.loads(line)
                        if 'answer' in data and 'ground_truths' not in data:
                            data['ground_truths'] = data['answer']
                        yield data
                    except json.JSONDecodeError:
                        continue
    
    def run(self):
        yield json.dumps({'is_meta': True, 'type': 'info', 'message': 'Pipeline started'}) + "\n"
        pass


class BaseAdhocPipeline(BasePipeline):
    """
    Base class for Ad-hoc pipelines (Vanilla and RAG) to reduce duplication.
    """
    def create_run_object(self):
        raise NotImplementedError

    def process_question(self, run_object, question, ground_truths):
        raise NotImplementedError

    def run(self):
        run_object = self.create_run_object()
        yield json.dumps({'is_meta': True, 'type': 'run_created', 'run_id': run_object.id, 'name': run_object.name}) + "\n"
        
        total_count = 0
        correct_count = 0

        for data in self.load_questions():
            if not self.check_active():
                break

            question = data['question']
            ground_truths = data.get('ground_truths', [])

            try:
                result_data, is_correct = self.process_question(run_object, question, ground_truths)
                
                if is_correct:
                    correct_count += 1
                total_count += 1

                yield json.dumps(result_data) + "\n"

            except Exception as e:
                yield json.dumps({'error': str(e), 'question': question}) + "\n"

        run_object.total_questions = total_count
        run_object.correct_answers = correct_count
        run_object.accuracy = (correct_count / total_count * 100) if total_count > 0 else 0
        run_object.save()
        self.stop_token()


class VanillaLLMAdhocPipeline(BaseAdhocPipeline):
    def __init__(self, base_url, api_key, model, pipeline_id=None, dataset_id=None):
        super().__init__(base_url, api_key, model, pipeline_id, dataset_id)
        self.redis_prefix = "vanilla_llm_adhoc_pipeline_active"

    def create_run_object(self):
        settings = LLMSettings.load()
        run_name = f"Vanilla LLM Ad-hoc Run {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        snapshot = {
            'llm_settings': {
                'llm_base_url': settings.llm_base_url,
                'llm_model': settings.llm_model,
                'max_retries': settings.max_retries
            }
        }
        return VanillaLLMAdhocRun.objects.create(
            name=run_name,
            settings_snapshot=snapshot,
            total_questions=0,
            correct_answers=0
        )

    def process_question(self, run, question, ground_truths):
        prompt = PROMPTS["adhoc_answer"].format(question=question)
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        answer = response.choices[0].message.content
        
        rule_result = check_answer_rule(question, ground_truths, answer)
        llm_result = check_answer_llm(question, ground_truths, answer, client=self.client, model=self.model)

        VanillaLLMAdhocResult.objects.create(
            run=run,
            question=question,
            ground_truths=ground_truths,
            answer=answer,
            is_correct_rule=rule_result,
            is_correct_llm=llm_result
        )

        return {
            'question': question,
            'answer': answer,
            'ground_truths': ground_truths,
            'rule_result': rule_result,
            'llm_result': llm_result
        }, llm_result


class RagAdhocPipeline(BaseAdhocPipeline):
    def __init__(self, base_url, api_key, model, rag_prompt_template, pipeline_id=None, dataset_id=None):
        super().__init__(base_url, api_key, model, pipeline_id, dataset_id)
        self.prompt_template = rag_prompt_template
        self.search_engine = get_search_engine()
        self.redis_prefix = "rag_adhoc_pipeline_active"

    def create_run_object(self):
        llm_settings = LLMSettings.load()
        rag_settings = RagSettings.load()
        search_settings = SearchSettings.load()
        
        run_name = f"RAG Ad-hoc Run {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        snapshot = {
            'llm_settings': {
                'llm_base_url': llm_settings.llm_base_url,
                'llm_model': llm_settings.llm_model,
                'max_retries': llm_settings.max_retries
            },
            'rag_settings': {
                'prompt_template': rag_settings.prompt_template
            },
            'search_settings': {
                'search_provider': search_settings.search_provider,
                'serper_fetch_full_content': search_settings.serper_fetch_full_content
            }
        }
        return RagAdhocRun.objects.create(
            name=run_name,
            settings_snapshot=snapshot,
            total_questions=0,
            correct_answers=0
        )

    def process_question(self, run, question, ground_truths):
        search_results = self.search_engine.search(question)
        formatted_results = self.search_engine.format_results(search_results)
        
        prompt = self.prompt_template.replace('{question}', question).replace('{search_results}', formatted_results)
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        answer = response.choices[0].message.content
        
        rule_result = check_answer_rule(question, ground_truths, answer)
        llm_result = check_answer_llm(question, ground_truths, answer, client=self.client, model=self.model)

        RagAdhocResult.objects.create(
            run=run,
            question=question,
            ground_truths=ground_truths,
            answer=answer,
            is_correct_rule=rule_result,
            is_correct_llm=llm_result,
            num_docs_used=len(search_results),
            search_results=search_results
        )

        return {
            'question': question,
            'answer': answer,
            'ground_truths': ground_truths,
            'rule_result': rule_result,
            'llm_result': llm_result,
            'num_docs_used': len(search_results),
            'search_results': search_results
        }, llm_result


class BaseMultiTurnPipeline(BasePipeline):
    def __init__(self, base_url, api_key, model, max_retries, pipeline_id=None, dataset_id=None):
        super().__init__(base_url, api_key, model, pipeline_id, dataset_id)
        self.max_retries = max_retries
        self.redis_prefix = "multi_turn_pipeline_active"

    def create_session(self, settings, question_text, ground_truths, group):
        raise NotImplementedError("Subclasses must implement create_session")

    def create_trial(self, session, trial_number):
        raise NotImplementedError("Subclasses must implement create_trial")
    
    def _construct_messages(self, session, trial):
        raise NotImplementedError("Subclasses must implement _construct_messages")

    def run(self):
        group_name = f"Pipeline Run ({self.__class__.__name__}) - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}" 
        
        # Load settings for snapshot
        llm_settings = LLMSettings.load()
        rag_settings = RagSettings.load()
        search_settings = SearchSettings.load()

        snapshot = {
            'llm_settings': {
                'llm_base_url': llm_settings.llm_base_url,
                'llm_model': llm_settings.llm_model,
                'max_retries': llm_settings.max_retries
            },
            'rag_settings': {
                'prompt_template': rag_settings.prompt_template
            },
            'search_settings': {
                'search_provider': search_settings.search_provider,
                'serper_fetch_full_content': search_settings.serper_fetch_full_content
            }
        }

        group = MultiTurnSessionGroup.objects.create(name=group_name, settings_snapshot=snapshot)
        settings = llm_settings # Pass LLM settings to create_session if needed

        for data in self.load_questions():
            if not self.check_active():
                break

            question_text = data['question']
            ground_truths = data.get('ground_truths', [])
            
            try:
                session = self.create_session(settings, question_text, ground_truths, group)

                yield json.dumps({
                    'is_meta': True,
                    'type': 'session_created',
                    'session_id': session.id,
                    'question': question_text,
                    'group_id': group.id,
                    'group_name': group_name
                }) + "\n"

                is_session_completed = False
                trial_number = 1
                final_is_correct = False
                final_answer = ""
                
                while trial_number <= self.max_retries and not is_session_completed:
                    if not self.check_active():
                        break

                    trial = self.create_trial(session, trial_number)
                    
                    yield json.dumps({
                        'is_meta': True,
                        'type': 'trial_started',
                        'session_id': session.id,
                        'trial_number': trial_number,
                        'group_id': group.id
                    }) + "\n"

                    messages = self._construct_messages(session, trial)
                    
                    try:
                        response = self.client.chat.completions.create(
                            model=self.model,
                            messages=messages,
                            temperature=0,
                        )
                        answer = response.choices[0].message.content
                    except Exception as e:
                        trial.status = 'error'
                        trial.save()
                        raise e

                    is_correct = check_answer_llm(session.question, session.ground_truths, answer, client=self.client, model=self.model)

                    trial.answer = answer
                    trial.is_correct = is_correct
                    trial.feedback = "Correct" if is_correct else "Incorrect"
                    trial.status = 'completed'
                    trial.save()

                    yield json.dumps({
                        'is_meta': True,
                        'type': 'trial_completed',
                        'session_id': session.id,
                        'trial_number': trial_number,
                        'is_correct': is_correct,
                        'answer': answer,
                        'group_id': group.id
                    }) + "\n"

                    final_answer = answer
                    final_is_correct = is_correct

                    if is_correct:
                        is_session_completed = True
                    else:
                        trial_number += 1
                
                session.is_completed = True
                session.save()

                yield json.dumps({
                    'question': question_text,
                    'correct': final_is_correct,
                    'trials': trial_number if final_is_correct else (trial_number - 1),
                    'session_id': session.id,
                    'final_answer': final_answer,
                    'ground_truths': ground_truths,
                    'max_retries': self.max_retries,
                    'group_name': group_name,
                    'group_id': group.id
                }) + "\n"

            except Exception as e:
                yield json.dumps({'error': str(e), 'question': question_text}) + "\n"
        
        self.stop_token()

    def run_single_turn(self, session, trial):
        """
        Executes a single turn for a given session and trial object.
        """
        messages = self._construct_messages(session, trial)
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages
            )
            answer = response.choices[0].message.content
        except Exception as e:
            trial.status = 'error'
            trial.save()
            raise e

        # Logic for checking answer
        is_correct = check_answer_llm(session.question, session.ground_truths, answer, client=self.client, model=self.model)

        trial.answer = answer
        trial.is_correct = is_correct
        trial.feedback = "Correct" if is_correct else "Incorrect"
        trial.status = 'completed'
        trial.save()
        
        return answer, is_correct, getattr(trial, 'search_results', [])


class VanillaLLMMultiTurnPipeline(BaseMultiTurnPipeline):
    def __init__(self, base_url, api_key, model, max_retries, pipeline_id=None, dataset_id=None):
        super().__init__(base_url, api_key, model, max_retries, pipeline_id, dataset_id)
        self.redis_prefix = "vanilla_llm_multi_turn_pipeline_active"

    def create_session(self, settings, question_text, ground_truths, group):
        return VanillaLLMMultiTurnSession.objects.create(
            question=question_text,
            ground_truths=ground_truths,
            group=group,
            run_tag=self.pipeline_id
        )

    def create_trial(self, session, trial_number):
        return VanillaLLMMultiTurnTrial.objects.create(
            session=session,
            trial_number=trial_number,
            status='processing'
        )

    def _construct_messages(self, session, trial):
        trial_number = trial.trial_number
        messages = []
        
        if trial_number == 1:
            answer_prompt = PROMPTS["multi_turn_initial"].format(question=session.question)
            messages.append({"role": "user", "content": answer_prompt})
        else:
            messages.append({"role": "user", "content": f"Question: {session.question}"})
            prev_trials = session.trials.filter(trial_number__lt=trial_number).order_by('trial_number')
            for prev_trial in prev_trials:
                if prev_trial.answer:
                    messages.append({"role": "assistant", "content": prev_trial.answer})
                if prev_trial.is_correct == False:
                    messages.append({"role": "user", "content": "Your previous answer was incorrect."})
            
            messages.append({"role": "user", "content": PROMPTS["multi_turn_followup"]})
            
        return messages


class RagMultiTurnPipeline(BaseMultiTurnPipeline):
    def __init__(self, base_url, api_key, model, max_retries, reformulation_strategy='no_reform', pipeline_id=None, dataset_id=None):
        super().__init__(base_url, api_key, model, max_retries, pipeline_id, dataset_id)
        self.search_engine = get_search_engine()
        self.reformulation_strategy = reformulation_strategy
        self.redis_prefix = f"rag_multi_turn_{self.reformulation_strategy}_pipeline_active"

    def create_session(self, settings, question_text, ground_truths, group):
        return RAGMultiTurnSession.objects.create(
            question=question_text,
            ground_truths=ground_truths,
            group=group,
            reformulation_strategy=self.reformulation_strategy,
            run_tag=self.pipeline_id
        )

    def create_trial(self, session, trial_number):
        return RAGMultiTurnTrial.objects.create(
            session=session,
            trial_number=trial_number,
            status='processing'
        )

    def _construct_messages(self, session, trial):
        trial_number = trial.trial_number
        messages = []
        current_search_query = session.question
        
        if self.reformulation_strategy == 'reform' and trial_number > 1:
            reform_messages = [{"role": "system", "content": "You are a helpful assistant that reformulates search queries based on conversation history."}]
            reform_messages.append({"role": "user", "content": f"Original Question: {session.question}"})
            
            prev_trials = session.trials.filter(trial_number__lt=trial_number).order_by('trial_number')
            for prev_trial in prev_trials:
                if prev_trial.answer:
                    reform_messages.append({"role": "assistant", "content": f"Previous Answer: {prev_trial.answer}"})
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
                pass

        search_results = self.search_engine.search(current_search_query)
        formatted_results = self.search_engine.format_results(search_results)
        
        # Save search info to the passed trial object directly
        trial.search_query = current_search_query
        trial.search_results = search_results
        trial.save()

        system_prompt = PROMPTS["rag_system_context"].format(query=current_search_query, results=formatted_results)
        messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": f"Question: {session.question}"})
        
        prev_trials = session.trials.filter(trial_number__lt=trial_number).order_by('trial_number')
        for prev_trial in prev_trials:
            if prev_trial.answer:
                messages.append({"role": "assistant", "content": prev_trial.answer})
            if prev_trial.is_correct == False:
                messages.append({"role": "user", "content": "Your previous answer was incorrect."})

        messages.append({"role": "user", "content": "Answer the question based on the context. Return ONLY the exact answer."})
        
        return messages