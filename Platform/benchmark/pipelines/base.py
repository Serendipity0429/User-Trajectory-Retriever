import json
import os
import openai
import asyncio
import time
from asgiref.sync import sync_to_async
from datetime import datetime
from task_manager.utils import redis_client, check_answer_rule, check_answer_llm
from ..utils import (
    print_debug, extract_final_answer, count_questions_in_file,
    TrialGuard, RedisKeys, PipelinePrefix,
    TraceFormatter, SimpleMsg, PROMPTS
)
from ..models import (
    BenchmarkSettings, BenchmarkDataset,
    MultiTurnRun, MultiTurnSession, MultiTurnTrial
)
from agentscope.message import Msg


# Re-export for backward compatibility with other modules
REDIS_PREFIX_ACTIVE = PipelinePrefix.ACTIVE
REDIS_PREFIX_MULTI_TURN = PipelinePrefix.MULTI_TURN
REDIS_PREFIX_VANILLA_MULTI_TURN = PipelinePrefix.VANILLA
REDIS_PREFIX_BROWSER_AGENT = PipelinePrefix.BROWSER_AGENT

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
        self.llm_settings = BenchmarkSettings.get_effective_settings()

    def check_active(self):
        if not self.pipeline_id:
            return True
        return redis_client.get(RedisKeys.pipeline_active(self.redis_prefix, self.pipeline_id))

    def stop_token(self):
        if self.pipeline_id:
            redis_client.delete(RedisKeys.pipeline_active(self.redis_prefix, self.pipeline_id))

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
                    sleep_time = (2 ** attempt) * 0.5  # 0.5s, 1s, 2s, 4s...
                    time.sleep(sleep_time)
                else:
                    raise last_exception

    def get_llm_response_stream(self, messages, temperature=None):
        """
        Sends messages to LLM and yields the full response as it grows.
        """
        if temperature is None:
            temperature = getattr(self.llm_settings, 'temperature', 0.0)
            
        top_p = getattr(self.llm_settings, 'top_p', 1.0)
        max_tokens = getattr(self.llm_settings, 'max_tokens', None)
        
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
            "stream": True
        }
        if max_tokens:
            kwargs['max_tokens'] = max_tokens

        full_response = ""
        try:
            response = self.client.chat.completions.create(**kwargs)
            for chunk in response:
                if not chunk.choices:
                    continue
                content = chunk.choices[0].delta.content
                if content:
                    full_response += content
                    yield full_response
        except Exception as e:
            print_debug(f"LLM API stream failed: {e}")
            raise e
    
    async def run(self):
        raise NotImplementedError("Subclasses must implement the 'run' method.")
        
    def get_settings_snapshot(self):
        """
        Returns the base settings snapshot with LLM settings.
        Subclasses can extend this.
        """
        return {
            'llm': {
                'llm_base_url': self.llm_settings.llm_base_url,
                'llm_model': self.llm_settings.llm_model,
                'max_retries': getattr(self.llm_settings, 'max_retries', 3), # Handle defaults safely
                'allow_reasoning': getattr(self.llm_settings, 'allow_reasoning', False),
                'temperature': getattr(self.llm_settings, 'temperature', 0.0),
                'top_p': getattr(self.llm_settings, 'top_p', 1.0),
                'max_tokens': getattr(self.llm_settings, 'max_tokens', None),
                'llm_api_key': self.llm_settings.llm_api_key
            }
        }


class BaseMultiTurnPipeline(BasePipeline):
    def __init__(self, base_url, api_key, model, max_retries, pipeline_id=None, dataset_id=None, group_id=None):
        super().__init__(base_url, api_key, model, pipeline_id, dataset_id)
        self.max_retries = max_retries
        self.redis_prefix = REDIS_PREFIX_MULTI_TURN
        self.group_id = group_id

    def create_session(self, settings, question_text, ground_truths, group):
        raise NotImplementedError("Subclasses must implement create_session")

    def create_trial(self, session, trial_number):
        raise NotImplementedError("Subclasses must implement create_trial")
    
    def _construct_messages(self, session, trial, completed_trials):
        raise NotImplementedError("Subclasses must implement _construct_messages")

    def _get_trial_meta(self, trial) -> dict:
        """
        Override to return baseline-specific metadata for export/analytics.
        This data is stored in trial.log['meta'] separate from conversation messages.
        """
        return {}

    def _process_single_session(self, group, question_text, ground_truths, existing_session=None):
        """
        Process a single question session, including retries.
        Yields events for each step.
        """
        try:
            if existing_session:
                session = existing_session
                # Clean up stalled/incomplete trials to retry the step
                session.trials.exclude(status='completed').delete()

                last_completed = session.trials.order_by('trial_number').last()

                if last_completed:
                    # Check if session is actually finished (correct or reached max retries)
                    if last_completed.is_correct_llm or last_completed.trial_number >= self.max_retries:
                        # Session is done, mark as completed and skip
                        session.is_completed = True
                        session.save()
                        return  # Skip processing this session
                    else:
                        # Session not finished yet, delete last trial and rerun it
                        trial_number = last_completed.trial_number
                        last_completed.delete()
                else:
                    # No completed trials, start from trial 1
                    trial_number = 1
            else:
                session = self.create_session(self.llm_settings, question_text, ground_truths, group)
                trial_number = 1

            yield {
                'is_meta': True,
                'type': 'session_created',
                'session_id': session.id,
                'question': question_text,
                'group_id': group.id,
                'group_name': group.name
            }

            is_session_completed = False
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
                    parsed_answer, is_correct_llm, _ = self.run_single_turn(session, trial)
                except Exception as e:
                    raise e

                # run_single_turn handles saving the trial

                yield {
                    'is_meta': True,
                    'type': 'trial_completed',
                    'session_id': session.id,
                    'trial_number': trial_number,
                    'is_correct': is_correct_llm,
                    'is_correct_llm': is_correct_llm,
                    'is_correct_rule': trial.is_correct_rule,
                    'answer': parsed_answer,
                    'group_id': group.id
                }

                final_answer = parsed_answer
                final_is_correct = is_correct_llm

                if is_correct_llm:
                    is_session_completed = True
                else:
                    trial_number += 1
            session.is_completed = True
            session.save()

            first_trial = session.trials.order_by('trial_number').first()
            yield {
                'question': question_text,
                'correct': final_is_correct,
                'is_correct_llm': final_is_correct, # For consistency
                'is_correct_rule': trial.is_correct_rule,
                'trials': trial_number if final_is_correct else (trial_number - 1),
                'session_id': session.id,
                'final_answer': final_answer,
                'ground_truths': ground_truths,
                'max_retries': self.max_retries,
                'group_name': group.name,
                'group_id': group.id,
                'initial_correct': first_trial.is_correct_llm if first_trial else None,
                'initial_correct_rule': first_trial.is_correct_rule if first_trial else None,
                'coherence': (
                    sum(1 for t in session.trials.all() if t.is_correct_llm == t.is_correct_rule) / session.trials.count()
                    if session.trials.count() > 0 else 0
                )
            }

        except Exception as e:
            yield {'error': str(e), 'question': question_text, 'session_id': session.id if 'session' in locals() else None}

    def run(self):
        completed_questions = set()
        incomplete_sessions = {}
        
        if self.group_id:
            try:
                group = MultiTurnRun.objects.get(pk=self.group_id)
                
                # Identify completed questions
                completed_questions = set(
                    group.sessions.filter(is_completed=True).values_list('question', flat=True)
                )
                
                # Map incomplete sessions: question -> session object
                # We use a dict to quickly look up if an incomplete session exists for a question
                incomplete_qs = group.sessions.filter(is_completed=False)
                for s in incomplete_qs:
                    incomplete_sessions[s.question] = s
                    
            except MultiTurnRun.DoesNotExist:
                yield {'error': f"Group with ID {self.group_id} not found."}
                return
        else:
            group_name = f"{str(self)}- {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}" 
            # Create a new settings instance for this run
            new_settings = self.llm_settings.clone()
            new_settings.save()
            group = MultiTurnRun.objects.create(name=group_name, settings=new_settings)
        
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
                
                # Resume Logic: Skip if completed
                if question_text in completed_questions:
                    continue
                
                ground_truths = data.get('ground_truths', [])
                
                # Check for existing incomplete session
                existing_session = incomplete_sessions.get(question_text)

                yield from self._process_single_session(group, question_text, ground_truths, existing_session)
        except Exception as e:
            yield {'error': str(e)}
        finally:
            self.stop_token()

    def run_single_turn(self, session, trial):
        """
        Executes a single turn for a given session and trial object.
        """
        with TrialGuard(trial):
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
            
            # Extract allow_reasoning from session run settings
            allow_reasoning = False
            if session.run and session.run.settings:
                allow_reasoning = session.run.settings.allow_reasoning
            
            # Prepare trace components using TraceFormatter
            static_trace_msgs = []
            if messages:
                if messages[0].get('role') == 'system':
                    static_trace_msgs.append(SimpleMsg('system', messages[0].get('content')))
            static_trace_msgs.append(SimpleMsg("user", instruction))

            def update_redis_trace(current_full_response):
                temp_trace_msgs = static_trace_msgs + [SimpleMsg("assistant", current_full_response)]
                trace_data, _ = TraceFormatter.serialize(temp_trace_msgs)
                redis_client.set(RedisKeys.trial_trace(trial.id), json.dumps(trace_data), ex=RedisKeys.DEFAULT_TTL)

            full_response = ""
            # 1. Stream the response and update Redis periodically
            chunk_count = 0
            for partial_response in self.get_llm_response_stream(messages):
                full_response = partial_response
                chunk_count += 1
                if chunk_count % 5 == 0: # Update every 5 chunks to reduce overhead
                    update_redis_trace(full_response)
            
            # Final update
            update_redis_trace(full_response)
            
            # Extract final answer
            if allow_reasoning:
                answer = extract_final_answer(full_response)
            else:
                answer = full_response

            # Logic for checking answer
            is_correct_llm = check_answer_llm(session.question, session.ground_truths, answer, client=self.client, model=self.model)
            is_correct_rule = check_answer_rule(session.question, session.ground_truths, answer)

            # Store only this trial's messages (delta), not full conversation history
            # This matches the trace structure: system prompt + current user input + response
            trial_messages = []
            if messages and messages[0].get('role') == 'system':
                trial_messages.append({"role": "system", "content": messages[0].get("content", "")})
            trial_messages.append({"role": "user", "content": instruction})
            trial_messages.append({"role": "assistant", "content": full_response})

            trial.answer = answer
            trial.is_correct_llm = is_correct_llm
            trial.is_correct_rule = is_correct_rule
            trial.feedback = "Correct" if is_correct_llm else "Incorrect"

            trial.log = trial.log or {}
            trial.log['messages'] = trial_messages
            trial.status = 'completed'
            trial.save()

            # Cache completion status in Redis for efficient polling (parse trace for UI)
            try:
                trace, _ = TraceFormatter.serialize([SimpleMsg(m["role"], m["content"]) for m in trial_messages])
                status_data = {
                    "id": trial.id,
                    "status": "completed",
                    "answer": trial.answer,
                    "feedback": trial.feedback,
                    "is_correct_llm": trial.is_correct_llm,
                    "is_correct_rule": trial.is_correct_rule,
                }
                redis_client.set(RedisKeys.trial_status(trial.id), json.dumps(status_data), ex=RedisKeys.DEFAULT_TTL)
                redis_client.set(RedisKeys.trial_trace(trial.id), json.dumps(trace), ex=RedisKeys.DEFAULT_TTL)
            except Exception as e:
                print_debug(f"Failed to cache trial status/trace: {e}")
            
            return answer, is_correct_llm, []


class BaseAgentPipeline(BaseMultiTurnPipeline):
    """
    Base class for Agent pipelines (Vanilla and Browser) using the Template Method pattern.
    It centralizes the heavy lifting of async session management and state persistence,
    allowing subclasses to focus purely on agent initialization and execution.
    """
    def _serialize_trace(self, trace_msgs):
        return TraceFormatter.serialize(trace_msgs)

    async def _populate_agent_memory(self, session, agent):
        """
        Reconstructs the agent's internal state from database messages of previous trials.

        This is critical for 'Long-Term Coherence': it ensures that if a session is
        interrupted and resumed, the LLM still 'remembers' its previous attempts and
        can reflect on its failures as if the conversation never broke.
        """
        completed_trials = await sync_to_async(lambda: list(session.trials.filter(
            status='completed'
        ).order_by('trial_number')))()

        for t in completed_trials:
            messages = t.log.get('messages', [])
            for msg_dict in messages:
                if msg_dict.get('role') == 'system':
                    continue

                # Rebuild Msg objects from stored dict representation
                msg = Msg(
                    name=msg_dict.get('name'),
                    role=msg_dict.get('role'),
                    content=msg_dict.get('content')
                )
                await agent.memory.add(msg)

    async def _process_single_session_async(self, group, question_text, ground_truths, existing_session=None):
        """
        Orchestrates the lifecycle of a single question across multiple trials.
        Handles retry logic and session-level metadata events for the UI.
        """
        try:
            if existing_session:
                session = existing_session
                # Resumption logic: clean up stalled trials and find where we left off.
                def cleanup_and_check():
                    session.trials.exclude(status='completed').delete()
                    last_completed = session.trials.order_by('trial_number').last()

                    if last_completed:
                        # Check if session is actually finished (correct or reached max retries)
                        if last_completed.is_correct_llm or last_completed.trial_number >= self.max_retries:
                            # Session is done, mark as completed and return None to signal skip
                            session.is_completed = True
                            session.save()
                            return None
                        else:
                            # Session not finished yet, delete last trial and rerun it
                            trial_num = last_completed.trial_number
                            last_completed.delete()
                            return trial_num
                    else:
                        return 1

                trial_number = await sync_to_async(cleanup_and_check)()
                if trial_number is None:
                    return  # Skip processing this session
            else:
                session = await sync_to_async(self.create_session)(self.llm_settings, question_text, ground_truths, group)
                trial_number = 1

            yield {
                'is_meta': True, 'type': 'session_created', 'session_id': session.id,
                'question': question_text, 'group_id': group.id, 'group_name': group.name
            }

            is_session_completed = False
            final_is_correct = False
            final_answer = ""
            
            while trial_number <= self.max_retries and not is_session_completed:
                if not await sync_to_async(self.check_active)():
                    break

                trial = await sync_to_async(self.create_trial)(session, trial_number)
                yield {
                    'is_meta': True, 'type': 'trial_started', 'session_id': session.id,
                    'trial_number': trial_number, 'group_id': group.id
                }

                try:
                    parsed_answer, is_correct_llm, _ = await self.run_single_turn_async(session, trial)
                except Exception as e:
                    raise e
                
                yield {
                    'is_meta': True, 'type': 'trial_completed', 'session_id': session.id,
                    'trial_number': trial_number, 'is_correct': is_correct_llm,
                    'is_correct_llm': is_correct_llm, 'is_correct_rule': trial.is_correct_rule,
                    'answer': parsed_answer, 'group_id': group.id
                }

                final_answer = parsed_answer
                final_is_correct = is_correct_llm
                if is_correct_llm: is_session_completed = True
                else: trial_number += 1
            
            session.is_completed = True
            await sync_to_async(session.save)()

            first_trial = await sync_to_async(lambda: session.trials.order_by('trial_number').first())()
            yield {
                'question': question_text, 'correct': final_is_correct,
                'is_correct_llm': final_is_correct, 'is_correct_rule': trial.is_correct_rule,
                'trials': trial_number if final_is_correct else (trial_number - 1),
                'session_id': session.id, 'final_answer': final_answer,
                'ground_truths': ground_truths, 'max_retries': self.max_retries,
                'group_name': group.name, 'group_id': group.id,
                'initial_correct': first_trial.is_correct_llm if first_trial else None,
                'initial_correct_rule': first_trial.is_correct_rule if first_trial else None,
                'coherence': await sync_to_async(lambda: (
                    sum(1 for t in session.trials.all() if t.is_correct_llm == t.is_correct_rule) / session.trials.count()
                    if session.trials.count() > 0 else 0
                ))()
            }
        except Exception as e:
            yield {'error': str(e), 'question': question_text}

    async def run(self):
        """
        The main pipeline entry point. Manages the high-level loop over questions
        in a dataset, supporting run resumption and stop signals.
        """
        def create_run_obj():
            name = f"{str(self)}- {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}" 
            new_settings = self.llm_settings.clone()
            new_settings.save()
            return MultiTurnRun.objects.create(name=name, settings=new_settings)

        completed_questions = set()
        incomplete_sessions = {}

        if self.group_id:
            try:
                group = await sync_to_async(MultiTurnRun.objects.get)(pk=self.group_id)
                completed_questions = set(await sync_to_async(lambda: list(group.sessions.filter(is_completed=True).values_list('question', flat=True)))())
                def get_incomplete_map():
                    mapping = {}
                    qs = group.sessions.filter(is_completed=False)
                    for s in qs: mapping[s.question] = s
                    return mapping
                incomplete_sessions = await sync_to_async(get_incomplete_map)()
            except MultiTurnRun.DoesNotExist:
                 yield {'error': f"Group with ID {self.group_id} not found."}
                 return
        else:
            group = await sync_to_async(create_run_obj)()
        
        file_path = await sync_to_async(self.get_questions_file_path)()
        total_questions = await sync_to_async(count_questions_in_file)(file_path)
        yield {'is_meta': True, 'type': 'total_count', 'count': total_questions}
        
        from .agent import question_file_iterator
        questions_iterator = question_file_iterator(file_path)
        
        count = 0
        while True:
            if not await sync_to_async(self.check_active)(): break
            try:
                data = await sync_to_async(next)(questions_iterator)
                count += 1
            except StopIteration: break
            
            question_text = data['question']
            if question_text in completed_questions: continue
            
            ground_truths = data.get('ground_truths', [])
            existing_session = incomplete_sessions.get(question_text)
            
            async for event in self._process_single_session_async(group, question_text, ground_truths, existing_session):
                yield event
        
        await self.cleanup()
        await sync_to_async(self.stop_token)()

    async def cleanup(self):
        """Optional hook for subclasses to release resources (e.g. MCP connections)."""
        pass

    async def run_single_turn_async(self, session, trial):
        """
        TEMPLATE METHOD: Executes a single turn of the agent.
        
        This manages the context preparation and result persistence, while delegating 
        the specific initialization and execution logic to subclasses via hooks.
        """
        from ..utils import AsyncTrialGuard
        async with AsyncTrialGuard(trial):
            # 1. Prepare Agent & Message
            if trial.trial_number == 1:
                # Reset agent for fresh start.
                if hasattr(self, 'active_agent'): self.active_agent = None
                current_msg = Msg(name="User", role="user", content=PROMPTS["shared_user_question"].format(question=session.question))
                turn_start_index = 0
            else:
                # Retry logic: ensure agent is alive and context is inherited.
                if not hasattr(self, 'active_agent') or not self.active_agent:
                    self.active_agent = await self._init_agent()
                    await self._populate_agent_memory(session, self.active_agent)
                
                last_trial = await sync_to_async(lambda: session.trials.filter(status='completed').last())()
                feedback = last_trial.feedback if last_trial else "Incorrect"
                retry_prompt = self._get_retry_prompt_key()
                current_msg = Msg(name="User", role="user", content=PROMPTS[retry_prompt].format(feedback=feedback))
                
                try:
                    current_mem = await self.active_agent.memory.get_memory()
                    turn_start_index = len(current_mem) if current_mem else 0
                except: turn_start_index = 0

            if not hasattr(self, 'active_agent') or not self.active_agent:
                self.active_agent = await self._init_agent()
            
            # The update hook allows real-time trace streaming to the frontend.
            self.active_agent.memory._update_hook = lambda: self._update_trace(trial, turn_start_index, self._get_system_prompt_key())

            try:
                # 2. Execute Agent (delegated hook)
                response_msg = await self._execute_agent(current_msg)

                # 3. Process Response
                trace_msgs = await self.active_agent.memory.get_memory()
                answer = self._parse_answer(response_msg)

                # Slice to only save the 'delta' for the current trial
                relevant_trace_msgs = trace_msgs[turn_start_index:] if len(trace_msgs) > turn_start_index else []

                # Parse trace for UI rendering and answer extraction
                trace_data, real_answer_found = self._serialize_trace(relevant_trace_msgs)
                if real_answer_found: answer = real_answer_found

                # Ensure system prompt is at top of trace
                if not trace_data or trace_data[0].get('role') != 'system':
                    system_prompt_step = {"role": "system", "content": PROMPTS[self._get_system_prompt_key()], "step_type": "text"}
                    trace_data = [system_prompt_step] + trace_data

                # 4. Save - pass raw messages and parsed trace
                answer, is_correct_llm = await sync_to_async(self.save_trial_result)(
                    session, trial, answer, relevant_trace_msgs, trace_data
                )
            finally:
                # Avoid side-effects after trial finishes.
                if hasattr(self, 'active_agent') and self.active_agent:
                    self.active_agent.memory._update_hook = None
            
            return answer, is_correct_llm, []

    # --- Subclass Implementation Hooks ---
    
    async def _init_agent(self): 
        """Must return an initialized AgentScope agent."""
        raise NotImplementedError()
    
    async def _execute_agent(self, msg): 
        """Wrapper for calling the agent, allows subclasses to handle async generators."""
        return await self.active_agent(msg)
    
    def _get_system_prompt_key(self): raise NotImplementedError()
    def _get_retry_prompt_key(self): raise NotImplementedError()
    
    def _parse_answer(self, response_msg):
        """Extracts text answer from multi-modal or structured responses."""
        raw_content = response_msg.content
        if isinstance(raw_content, list):
            try:
                texts = [c.get('text', '') if isinstance(c, dict) else str(c) for c in raw_content]
                return "".join(texts)
            except: return json.dumps(raw_content)
        return str(raw_content) if raw_content is not None else ""

    async def _update_trace(self, trial, turn_start_index, system_prompt_key):
        """Updates the real-time trace in Redis for frontend rendering."""
        try:
            msgs = await self.active_agent.memory.get_memory()
            relevant_msgs = msgs[turn_start_index:] if len(msgs) > turn_start_index else []
            trace_data, _ = self._serialize_trace(relevant_msgs)
            if not trace_data or trace_data[0].get('role') != 'system':
                system_prompt_step = {"role": "system", "content": PROMPTS[system_prompt_key], "step_type": "text"}
                trace_data = [system_prompt_step] + trace_data
            key = RedisKeys.trial_trace(trial.id)
            await asyncio.to_thread(redis_client.set, key, json.dumps(trace_data), RedisKeys.DEFAULT_TTL)
        except Exception as e: print_debug(f"Trace update failed: {e}")

    def save_trial_result(self, session, trial, answer, messages, trace_data):
        """
        Saves the trial result to DB and caches status in Redis.
        Args:
            messages: Raw Msg objects (list) - the authentic agent context
            trace_data: Parsed trace for UI rendering
        Returns: (answer, is_correct_llm)
        """
        is_correct_llm = check_answer_llm(session.question, session.ground_truths, answer, client=self.client, model=self.model)
        is_correct_rule = check_answer_rule(session.question, session.ground_truths, answer)

        trial.answer = answer
        trial.is_correct_llm = is_correct_llm
        trial.is_correct_rule = is_correct_rule
        trial.feedback = "Correct" if is_correct_llm else "Incorrect"

        # Store raw messages (authentic agent context)
        trial.log = trial.log or {}
        trial.log['messages'] = [m.to_dict() if hasattr(m, 'to_dict') else m for m in messages]

        # Calculate query metrics from trace
        query_metrics = self._calculate_query_metrics(trace_data)
        trial.log.update(query_metrics)

        trial.status = 'completed'
        trial.save()

        # Cache completion status in Redis (with trace for live UI)
        try:
            status_data = {
                "id": trial.id,
                "status": "completed",
                "answer": trial.answer,
                "feedback": trial.feedback,
                "is_correct_llm": trial.is_correct_llm,
                "is_correct_rule": trial.is_correct_rule,
                "query_metrics": query_metrics
            }
            redis_client.set(RedisKeys.trial_status(trial.id), json.dumps(status_data), ex=RedisKeys.DEFAULT_TTL)
            # Cache trace separately for live UI rendering
            redis_client.set(RedisKeys.trial_trace(trial.id), json.dumps(trace_data), ex=RedisKeys.DEFAULT_TTL)
        except Exception as e:
            print_debug(f"Failed to cache agent trial status: {e}")

        return answer, is_correct_llm

    def _calculate_query_metrics(self, trace_data):
        """
        Extracts search queries from trace_data and calculates metrics.
        """
        queries = []
        for step in trace_data:
            if step.get('step_type') == 'action':
                content = step.get('content', '')
                try:
                    # Content can be a JSON string of a list of tool calls
                    actions = json.loads(content)
                    if isinstance(actions, list):
                        for action in actions:
                            # Handle different AgentScope/OpenAI formats
                            name = action.get('name') or action.get('function', {}).get('name')
                            if name == 'web_search_tool':
                                args = action.get('input') or action.get('function', {}).get('arguments')
                                if isinstance(args, str):
                                    try: args = json.loads(args)
                                    except (json.JSONDecodeError, ValueError): pass
                                if isinstance(args, dict) and 'query' in args:
                                    queries.append(args['query'])
                    elif isinstance(actions, dict):
                         # Single action
                         name = actions.get('name') or actions.get('function', {}).get('name')
                         if name == 'web_search_tool':
                                args = actions.get('input') or actions.get('function', {}).get('arguments')
                                if isinstance(args, str):
                                    try: args = json.loads(args)
                                    except (json.JSONDecodeError, ValueError): pass
                                if isinstance(args, dict) and 'query' in args:
                                    queries.append(args['query'])
                except (json.JSONDecodeError, ValueError, TypeError):
                    continue
        
        metrics = {
            'search_queries': queries,
            'query_count': len(queries),
            'distinct_query_count': len(set(queries))
        }
        
        # Simple query shift: percentage of consecutive queries that are different
        if len(queries) > 1:
            shifts = 0
            for i in range(len(queries) - 1):
                if queries[i] != queries[i+1]:
                    shifts += 1
            metrics['query_shift_ratio'] = shifts / (len(queries) - 1)
        else:
            metrics['query_shift_ratio'] = 0.0
            
        return metrics