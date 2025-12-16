import json
import os
import openai
import logging
import asyncio
import time
from datetime import datetime
from task_manager.utils import check_answer_rule, check_answer_llm, redis_client
from .search_utils import get_search_engine
from .models import (
    LLMSettings, RagSettings, BenchmarkDataset, SearchSettings,
    AdhocRun, AdhocResult,
    MultiTurnRun, MultiTurnSession, MultiTurnTrial
)
from .utils import print_debug, extract_final_answer, count_questions_in_file
from .prompts import PROMPTS
from .agent_utils import VanillaAgentFactory
from .agent_utils import BrowserAgentFactory
from agentscope.message import Msg
from asgiref.sync import sync_to_async

REDIS_PREFIX_ACTIVE = "pipeline_active"
REDIS_PREFIX_VANILLA_ADHOC = "vanilla_llm_adhoc_pipeline_active"
REDIS_PREFIX_RAG_ADHOC = "rag_adhoc_pipeline_active"
REDIS_PREFIX_MULTI_TURN = "multi_turn_pipeline_active"
REDIS_PREFIX_VANILLA_MULTI_TURN = "vanilla_llm_multi_turn_pipeline_active"
REDIS_PREFIX_BROWSER_AGENT = "browser_agent_pipeline_active"

HARD_QUESTIONS_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'hard_questions_refined.jsonl')

def serialize_events(generator):
    """
    Helper function to serialize events from the pipeline generator.
    """
    for event in generator:
        yield json.dumps(event) + "\n"

async def serialize_events_async(generator):
    """
    Helper function to serialize events from an async pipeline generator.
    """
    async for event in generator:
        yield json.dumps(event) + "\n"

class BasePipeline:
    def __init__(self, base_url, api_key, model, pipeline_id=None, dataset_id=None):
        self.client = openai.OpenAI(base_url=base_url, api_key=api_key)
        self.model = model
        self.pipeline_id = pipeline_id
        self.dataset_id = dataset_id
        self.redis_prefix = REDIS_PREFIX_ACTIVE
        self.llm_settings = LLMSettings.load()

    def check_active(self):
        if not self.pipeline_id:
            return True
        return redis_client.get(f"{self.redis_prefix}:{self.pipeline_id}")

    def stop_token(self):
        if self.pipeline_id:
            redis_client.delete(f"{self.redis_prefix}:{self.pipeline_id}")

    def get_questions_file_path(self):
        file_path = None
        if self.dataset_id:
            try:
                dataset = BenchmarkDataset.objects.get(pk=self.dataset_id)
                if dataset.file and os.path.exists(dataset.file.path):
                    file_path = dataset.file.path
                else: # Dataset found, but file missing or invalid
                    raise ValueError(f"Dataset {self.dataset_id} has no valid file path associated with it.")
            except BenchmarkDataset.DoesNotExist:
                raise ValueError(f"Dataset with ID {self.dataset_id} not found.")
        else: # No dataset_id provided, use default
            file_path = HARD_QUESTIONS_PATH
            
        if not file_path or not os.path.exists(file_path):
            raise FileNotFoundError(f"Questions file not found at {file_path}")

        return file_path

    def load_questions(self):
        file_path = self.get_questions_file_path()
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

    def get_total_questions(self):
        try:
            file_path = self.get_questions_file_path()
            if self.dataset_id:
                try:
                    dataset = BenchmarkDataset.objects.get(pk=self.dataset_id)
                    if dataset.question_count > 0:
                        return dataset.question_count
                except BenchmarkDataset.DoesNotExist:
                    pass
            return count_questions_in_file(file_path)
        except Exception:
            return 0

    def get_llm_response(self, messages, temperature=None):
        """
        Sends messages to LLM and parses the response based on current settings.
        Returns: (parsed_answer, full_response)
        """
        if temperature is None:
            temperature = getattr(self.llm_settings, 'temperature', 0.0)
            
        top_p = getattr(self.llm_settings, 'top_p', 1.0)
        max_tokens = getattr(self.llm_settings, 'max_tokens', None)

        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p
        }
        if max_tokens:
            kwargs['max_tokens'] = max_tokens

        max_api_retries = 3
        last_exception = None

        for attempt in range(max_api_retries):
            try:
                response = self.client.chat.completions.create(**kwargs)
                full_response = response.choices[0].message.content
                
                if self.llm_settings.allow_reasoning:
                    answer = extract_final_answer(full_response)
                else:
                    answer = full_response
                    
                return answer, full_response

            except Exception as e:
                last_exception = e
                print_debug(f"LLM API call failed (attempt {attempt + 1}/{max_api_retries}): {e}")
                if attempt < max_api_retries - 1:
                    sleep_time = (2 ** attempt) * 1  # 1s, 2s, 4s...
                    time.sleep(sleep_time)
                else:
                    raise last_exception
    
    async def run(self):
        run_object = await sync_to_async(self.create_run_object)()
        yield {'is_meta': True, 'type': 'run_created', 'run_id': run_object.id, 'name': run_object.name}
        
        total_questions = 0
        questions_iterator = None
        
        try:
            total_questions = await sync_to_async(self.get_total_questions)()
            questions_iterator = await sync_to_async(self.load_questions)()
        except Exception as e:
            yield {'error': str(e)}
            await sync_to_async(self.stop_token)()
            return

        yield {'is_meta': True, 'type': 'total_count', 'count': total_questions}

        # Iterating over sync generator in async method?
        # load_questions returns a generator.
        # We can iterate it synchronously if it doesn't do I/O during iteration (it reads file line by line).
        # Actually load_questions reads file.
        # Ideally we convert it to list or iterate in thread.
        # For now, let's assume we can iterate it (blocking slightly).
        
        # But wait, BaseMultiTurnPipeline.run logic is different.
        # It calls _process_single_session.
        pass
        
    def get_settings_snapshot(self):
        raise NotImplementedError("Subclasses must implement get_settings_snapshot")


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
        yield {'is_meta': True, 'type': 'run_created', 'run_id': run_object.id, 'name': run_object.name}
        
        total_questions = 0
        questions_iterator = None
        
        try:
            total_questions = self.get_total_questions()
            questions_iterator = self.load_questions() # This now uses the file_path logic from get_questions_file_path
        except (ValueError, FileNotFoundError, BenchmarkDataset.DoesNotExist) as e:
            yield {'error': str(e)}
            self.stop_token() # Ensure stop token is cleared on error
            return # Terminate pipeline on error

        yield {'is_meta': True, 'type': 'total_count', 'count': total_questions}

        total_count = 0
        correct_count = 0

        for data in questions_iterator:
            if not self.check_active():
                break

            question = data['question']
            ground_truths = data.get('ground_truths', [])

            # Notify frontend that we are starting this question
            yield {
                'is_meta': True, 
                'type': 'processing_start', 
                'question': {
                    'question': question
                    # We can send more data if needed for display
                }
            }

            try:
                result_data, is_correct = self.process_question(run_object, question, ground_truths)
                
                if is_correct:
                    correct_count += 1
                total_count += 1

                yield result_data

            except Exception as e:
                yield {'error': str(e), 'question': question}

        run_object.total_questions = total_count
        run_object.correct_answers = correct_count
        run_object.accuracy = (correct_count / total_count * 100) if total_count > 0 else 0
        run_object.save()
        self.stop_token()


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
                'allow_reasoning': self.llm_settings.allow_reasoning,
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


class RagAdhocPipeline(BaseAdhocPipeline):
    def __init__(self, base_url, api_key, model, rag_prompt_template, pipeline_id=None, dataset_id=None):
        super().__init__(base_url, api_key, model, pipeline_id, dataset_id)
        self.prompt_template = rag_prompt_template
        self.search_engine = get_search_engine()
        self.redis_prefix = REDIS_PREFIX_RAG_ADHOC
        self.rag_settings = RagSettings.load()
        self.search_settings = SearchSettings.load()
        
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
            'rag_settings': {
                'prompt_template': self.rag_settings.prompt_template
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
        search_results = self.search_engine.search(question)
        formatted_results = self.search_engine.format_results(search_results)
        
        if self.llm_settings.allow_reasoning:
            prompt = PROMPTS["rag_adhoc_reasoning"].format(question=question, search_results=formatted_results)
        else:
            prompt = self.prompt_template.replace('{question}', question).replace('{search_results}', formatted_results)
        
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


class BaseMultiTurnPipeline(BasePipeline):
    def __init__(self, base_url, api_key, model, max_retries, pipeline_id=None, dataset_id=None):
        super().__init__(base_url, api_key, model, pipeline_id, dataset_id)
        self.max_retries = max_retries
        self.redis_prefix = REDIS_PREFIX_MULTI_TURN

    def create_session(self, settings, question_text, ground_truths, group):
        raise NotImplementedError("Subclasses must implement create_session")

    def create_trial(self, session, trial_number):
        raise NotImplementedError("Subclasses must implement create_trial")
    
    def _construct_messages(self, session, trial, completed_trials):
        raise NotImplementedError("Subclasses must implement _construct_messages")

    def _process_single_session(self, group, question_text, ground_truths):
        """
        Process a single question session, including retries.
        Yields events for each step.
        """
        try:
            session = self.create_session(self.llm_settings, question_text, ground_truths, group)

            yield {
                'is_meta': True,
                'type': 'session_created',
                'session_id': session.id,
                'question': question_text,
                'group_id': group.id,
                'group_name': group.name
            }

            is_session_completed = False
            trial_number = 1
            final_is_correct = False
            final_answer = ""
            completed_trials = []
            
            while trial_number <= self.max_retries and not is_session_completed:
                if not self.check_active():
                    break

                trial = self.create_trial(session, trial_number)
                
                yield {
                    'is_meta': True,
                    'type': 'trial_started',
                    'session_id': session.id,
                    'trial_number': trial_number,
                    'group_id': group.id
                }

                messages = self._construct_messages(session, trial, completed_trials)
                
                try:
                    parsed_answer, full_response = self.get_llm_response(messages)
                except Exception as e:
                    trial.status = 'error'
                    trial.save()
                    raise e
                
                try:
                    is_correct = check_answer_llm(session.question, session.ground_truths, parsed_answer, client=self.client, model=self.model)
                except Exception as e:
                    print_debug(f"Judge failed: {e}")
                    is_correct = None


                trial.answer = parsed_answer
                trial.full_response = full_response
                trial.is_correct = is_correct
                trial.feedback = "Correct" if is_correct else "Incorrect"
                trial.status = 'completed'
                trial.save()
                
                completed_trials.append(trial)

                yield {
                    'is_meta': True,
                    'type': 'trial_completed',
                    'session_id': session.id,
                    'trial_number': trial_number,
                    'is_correct': is_correct,
                    'answer': parsed_answer, # Send parsed answer for display/check validity
                    'full_response': full_response,
                    'group_id': group.id
                }

                final_answer = parsed_answer
                final_is_correct = is_correct

                if is_correct:
                    is_session_completed = True
                else:
                    trial_number += 1
            
            session.is_completed = True
            session.save()

            yield {
                'question': question_text,
                'correct': final_is_correct,
                'trials': trial_number if final_is_correct else (trial_number - 1),
                'session_id': session.id,
                'final_answer': final_answer,
                'ground_truths': ground_truths,
                'max_retries': self.max_retries,
                'group_name': group.name,
                'group_id': group.id
            }

        except Exception as e:
            yield {'error': str(e), 'question': question_text}

    def run(self):
        group_name = f"{str(self)}- {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}" 
        
        snapshot = self.get_settings_snapshot()

        group = MultiTurnRun.objects.create(name=group_name, settings_snapshot=snapshot)
        
        total_questions = 0
        questions_iterator = None
        
        try:
            total_questions = self.get_total_questions()
            questions_iterator = self.load_questions()
        except (ValueError, FileNotFoundError, BenchmarkDataset.DoesNotExist) as e:
            yield {'error': str(e)}
            self.stop_token()
            return

        yield {'is_meta': True, 'type': 'total_count', 'count': total_questions}

        for data in questions_iterator:
            if not self.check_active():
                break

            question_text = data['question']
            ground_truths = data.get('ground_truths', [])
            
            yield from self._process_single_session(group, question_text, ground_truths)
        
        self.stop_token()

    def run_single_turn(self, session, trial):
        """
        Executes a single turn for a given session and trial object.
        """
        completed_trials = list(session.trials.filter(
            trial_number__lt=trial.trial_number, 
            status='completed'
        ).order_by('trial_number'))
        
        messages = self._construct_messages(session, trial, completed_trials)
        
        try:
            answer, full_response = self.get_llm_response(messages)
        except Exception as e:
            trial.status = 'error'
            trial.save()
            raise e

        # Logic for checking answer
            
        is_correct = check_answer_llm(session.question, session.ground_truths, answer, client=self.client, model=self.model)

        trial.answer = answer
        trial.full_response = full_response # Save full response too
        trial.is_correct = is_correct
        trial.feedback = "Correct" if is_correct else "Incorrect"
        trial.status = 'completed'
        trial.save()
        
        return answer, is_correct, getattr(trial, 'search_results', [])


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
                'allow_reasoning': self.llm_settings.allow_reasoning,
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
        allow_reasoning = settings_snapshot.get('llm_settings', {}).get('allow_reasoning', False)

        # 1. Initial Prompt
        if allow_reasoning:
            initial_prompt = PROMPTS["multi_turn_reasoning_initial"].format(question=session.question)
        else:
            initial_prompt = PROMPTS["multi_turn_initial"].format(question=session.question)
        
        messages.append({"role": "user", "content": initial_prompt})

        # 2. History
        for past_trial in completed_trials:
            if past_trial.answer:
                messages.append({"role": "assistant", "content": past_trial.answer})
            messages.append({"role": "user", "content": "Your previous answer was incorrect."})

        # 3. Follow-up instructions (only if we have history)
        if completed_trials:
            if allow_reasoning:
                messages.append({"role": "user", "content": PROMPTS["multi_turn_reasoning_followup"]})
            else:
                messages.append({"role": "user", "content": PROMPTS["multi_turn_followup"]})
            
        return messages


class RagMultiTurnPipeline(BaseMultiTurnPipeline):
    def __init__(self, base_url, api_key, model, max_retries, reformulation_strategy='no_reform', pipeline_id=None, dataset_id=None):
        super().__init__(base_url, api_key, model, max_retries, pipeline_id, dataset_id)
        self.search_engine = get_search_engine()
        self.reformulation_strategy = reformulation_strategy
        self.redis_prefix = f"rag_multi_turn_{self.reformulation_strategy}_pipeline_active"
    
    def __str__(self):
        return f"RAG Multi-Turn Pipeline ({self.reformulation_strategy})"

    def get_settings_snapshot(self):
        rag_settings = RagSettings.load()
        search_settings = SearchSettings.load()
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
            'rag_settings': {
                'prompt_template': rag_settings.prompt_template
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
            reformulation_strategy=self.reformulation_strategy,
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

        first_trial = completed_trials[0] if completed_trials else None
        last_trial = completed_trials[-1] if completed_trials else None

        # Optimization: Reuse search results from the first trial if no reformulation is used
        if self.reformulation_strategy == 'no_reform' and trial.trial_number > 1:
            if first_trial:
                search_results = first_trial.search_results
                current_search_query = first_trial.search_query

        # Check if trial already has search results (e.g. from history reconstruction or manual run)
        if search_results is None and trial.search_results:
            search_results = trial.search_results
            current_search_query = trial.search_query

        if search_results is None:
            if self.reformulation_strategy == 'reform' and trial.trial_number > 1:
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

        for past_trial in completed_trials:
            if past_trial.answer:
                messages.append({"role": "assistant", "content": past_trial.answer})
            messages.append({"role": "user", "content": "Your previous answer was incorrect."})


        
        return messages

def parse_react_content(content):
    """
    Parses a ReAct-style text content into blocks of Thought, Action, Observation.
    """
    if not isinstance(content, str):
        return [{"type": "text", "content": content}]
        
    blocks = []
    current_type = "text"
    current_lines = []
    
    lines = content.split('\n')
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("Thought:") or stripped.startswith("Reasoning:"):
            if current_lines:
                blocks.append({"type": current_type, "content": "\n".join(current_lines).strip()})
            current_type = "thought"
            current_lines = [stripped.split(":", 1)[1].strip() if ":" in stripped else stripped]
        elif stripped.startswith("Action:") or stripped.startswith("Tool Call:"):
            if current_lines:
                blocks.append({"type": current_type, "content": "\n".join(current_lines).strip()})
            current_type = "action"
            current_lines = [stripped.split(":", 1)[1].strip() if ":" in stripped else stripped]
        elif stripped.startswith("Observation:") or stripped.startswith("Execution Result:"):
            if current_lines:
                blocks.append({"type": current_type, "content": "\n".join(current_lines).strip()})
            current_type = "observation"
            current_lines = [stripped.split(":", 1)[1].strip() if ":" in stripped else stripped]
        else:
            current_lines.append(line)
            
    if current_lines:
        blocks.append({"type": current_type, "content": "\n".join(current_lines).strip()})
        
    # Filter out empty blocks
    return [b for b in blocks if b['content']]

class VanillaAgentPipeline(BaseMultiTurnPipeline):
    def __init__(self, base_url, api_key, model, max_retries, pipeline_id=None, dataset_id=None):
        super().__init__(base_url, api_key, model, max_retries, pipeline_id, dataset_id)
        # Initialize AgentScope
        # We need to create a temporary settings object to pass to the factory
        # Since we might override settings in arguments
        self.temp_settings = LLMSettings(
            llm_base_url=base_url,
            llm_api_key=api_key,
            llm_model=model,
            temperature=0.0 # Default for agent
        )
        self.agent_model = VanillaAgentFactory.init_agentscope(self.temp_settings)
        self.redis_prefix = f"vanilla_agent_pipeline_active"

    def __str__(self):
        return "Vanilla Agent Pipeline"

    def get_settings_snapshot(self):
        rag_settings = RagSettings.load()
        search_settings = SearchSettings.load()
        return {
            'llm_settings': {
                'llm_base_url': self.llm_settings.llm_base_url,
                'llm_model': self.llm_settings.llm_model,
                'max_retries': self.llm_settings.max_retries,
            },
            'pipeline_type': 'vanilla_agent',
            'agent_config': {
                'model_name': self.agent_model.model_name if hasattr(self.agent_model, 'model_name') else 'unknown'
            }
        }

    def create_session(self, settings, question_text, ground_truths, group):
        return MultiTurnSession.objects.create(
            question=question_text,
            ground_truths=ground_truths,
            run=group,
            run_tag=self.pipeline_id,
            pipeline_type='vanilla_agent'
        )

    def create_trial(self, session, trial_number):
        return MultiTurnTrial.objects.create(
            session=session,
            trial_number=trial_number,
            status='processing'
        )

    def _process_single_session(self, group, question_text, ground_truths):
        """
        Process a single question session, including retries, utilizing the Vanilla Agent run_single_turn logic.
        """
        try:
            session = self.create_session(self.llm_settings, question_text, ground_truths, group)

            yield {
                'is_meta': True,
                'type': 'session_created',
                'session_id': session.id,
                'question': question_text,
                'group_id': group.id,
                'group_name': group.name
            }

            is_session_completed = False
            trial_number = 1
            final_is_correct = False
            final_answer = ""
            
            while trial_number <= self.max_retries and not is_session_completed:
                if not self.check_active():
                    break

                trial = self.create_trial(session, trial_number)
                
                yield {
                    'is_meta': True,
                    'type': 'trial_started',
                    'session_id': session.id,
                    'trial_number': trial_number,
                    'group_id': group.id
                }

                try:
                    # Execute agent logic
                    # run_single_turn returns (answer, is_correct, search_results)
                    parsed_answer, is_correct, _ = self.run_single_turn(session, trial)
                except Exception as e:
                    trial.status = 'error'
                    trial.save()
                    raise e
                
                # run_single_turn already handles saving trial status, correctness, etc.
                
                yield {
                    'is_meta': True,
                    'type': 'trial_completed',
                    'session_id': session.id,
                    'trial_number': trial_number,
                    'is_correct': is_correct,
                    'answer': parsed_answer,
                    'full_response': trial.full_response,
                    'group_id': group.id
                }

                final_answer = parsed_answer
                final_is_correct = is_correct

                if is_correct:
                    is_session_completed = True
                else:
                    trial_number += 1
            
            session.is_completed = True
            session.save()

            yield {
                'question': question_text,
                'correct': final_is_correct,
                'trials': trial_number if final_is_correct else (trial_number - 1),
                'session_id': session.id,
                'final_answer': final_answer,
                'ground_truths': ground_truths,
                'max_retries': self.max_retries,
                'group_name': group.name,
                'group_id': group.id
            }

        except Exception as e:
            yield {'error': str(e), 'question': question_text}

    def _serialize_trace(self, trace_msgs):
        trace_data = []
        real_answer_found = None
        should_stop = False
        
        for m in trace_msgs:
            if should_stop:
                break
                
            # Check for native tool calls
            m_dict = m.to_dict() if hasattr(m, 'to_dict') else m.__dict__
            
            # Helper to extract text from content list/dict
            def extract_text(c):
                if isinstance(c, str): return c
                if isinstance(c, list):
                    try:
                        texts = []
                        for item in c:
                            if isinstance(item, dict) and item.get('type') == 'text':
                                texts.append(item.get('text', ''))
                            elif isinstance(item, str):
                                texts.append(item)
                        return "".join(texts)
                    except: return json.dumps(c, indent=2)
                if isinstance(c, dict):
                    if c.get('type') == 'text': return c.get('text', '')
                    return json.dumps(c, indent=2)
                return str(c)

            # 1. Handle Tool Calls (Action)
            if m_dict.get('tool_calls') or m_dict.get('function_call'):
                 calls = m_dict.get('tool_calls') or m_dict.get('function_call')
                 
                 # Try to extract answer from tool call
                 if isinstance(calls, list):
                     for call in calls:
                         if call.get('name') == 'answer_question' or call.get('function', {}).get('name') == 'answer_question':
                             # Extract answer
                             args = call.get('input') or call.get('function', {}).get('arguments')
                             if isinstance(args, str):
                                 try: args = json.loads(args)
                                 except: pass
                             if isinstance(args, dict) and 'answer' in args:
                                 real_answer_found = args['answer']

                 content_str = json.dumps(calls, indent=2)
                 trace_data.append({
                     "role": m.role,
                     "name": m.name,
                     "step_type": "action",
                     "content": f"Tool Call: {content_str}",
                     "timestamp": getattr(m, 'timestamp', None)
                 })
                 if m.content:
                     trace_data.append({
                         "role": m.role,
                         "name": m.name,
                         "step_type": "thought",
                         "content": extract_text(m.content),
                         "timestamp": getattr(m, 'timestamp', None)
                     })
                 continue

            # 2. Handle Structured Content (e.g. Tool Results/Observations from agentscope)
            content = m.content
            if isinstance(content, list):
                try:
                    # Clean up nested JSON in tool results and SPLIT content
                    import copy
                    cleaned_content = copy.deepcopy(content)
                    
                    current_texts = []
                    
                    for item in cleaned_content:
                        if isinstance(item, dict) and item.get('type') == 'text':
                            current_texts.append(item.get('text', ''))
                        
                        elif isinstance(item, dict) and item.get('type') == 'tool_use':
                            # Flush texts as thought
                            if current_texts:
                                trace_data.append({
                                    "role": m.role,
                                    "name": m.name,
                                    "step_type": "thought",
                                    "content": "\n".join(current_texts),
                                    "timestamp": getattr(m, 'timestamp', None)
                                })
                                current_texts = []
                            
                            # Add action
                            if item.get('name') == 'answer_question':
                                 args = item.get('input')
                                 if isinstance(args, dict) and 'answer' in args:
                                     real_answer_found = args['answer']

                            trace_data.append({
                                "role": m.role,
                                "name": m.name,
                                "step_type": "action",
                                "content": f"Tool Call: {json.dumps(item, indent=2)}",
                                "timestamp": getattr(m, 'timestamp', None)
                            })

                        elif isinstance(item, dict) and item.get('type') == 'tool_result':
                            # Flush texts
                            if current_texts:
                                trace_data.append({
                                    "role": m.role,
                                    "name": m.name,
                                    "step_type": "text",
                                    "content": "\n".join(current_texts),
                                    "timestamp": getattr(m, 'timestamp', None)
                                })
                                current_texts = []

                            # Process output JSON if needed
                            output = item.get('output')
                            if isinstance(output, str) and (output.strip().startswith('[') or output.strip().startswith('{')):
                                try: item['output'] = json.loads(output)
                                except: pass
                            
                            if item.get('name') == 'answer_question':
                                should_stop = True
                            
                            trace_data.append({
                                "role": m.role,
                                "name": m.name,
                                "step_type": "observation",
                                "content": json.dumps(item, indent=2),
                                "timestamp": getattr(m, 'timestamp', None)
                            })
                        else:
                            # Fallback for unknown items in list
                            if isinstance(item, str):
                                current_texts.append(item)
                            else:
                                current_texts.append(json.dumps(item))

                    # Flush remaining texts
                    if current_texts:
                        trace_data.append({
                            "role": m.role,
                            "name": m.name,
                            "step_type": "thought" if m.role == "assistant" else "text",
                            "content": "\n".join(current_texts),
                            "timestamp": getattr(m, 'timestamp', None)
                        })

                    continue
                except Exception as e:
                    print_debug(f"Error parsing list content: {e}")
                    pass
                
                content = extract_text(content)
            elif isinstance(content, dict):
                content = extract_text(content)
            
            # 3. Handle Text Content (Thoughts/Standard messages)
            if isinstance(content, str):
                blocks = parse_react_content(content)
                for b in blocks:
                    trace_data.append({
                        "role": m.role,
                        "name": m.name,
                        "step_type": b['type'],
                        "content": b['content'],
                        "timestamp": getattr(m, 'timestamp', None)
                    })
            else:
                 trace_data.append({
                    "role": m.role,
                    "name": m.name,
                    "step_type": "text",
                    "content": str(content),
                    "timestamp": getattr(m, 'timestamp', None)
                })
        
        return trace_data, real_answer_found
    def run_single_turn(self, session, trial):
        # Re-init agentscope just in case (e.g. if run in a fresh worker)
        agent_model = VanillaAgentFactory.init_agentscope(self.temp_settings)
        
        # Construct history for the agent
        prev_trials = session.trials.filter(trial_number__lt=trial.trial_number).order_by('trial_number')
        
        history_msgs = []
        current_msg = None

        if trial.trial_number > 1:
            # Reconstruct full history including the original question
            history_msgs.append(Msg(name="User", role="user", content=f"Question: {session.question}"))
            
            # Convert to list to handle indexing
            trials_list = list(prev_trials)
            
            for i, pt in enumerate(trials_list):
                if pt.answer:
                     history_msgs.append(Msg(name="Assistant", role="assistant", content=pt.answer))
                
                # If NOT the last trial, add feedback to history
                if i < len(trials_list) - 1:
                     history_msgs.append(Msg(name="User", role="user", content=f"Incorrect. Feedback: {pt.feedback}"))
            
            # Last trial's feedback becomes the current prompt
            last_pt = trials_list[-1]
            current_msg = Msg(name="User", role="user", content=f"Your previous answer was incorrect. Feedback: {last_pt.feedback}. Please search again and provide the correct answer.")
        else:
            # First trial
            current_msg = Msg(name="User", role="user", content=f"Question: {session.question}")

        # Calculate history length to filter trace
        initial_history_len = len(history_msgs)

        # Define callback for streaming updates
        def on_memory_update(msgs):
            try:
                # Filter out history messages from the trace visualization
                # msgs contains [History..., Current_Prompt, Agent_Steps...]
                # We want to show [Current_Prompt, Agent_Steps...]
                # So slice from initial_history_len
                relevant_msgs = msgs[initial_history_len:] if len(msgs) > initial_history_len else []
                
                # Use self._serialize_trace logic
                trace_data, _ = self._serialize_trace(relevant_msgs)
                key = f"trial_trace:{trial.id}"
                redis_client.set(key, json.dumps(trace_data), ex=3600)
            except Exception as e:
                print_debug(f"Redis update failed: {e}")

        agent = VanillaAgentFactory.create_agent(agent_model, update_callback=on_memory_update)
        
        # Run the agent
        async def run_agent_task():
            import inspect
            
            # Populate history first
            if history_msgs:
                await agent.memory.add(history_msgs)

            response = await agent(current_msg)
            
            # Consume stream if applicable to ensure execution finishes
            if inspect.isasyncgen(response):
                final_res = None
                async for x in response:
                    final_res = x
                response = final_res
                
            # Memory access is async in agentscope v1.0.9+
            trace = await agent.memory.get_memory()
            return response, trace

        try:
            response_msg, trace_msgs = asyncio.run(run_agent_task())
        except Exception as e:
            print_debug(f"Agent execution failed: {e}")
            raise e
        
        # Handle potential list content from agentscope (fallback if tool not used)
        raw_content = response_msg.content
        if isinstance(raw_content, list):
            try:
                texts = []
                for c in raw_content:
                    if isinstance(c, dict) and c.get('type') == 'text':
                        texts.append(c.get('text', ''))
                    elif isinstance(c, str):
                        texts.append(c)
                answer = "".join(texts)
            except:
                answer = json.dumps(raw_content)
        else:
            answer = str(raw_content) if raw_content is not None else ""
        
        # Serialize trace (filtering history)
        relevant_trace_msgs = trace_msgs[initial_history_len:] if len(trace_msgs) > initial_history_len else []
        trace_data, real_answer_found = self._serialize_trace(relevant_trace_msgs)
        
        # Override answer if tool was used
        if real_answer_found:
            answer = real_answer_found
        
        full_response = json.dumps(trace_data)
        
        # If full_response is empty/invalid, just use answer (wrapped in a basic trace)
        if not trace_data:
             # Fallback
             full_response = json.dumps([{
                 "role": "assistant", 
                 "name": "Agent Debug Fallback", 
                 "content": answer
             }])

        # Check correctness
        is_correct = check_answer_llm(session.question, session.ground_truths, answer, client=self.client, model=self.model)

        trial.answer = answer
        trial.full_response = full_response
        trial.is_correct = is_correct
        trial.feedback = "Correct" if is_correct else "Incorrect"
        trial.status = 'completed'
        trial.save()

        return answer, is_correct, [] # No search results returned explicitly, they are in trace


class BrowserAgentPipeline(BaseMultiTurnPipeline):
    def __init__(self, base_url, api_key, model, max_retries, pipeline_id=None, dataset_id=None):
        super().__init__(base_url, api_key, model, max_retries, pipeline_id, dataset_id)
        self.temp_settings = LLMSettings(
            llm_base_url=base_url,
            llm_api_key=api_key,
            llm_model=model,
            temperature=0.0 # Default for agent
        )
        self.agent_model = None # Initialized by async factory
        self.agent_toolkit = None # Initialized by async factory
        self.mcp_client = None # Initialized by async factory
        self.redis_prefix = REDIS_PREFIX_BROWSER_AGENT

    @classmethod
    async def create(cls, base_url, api_key, model, max_retries, pipeline_id=None, dataset_id=None):
        instance = await sync_to_async(cls)(base_url, api_key, model, max_retries, pipeline_id, dataset_id)
        # Skip MCP initialization during creation to avoid loop binding issues
        instance.agent_model, instance.agent_toolkit, instance.mcp_client = await BrowserAgentFactory.init_agentscope(instance.temp_settings, skip_mcp=True)
        return instance

    def __str__(self):
        return "Browser Agent Pipeline"

    def get_settings_snapshot(self):
        return {
            'llm_settings': {
                'llm_base_url': self.llm_settings.llm_base_url,
                'llm_model': self.llm_settings.llm_model,
                'max_retries': self.llm_settings.max_retries,
            },
            'pipeline_type': 'browser_agent',
            'agent_config': {
                'model_name': self.agent_model.model_name if hasattr(self.agent_model, 'model_name') else 'unknown'
            }
        }

    def create_session(self, settings, question_text, ground_truths, group):
        return MultiTurnSession.objects.create(
            question=question_text,
            ground_truths=ground_truths,
            run=group,
            run_tag=self.pipeline_id,
            pipeline_type='browser_agent' # New pipeline type
        )

    def create_trial(self, session, trial_number):
        return MultiTurnTrial.objects.create(
            session=session,
            trial_number=trial_number,
            status='processing'
        )
        
    def _construct_messages(self, session, trial, completed_trials):
        print_debug(f"Constructing messages for BrowserAgentPipeline, trial number: {trial.trial_number}")
        # The browser agent's initial prompt is self-contained.
        # History will be managed by the agentscope agent itself.
        messages = []
        # If it's the first trial, the question is the primary message
        if trial.trial_number == 1:
            messages.append(Msg(name="User", role="user", content=f"Task: {session.question}"))
        else:
            # For subsequent trials (retries), we'll provide feedback
            # This mimics the ReAct agent's feedback mechanism
            last_trial = completed_trials[-1]
            feedback_message = f"Your previous attempt was incorrect. Feedback: {last_trial.feedback}. Please re-evaluate the task and try again."
            messages.append(Msg(name="User", role="user", content=feedback_message))
        
        return messages

    # Reusing the _serialize_trace from VanillaAgentPipeline since it handles tool calls generically
    _serialize_trace = VanillaAgentPipeline._serialize_trace

    async def _process_single_session_async(self, group, question_text, ground_truths):
        try:
            session = await sync_to_async(self.create_session)(self.llm_settings, question_text, ground_truths, group)

            yield {
                'is_meta': True,
                'type': 'session_created',
                'session_id': session.id,
                'question': question_text,
                'group_id': group.id,
                'group_name': group.name
            }

            is_session_completed = False
            trial_number = 1
            final_is_correct = False
            final_answer = ""
            
            while trial_number <= self.max_retries and not is_session_completed:
                if not await sync_to_async(self.check_active)():
                    break

                trial = await sync_to_async(self.create_trial)(session, trial_number)
                
                yield {
                    'is_meta': True,
                    'type': 'trial_started',
                    'session_id': session.id,
                    'trial_number': trial_number,
                    'group_id': group.id
                }

                try:
                    parsed_answer, is_correct, _ = await self.run_single_turn_async(session, trial)
                except Exception as e:
                    def update_error():
                        trial.status = 'error'
                        trial.save()
                    await sync_to_async(update_error)()
                    raise e
                
                yield {
                    'is_meta': True,
                    'type': 'trial_completed',
                    'session_id': session.id,
                    'trial_number': trial_number,
                    'is_correct': is_correct,
                    'answer': parsed_answer,
                    'full_response': trial.full_response,
                    'group_id': group.id
                }

                final_answer = parsed_answer
                final_is_correct = is_correct

                if is_correct:
                    is_session_completed = True
                else:
                    trial_number += 1
            
            session.is_completed = True
            await sync_to_async(session.save)()

            yield {
                'question': question_text,
                'correct': final_is_correct,
                'trials': trial_number if final_is_correct else (trial_number - 1),
                'session_id': session.id,
                'final_answer': final_answer,
                'ground_truths': ground_truths,
                'max_retries': self.max_retries,
                'group_name': group.name,
                'group_id': group.id
            }

        except Exception as e:
            yield {'error': str(e), 'question': question_text}

    async def cleanup(self):
        if self.mcp_client:
            try:
                # Attempt to close/disconnect MCP client to avoid TaskGroup errors
                if hasattr(self.mcp_client, 'disconnect'):
                    await self.mcp_client.disconnect()
                elif hasattr(self.mcp_client, 'close'):
                    await self.mcp_client.close()
            except Exception as e:
                print_debug(f"Error cleaning up MCP client: {e}")
            finally:
                self.mcp_client = None

    async def run(self):
        def create_run_obj():
            name = f"{str(self)}- {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}" 
            snapshot = self.get_settings_snapshot()
            return MultiTurnRun.objects.create(name=name, settings_snapshot=snapshot)

        group = await sync_to_async(create_run_obj)()
        
        total_questions = 0
        questions_iterator = None
        
        try:
            total_questions = await sync_to_async(self.get_total_questions)()
            questions_iterator = await sync_to_async(self.load_questions)()
        except Exception as e:
            yield {'error': str(e)}
            await sync_to_async(self.stop_token)()
            return

        yield {'is_meta': True, 'type': 'total_count', 'count': total_questions}
        
        try:
            all_questions = await sync_to_async(list)(questions_iterator)

            for data in all_questions:
                if not await sync_to_async(self.check_active)():
                    break

                question_text = data['question']
                ground_truths = data.get('ground_truths', [])
                
                async for event in self._process_single_session_async(group, question_text, ground_truths):
                    yield event
        finally:
            await self.cleanup()
            await sync_to_async(self.stop_token)()

    async def run_single_turn_async(self, session, trial, auto_cleanup=False):
        # Lazy init for MCP client (handle loop changes or delayed init)
        if not self.mcp_client:
             self.mcp_client = await BrowserAgentFactory.connect_mcp(self.agent_toolkit)

        # The agent_model, toolkit and mcp_client are already initialized in __init__
        
        # Async DB access for history
        def get_history():
            prev_trials = session.trials.filter(trial_number__lt=trial.trial_number).order_by('trial_number')
            return list(prev_trials)
            
        trials_list = await sync_to_async(get_history)()
        
        history_msgs = []
        if trial.trial_number > 1:
            # Reconstruct history for the browser agent for retries
            history_msgs.append(Msg(name="User", role="user", content=f"Task: {session.question}"))
            for i, pt in enumerate(trials_list):
                if pt.answer:
                    history_msgs.append(Msg(name="Assistant", role="assistant", content=pt.full_response))
                if i < len(trials_list) - 1:
                    history_msgs.append(Msg(name="User", role="user", content=f"Incorrect. Feedback: {pt.feedback}"))
            
            last_pt = trials_list[-1]
            current_msg = Msg(name="User", role="user", content=f"Your previous attempt was incorrect. Feedback: {last_pt.feedback}. Please re-evaluate the task and try again.")
        else:
            current_msg = Msg(name="User", role="user", content=f"Task: {session.question}")

        initial_history_len = len(history_msgs)

        def on_memory_update(msgs):
            try:
                relevant_msgs = msgs[initial_history_len:] if len(msgs) > initial_history_len else []
                trace_data, _ = self._serialize_trace(relevant_msgs)
                key = f"trial_trace:{trial.id}"
                redis_client.set(key, json.dumps(trace_data), ex=3600)
            except Exception as e:
                print_debug(f"Redis update failed in BrowserAgentPipeline: {e}")

        async def run_agent_task():
            agent = await BrowserAgentFactory.create_agent(self.agent_model, self.agent_toolkit, self.mcp_client, update_callback=on_memory_update)
            try:
                import inspect
                if history_msgs:
                    await agent.memory.add(history_msgs)
                response = await agent(current_msg)
                if inspect.isasyncgen(response):
                    final_res = None
                    async for x in response:
                        final_res = x
                    response = final_res
                trace = await agent.memory.get_memory()
                return response, trace
            except Exception as e:
                print_debug(f"Error in run_agent_task: {e}")
                raise e

        try:
            # Direct await instead of asyncio.run
            response_msg, trace_msgs = await run_agent_task()
        except Exception as e:
            print_debug(f"Browser agent execution failed: {e}")
            raise e
        finally:
            if auto_cleanup:
                await self.cleanup()
        
        raw_content = response_msg.content
        if isinstance(raw_content, list):
            try:
                texts = []
                for c in raw_content:
                    if isinstance(c, dict) and c.get('type') == 'text':
                        texts.append(c.get('text', ''))
                    elif isinstance(c, str):
                        texts.append(c)
                answer = "".join(texts)
            except:
                answer = json.dumps(raw_content)
        else:
            answer = str(raw_content) if raw_content is not None else ""
        
        relevant_trace_msgs = trace_msgs[initial_history_len:] if len(trace_msgs) > initial_history_len else []
        trace_data, real_answer_found = self._serialize_trace(relevant_trace_msgs)
        
        if real_answer_found:
            answer = real_answer_found
        
        full_response = json.dumps(trace_data)
        
        if not trace_data:
             full_response = json.dumps([{
                 "role": "assistant", 
                 "name": "Browser Agent Debug Fallback", 
                 "content": answer
             }])

        # Async DB access for saving result
        def save_result():
            is_correct = check_answer_llm(session.question, session.ground_truths, answer, client=self.client, model=self.model)
            trial.answer = answer
            trial.full_response = full_response
            trial.is_correct = is_correct
            trial.feedback = "Correct" if is_correct else "Incorrect"
            trial.status = 'completed'
            trial.save()
            return answer, is_correct

        answer, is_correct = await sync_to_async(save_result)()

        return answer, is_correct, []

    def run_single_turn(self, session, trial):
        # Auto-cleanup when running via sync wrapper (one-off execution)
        return asyncio.run(self.run_single_turn_async(session, trial, auto_cleanup=True))