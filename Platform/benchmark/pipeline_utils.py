import json
import os
import openai
import logging
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

REDIS_PREFIX_ACTIVE = "pipeline_active"
REDIS_PREFIX_VANILLA_ADHOC = "vanilla_llm_adhoc_pipeline_active"
REDIS_PREFIX_RAG_ADHOC = "rag_adhoc_pipeline_active"
REDIS_PREFIX_MULTI_TURN = "multi_turn_pipeline_active"
REDIS_PREFIX_VANILLA_MULTI_TURN = "vanilla_llm_multi_turn_pipeline_active"

HARD_QUESTIONS_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'hard_questions_refined.jsonl')

def serialize_events(generator):
    """
    Helper function to serialize events from the pipeline generator.
    """
    for event in generator:
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

        try:
            response = self.client.chat.completions.create(**kwargs)
            full_response = response.choices[0].message.content
        except Exception as e:
            # Let the caller handle or wrap exceptions
            raise e

        if self.llm_settings.allow_reasoning:
            answer = extract_final_answer(full_response)
        else:
            answer = full_response
            
        return answer, full_response
    
    def run(self):
        yield {'is_meta': True, 'type': 'info', 'message': 'Pipeline started'}
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

        if allow_reasoning:
            messages.append({"role": "user", "content": "Answer the question based on the context. Reference the provided source (like [1]) to avoid hallucination.\nFirst, explain your reasoning step-by-step.\nThen, on a new line, provide the final answer starting with 'Final Answer:'.\n\nFollow these rules for the final answer strictly:\n1. It must be an exact match to the correct answer.\n2. Do not include any punctuation.\n3. Do not include any extra words or sentences."})
        else:
            messages.append({"role": "user", "content": "Answer the question based on the context. Return ONLY the exact answer."})
        
        return messages