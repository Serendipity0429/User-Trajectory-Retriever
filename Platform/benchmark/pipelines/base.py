import json
import os
import openai
import logging
import asyncio
import time
from datetime import datetime
from concurrent import futures
from task_manager.utils import redis_client
from ..utils import print_debug, extract_final_answer, count_questions_in_file
from ..models import (
    LLMSettings, BenchmarkDataset, 
    MultiTurnRun, MultiTurnSession, MultiTurnTrial
)
from ..trace_formatter import TraceFormatter


REDIS_PREFIX_ACTIVE = "pipeline_active"
REDIS_PREFIX_MULTI_TURN = "multi_turn_pipeline_active"
REDIS_PREFIX_VANILLA_MULTI_TURN = "vanilla_llm_multi_turn_pipeline_active"
REDIS_PREFIX_BROWSER_AGENT = "browser_agent_pipeline_active"

HARD_QUESTIONS_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'hard_questions_refined.jsonl')

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
        self.llm_settings = LLMSettings.get_effective_settings()

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

    def get_llm_response(self, messages, temperature=None, allow_reasoning=None):
        """
        Sends messages to LLM and parses the response based on current settings.
        Returns: (parsed_answer, full_response)
        """
        if temperature is None:
            temperature = getattr(self.llm_settings, 'temperature', 0.0)
            
        top_p = getattr(self.llm_settings, 'top_p', 1.0)
        max_tokens = getattr(self.llm_settings, 'max_tokens', None)
        
        # Determine whether to extract final answer
        should_extract = allow_reasoning if allow_reasoning is not None else getattr(self.llm_settings, 'allow_reasoning', False)

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
                
                if should_extract:
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
        raise NotImplementedError("Subclasses must implement the 'run' method.")
        
    def get_settings_snapshot(self):
        """
        Returns the base settings snapshot with LLM settings.
        Subclasses can extend this.
        """
        return {
            'llm_settings': {
                'llm_base_url': self.llm_settings.llm_base_url,
                'llm_model': self.llm_settings.llm_model,
                'max_retries': getattr(self.llm_settings, 'max_retries', 3), # Handle defaults safely
                'allow_reasoning': getattr(self.llm_settings, 'allow_reasoning', False),
                'temperature': getattr(self.llm_settings, 'temperature', 0.0),
                'top_p': getattr(self.llm_settings, 'top_p', 1.0),
                'max_tokens': getattr(self.llm_settings, 'max_tokens', None)
            }
        }


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
                    # Delegate execution to run_single_turn
                    # This method is overridden by subclasses (e.g. VanillaAgentPipeline) 
                    # or used as-is (VanillaLLM, RAG)
                    parsed_answer, is_correct, _ = self.run_single_turn(session, trial)
                except Exception as e:
                    trial.status = 'error'
                    trial.save()
                    raise e
                
                # run_single_turn handles saving the trial
                
                yield {
                    'is_meta': True,
                    'type': 'trial_completed',
                    'session_id': session.id,
                    'trial_number': trial_number,
                    'is_correct': is_correct,
                    'answer': parsed_answer, 
                    'full_response': trial.full_response, # Access stored full response
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
        
        try:
            total_questions = 0
            questions_iterator = None
            
            try:
                total_questions = self.get_total_questions()
                questions_iterator = self.load_questions()
            except (ValueError, FileNotFoundError, BenchmarkDataset.DoesNotExist) as e:
                yield {'error': str(e)}
                return

            yield {'is_meta': True, 'type': 'total_count', 'count': total_questions}

            for data in questions_iterator:
                if not self.check_active():
                    break

                question_text = data['question']
                ground_truths = data.get('ground_truths', [])
                
                yield from self._process_single_session(group, question_text, ground_truths)
        except Exception as e:
            yield {'error': str(e)}
        finally:
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
        
        # Extract the last user message to use as the instruction
        instruction = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                instruction = msg.get("content", "")
                break
        
        # Extract allow_reasoning from session snapshot to ensure consistency
        settings_snapshot = session.run.settings_snapshot
        allow_reasoning = settings_snapshot.get('llm_settings', {}).get('allow_reasoning', False)
        
        try:
            answer, full_response = self.get_llm_response(messages, allow_reasoning=allow_reasoning)
        except Exception as e:
            trial.status = 'error'
            trial.save()
            raise e

        # Logic for checking answer
        from task_manager.utils import check_answer_llm
        is_correct = check_answer_llm(session.question, session.ground_truths, answer, client=self.client, model=self.model)

        trial.answer = answer
        trial.full_response = full_response # Save full response too
        trial.is_correct = is_correct
        trial.feedback = "Correct" if is_correct else "Incorrect"
        trial.query_instruction = instruction
        trial.status = 'completed'
        trial.save()
        
        # Cache completion status in Redis for efficient polling
        try:
            status_data = {
                "id": trial.id,
                "status": "completed",
                "answer": trial.answer,
                "feedback": trial.feedback,
                "is_correct": trial.is_correct,
                "full_response": trial.full_response,
                "query_instruction": trial.query_instruction
            }
            redis_client.set(f"trial_status:{trial.id}", json.dumps(status_data), ex=3600) # Expire in 1 hour
            
            # Cache Trace for UI (Vanilla/Base pipelines)
            trace_data = []
            for msg in messages:
                trace_data.append({
                    "role": msg.get('role', 'unknown'),
                    "content": msg.get('content', ''),
                    "step_type": "text"
                })
            trace_data.append({
                "role": "assistant",
                "content": full_response,
                "step_type": "text"
            })
            redis_client.set(f"trial_trace:{trial.id}", json.dumps(trace_data), ex=3600)

        except Exception as e:
            print_debug(f"Failed to cache trial status/trace: {e}")
        
        return answer, is_correct, getattr(trial, 'search_results', [])
class BaseAgentPipeline(BaseMultiTurnPipeline):
    """
    Base class for Agent pipelines (Vanilla and Browser) to share trace serialization
    and result saving logic.
    """
    def _serialize_trace(self, trace_msgs):
        return TraceFormatter.serialize(trace_msgs)

    def save_trial_result(self, session, trial, answer, full_response):
        """
        Saves the trial result to DB and caches status in Redis.
        Returns: (answer, is_correct)
        """
        from task_manager.utils import check_answer_llm
        is_correct = check_answer_llm(session.question, session.ground_truths, answer, client=self.client, model=self.model)

        trial.answer = answer
        trial.full_response = full_response
        trial.is_correct = is_correct
        trial.feedback = "Correct" if is_correct else "Incorrect"
        trial.status = 'completed'
        trial.save()

        # Cache completion status in Redis
        try:
            status_data = {
                "id": trial.id,
                "status": "completed",
                "answer": trial.answer,
                "feedback": trial.feedback,
                "is_correct": trial.is_correct,
                "full_response": trial.full_response
            }
            redis_client.set(f"trial_status:{trial.id}", json.dumps(status_data), ex=3600)
        except Exception as e:
            print_debug(f"Failed to cache agent trial status: {e}")
            
        return answer, is_correct
