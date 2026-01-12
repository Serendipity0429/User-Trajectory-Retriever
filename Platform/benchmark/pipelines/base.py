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
    TraceFormatter, SimpleMsg, PROMPTS, clear_trial_cache,
    extract_session_metrics
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
REDIS_PREFIX_VANILLA_AGENT = PipelinePrefix.VANILLA_AGENT
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
    # Timeout for LLM API calls (60 seconds)
    LLM_TIMEOUT = 60.0

    def __init__(self, base_url, api_key, model, pipeline_id=None, dataset_id=None):
        self.client = openai.OpenAI(base_url=base_url, api_key=api_key, timeout=self.LLM_TIMEOUT)
        self.model = model
        self.pipeline_id = pipeline_id
        self.dataset_id = dataset_id
        self.redis_prefix = REDIS_PREFIX_ACTIVE
        self.llm_settings = BenchmarkSettings.get_effective_settings()

        # Initialize judge client (uses same base_url/api_key but potentially different model)
        self.judge_client = self.client  # Same client, different model
        self.judge_model = self.llm_settings.llm_judge_model or model  # Fallback to generation model

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
        Returns: (parsed_answer, full_response, usage)

        Usage dict contains: input_tokens, output_tokens, total_tokens (or None if unavailable)
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

                # Extract token usage from response
                usage = None
                if hasattr(response, 'usage') and response.usage:
                    usage = {
                        "input_tokens": getattr(response.usage, 'prompt_tokens', 0),
                        "output_tokens": getattr(response.usage, 'completion_tokens', 0),
                        "total_tokens": getattr(response.usage, 'total_tokens', 0),
                    }

                if should_extract:
                    answer = extract_final_answer(full_response)
                else:
                    answer = full_response

                return answer, full_response, usage

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
        Sends messages to LLM and yields (full_response, usage) tuples as response grows.

        Usage is None during streaming and populated in the final yield when available.
        Callers should handle: for response, usage in self.get_llm_response_stream(...)
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
            "stream": True,
            "stream_options": {"include_usage": True}  # Request usage in stream
        }
        if max_tokens:
            kwargs['max_tokens'] = max_tokens

        full_response = ""
        usage = None
        try:
            response = self.client.chat.completions.create(**kwargs)
            for chunk in response:
                # Check for usage in chunk (typically in final chunk with stream_options)
                if hasattr(chunk, 'usage') and chunk.usage:
                    usage = {
                        "input_tokens": getattr(chunk.usage, 'prompt_tokens', 0),
                        "output_tokens": getattr(chunk.usage, 'completion_tokens', 0),
                        "total_tokens": getattr(chunk.usage, 'total_tokens', 0),
                    }
                if not chunk.choices:
                    continue
                content = chunk.choices[0].delta.content
                if content:
                    full_response += content
                    yield full_response, None  # Yield tuple during streaming
            # Final yield with usage (if we have content)
            if full_response:
                yield full_response, usage
        except Exception as e:
            print_debug(f"LLM API stream failed: {e}")
            raise e
    
    async def run(self):
        raise NotImplementedError("Subclasses must implement the 'run' method.")
        
    def get_settings_snapshot(self):
        """
        Returns the settings snapshot with LLM settings and pipeline-specific settings.
        Uses hook pattern: subclasses override _get_pipeline_settings() to add their settings.
        """
        snapshot = {
            'llm': {
                'llm_base_url': self.llm_settings.llm_base_url,
                'llm_model': self.llm_settings.llm_model,
                'llm_judge_model': getattr(self.llm_settings, 'llm_judge_model', '') or self.llm_settings.llm_model,
                'max_retries': getattr(self.llm_settings, 'max_retries', 3),
                'allow_reasoning': getattr(self.llm_settings, 'allow_reasoning', False),
                'temperature': getattr(self.llm_settings, 'temperature', 0.0),
                'top_p': getattr(self.llm_settings, 'top_p', 1.0),
                'max_tokens': getattr(self.llm_settings, 'max_tokens', None),
                'llm_api_key': self.llm_settings.llm_api_key
            }
        }
        # Hook: let subclasses add pipeline-specific settings
        pipeline_settings = self._get_pipeline_settings()
        if pipeline_settings:
            snapshot.update(pipeline_settings)
        return snapshot

    def _get_pipeline_settings(self):
        """
        Hook for subclasses to provide pipeline-specific settings.
        Override this to add settings like 'search', 'agent', 'pipeline_type', etc.
        Returns a dict to merge into the settings snapshot, or None.
        """
        return None

    def _accumulate_usage(self, existing_usage, new_usage, purpose=None):
        """
        Accumulate token usage from multiple LLM calls within a trial.

        Args:
            existing_usage: Current accumulated usage dict or None
            new_usage: New usage dict from an LLM call
            purpose: Optional label for the call (e.g., 'query_generation', 'answer_synthesis')

        Returns:
            Updated usage dict with accumulated totals
        """
        if not existing_usage:
            existing_usage = {
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "call_count": 0,
                "calls": []
            }

        if new_usage:
            existing_usage["input_tokens"] += new_usage.get("input_tokens", 0)
            existing_usage["output_tokens"] += new_usage.get("output_tokens", 0)
            existing_usage["total_tokens"] += new_usage.get("total_tokens", 0)
            existing_usage["call_count"] += 1

            call_detail = {**new_usage}
            if purpose:
                call_detail["purpose"] = purpose
            existing_usage["calls"].append(call_detail)

        return existing_usage


class BaseMultiTurnPipeline(BasePipeline):
    def __init__(self, base_url, api_key, model, max_retries, pipeline_id=None, dataset_id=None, group_id=None):
        super().__init__(base_url, api_key, model, pipeline_id, dataset_id)
        self.max_retries = max_retries
        self.redis_prefix = REDIS_PREFIX_MULTI_TURN
        self.group_id = group_id

    def create_session(self, settings, question_text, ground_truths, group):
        raise NotImplementedError("Subclasses must implement create_session")

    def create_trial(self, session, trial_number):
        """
        Creates a trial for the given session. This is identical across all pipelines.
        """
        trial = MultiTurnTrial.objects.create(
            session=session,
            trial_number=trial_number,
            status='processing'
        )
        # Clear any stale Redis cache for this trial ID (prevents data leakage from reused IDs)
        clear_trial_cache(trial.id)
        return trial
    
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
                # Clean up stalled/incomplete trials
                session.trials.exclude(status='completed').delete()
                # Continue from next trial after completed ones
                completed_count = session.trials.filter(status='completed').count()
                trial_number = completed_count + 1
            else:
                session = self.create_session(self.llm_settings, question_text, ground_truths, group)
                trial_number = 1
                completed_count = 0

            yield {
                'is_meta': True,
                'type': 'session_created',
                'session_id': session.id,
                'question': question_text,
                'group_id': group.id,
                'group_name': group.name
            }

            is_session_completed = False
            final_is_correct_llm = False
            final_answer = ""
            final_is_correct_llm_rule = False
            session_had_error = False

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
                    # TrialGuard already marked the trial as 'error' and saved partial trace
                    # Yield error event and abandon session, move to next question
                    print_debug(f"Trial {trial_number} failed with error: {e}")
                    yield {
                        'is_meta': True,
                        'type': 'trial_error',
                        'session_id': session.id,
                        'trial_id': trial.id,
                        'trial_number': trial_number,
                        'error': str(e),
                        'group_id': group.id
                    }
                    # Mark that session had an error (don't mark as completed)
                    session_had_error = True
                    break

                # run_single_turn handles saving the trial

                yield {
                    'is_meta': True,
                    'type': 'trial_completed',
                    'session_id': session.id,
                    'trial_number': trial_number,
                    'is_correct_llm': is_correct_llm,
                    'is_correct_rule': trial.is_correct_rule,
                    'answer': parsed_answer,
                    'group_id': group.id
                }

                final_answer = parsed_answer
                final_is_correct_llm = is_correct_llm
                final_is_correct_llm_rule = trial.is_correct_rule

                if is_correct_llm:
                    is_session_completed = True
                else:
                    trial_number += 1

            # Determine why the loop exited
            pipeline_stopped = not self.check_active()
            total_trials = session.trials.filter(status='completed').count()

            if session_had_error:
                # Error during trial - don't mark completed, yield error summary
                yield {
                    'question': question_text, 'is_correct_llm': False, 'is_correct_rule': False,
                    'trials': total_trials, 'session_id': session.id, 'final_answer': None,
                    'ground_truths': ground_truths, 'max_retries': self.max_retries,
                    'group_name': group.name, 'group_id': group.id, 'session_error': True
                }
            elif pipeline_stopped:
                # Pipeline stopped mid-session - don't mark completed, will be resumed later
                pass
            else:
                # Success or exhausted retries - mark completed
                session.is_completed = True
                session.save()

                # Reload session with prefetched trials to ensure fresh data for metrics
                # This is critical: session.refresh_from_db() does NOT refresh related objects
                fresh_session = MultiTurnSession.objects.prefetch_related('trials').get(pk=session.id)

                # Extract full session metrics for live dashboard display
                enriched = extract_session_metrics(fresh_session)
                enriched.update({
                    'max_retries': self.max_retries,
                    'group_name': group.name,
                    'group_id': group.id
                })
                yield enriched

        except Exception as e:
            yield {'error': str(e), 'question': question_text, 'session_id': session.id if 'session' in locals() else None}

    def run(self):
        completed_questions = set()
        incomplete_sessions = []

        if self.group_id:
            try:
                group = MultiTurnRun.objects.get(pk=self.group_id)

                # Collect incomplete sessions + fix any incorrectly completed ones
                incomplete_sessions = list(group.sessions.filter(is_completed=False).prefetch_related('trials'))

                for session in group.sessions.filter(is_completed=True).prefetch_related('trials'):
                    completed_trials = list(session.trials.filter(status='completed'))
                    has_success = any(t.is_correct_llm for t in completed_trials)
                    if not has_success and len(completed_trials) < self.max_retries:
                        session.is_completed = False
                        session.save()
                        incomplete_sessions.append(session)
                        print_debug(f"Reset incorrectly completed session #{session.id} ({len(completed_trials)} trials, no success)")

                # Identify truly completed questions (succeeded or exhausted retries)
                completed_questions = set(
                    s.question for s in group.sessions.filter(is_completed=True)
                )

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

            # PHASE 1: Resume ALL incomplete sessions first
            for session in incomplete_sessions:
                if not self.check_active():
                    break

                # Add to completed set so we don't process again in phase 2
                completed_questions.add(session.question)

                yield from self._process_single_session(
                    group,
                    session.question,
                    session.ground_truths,
                    existing_session=session
                )

            # PHASE 2: Process new questions from dataset
            for data in questions_iterator:
                if not self.check_active():
                    break

                question_text = data['question']

                # Skip if already completed or processed in phase 1
                if question_text in completed_questions:
                    continue

                ground_truths = data.get('ground_truths', [])

                yield from self._process_single_session(group, question_text, ground_truths, existing_session=None)
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

            def update_redis_trace(current_full_response, is_streaming=True):
                temp_trace_msgs = static_trace_msgs + [SimpleMsg("assistant", current_full_response)]
                trace_data, _ = TraceFormatter.serialize(temp_trace_msgs)
                # Mark last step as streaming for frontend optimization
                if is_streaming and trace_data:
                    trace_data[-1]['is_streaming'] = True
                redis_client.set(RedisKeys.trial_trace(trial.id), json.dumps(trace_data), ex=RedisKeys.DEFAULT_TTL)

            full_response = ""
            trial_usage = None
            # 1. Stream the response and update Redis periodically
            chunk_count = 0
            for partial_response, usage in self.get_llm_response_stream(messages):
                full_response = partial_response
                if usage:  # Usage is provided in final yield
                    trial_usage = self._accumulate_usage(trial_usage, usage, "generation")
                chunk_count += 1
                if chunk_count % 5 == 0:  # Update every 5 chunks to reduce overhead
                    update_redis_trace(full_response, is_streaming=True)

            # Final update - mark as not streaming
            update_redis_trace(full_response, is_streaming=False)
            
            # Extract final answer
            if allow_reasoning:
                answer = extract_final_answer(full_response)
            else:
                answer = full_response

            # Logic for checking answer (uses judge client/model, not generation model)
            is_correct_llm = check_answer_llm(session.question, session.ground_truths, answer, client=self.judge_client, model=self.judge_model)
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
            # Store system prompt separately for database fallback when Redis expires
            if messages and messages[0].get('role') == 'system':
                trial.log['system_prompt'] = messages[0].get('content', '')
            # Store token usage
            if trial_usage:
                trial.log['token_usage'] = trial_usage
            trial.status = 'completed'
            trial.save()

            # Cache completion status in Redis for efficient polling (parse trace for UI)
            try:
                trace, _ = TraceFormatter.serialize([SimpleMsg(m["role"], m["content"]) for m in trial_messages])

                # Ensure system prompt is at top of trace
                if not trace or trace[0].get('role') != 'system':
                    # Get system prompt from messages or construct it
                    system_prompt = None
                    if messages and messages[0].get('role') == 'system':
                        system_prompt = messages[0].get('content', '')
                    if system_prompt:
                        system_prompt_step = {"role": "system", "content": system_prompt, "step_type": "text"}
                        trace = [system_prompt_step] + trace

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


class _AsyncNullContext:
    """Async null context manager for non-ReMe memories."""
    async def __aenter__(self):
        return None
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None


class BaseAgentPipeline(BaseMultiTurnPipeline):
    """
    Base class for Agent pipelines (Vanilla and Browser) using the Template Method pattern.
    It centralizes the heavy lifting of async session management and state persistence,
    allowing subclasses to focus purely on agent initialization and execution.
    """

    # Reference to long-term memory, set by subclasses in _init_agent()
    long_term_memory = None

    def _get_pipeline_settings(self):
        """
        Returns agent-specific settings. Subclasses should call super() and extend.
        """
        settings = BenchmarkSettings.get_effective_settings()
        base_settings = {
            'agent': {
                'model_name': self._get_agent_model_name(),
                'memory_type': settings.memory_type
            }
        }
        # Add pipeline_type from subclass hook
        pipeline_type = self._get_pipeline_type()
        if pipeline_type:
            base_settings['pipeline_type'] = pipeline_type
        return base_settings

    def _get_agent_model_name(self):
        """Hook for subclasses to provide the agent model name."""
        if hasattr(self, 'agent_model') and self.agent_model and hasattr(self.agent_model, 'model_name'):
            return self.agent_model.model_name
        return 'unknown'

    def _get_pipeline_type(self):
        """Hook for subclasses to provide their pipeline type string."""
        return None

    def _get_memory_context(self):
        """Returns async context manager for long-term memory (ReMe needs it, others don't)."""
        try:
            from agentscope.memory import ReMePersonalLongTermMemory
            if ReMePersonalLongTermMemory and isinstance(self.long_term_memory, ReMePersonalLongTermMemory):
                return self.long_term_memory
        except ImportError:
            pass
        return _AsyncNullContext()

    def _serialize_trace(self, trace_msgs):
        return TraceFormatter.serialize(trace_msgs)

    def _extract_search_queries_from_trace(self, trace_data):
        """
        Extract search queries from agent trace data.

        Looks for web_search_tool actions in the trace and extracts the query parameters.
        Returns a list of search query strings.
        """
        queries = []
        if not trace_data:
            return queries

        for step in trace_data:
            # Look for action steps that contain web_search_tool calls
            if step.get('step_type') == 'action':
                content = step.get('content', '')
                if isinstance(content, str) and 'web_search_tool' in content:
                    try:
                        # Try to parse as JSON to extract the query
                        import json
                        data = json.loads(content)
                        # Handle both list format (tool_calls) and dict format (single tool)
                        if isinstance(data, list):
                            for item in data:
                                if item.get('name') == 'web_search_tool':
                                    query = self._extract_query_from_tool_call(item)
                                    if query:
                                        queries.append(query)
                        elif isinstance(data, dict):
                            if data.get('name') == 'web_search_tool':
                                query = self._extract_query_from_tool_call(data)
                                if query:
                                    queries.append(query)
                    except (json.JSONDecodeError, TypeError):
                        pass
        return queries

    def _extract_query_from_tool_call(self, tool_call):
        """Extract query string from a web_search_tool tool call dict."""
        # Handle different input formats
        input_data = tool_call.get('input') or tool_call.get('arguments') or tool_call.get('function', {}).get('arguments')
        if isinstance(input_data, str):
            try:
                import json
                input_data = json.loads(input_data)
            except (json.JSONDecodeError, TypeError):
                return input_data  # Might be the query string directly
        if isinstance(input_data, dict):
            return input_data.get('query')
        return None

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

    async def _on_session_start(self, session):
        """Hook called when a session starts. Override in subclasses for setup."""
        pass

    async def _on_session_end(self, session):
        """Hook called when a session ends. Override in subclasses for cleanup."""
        pass

    async def _process_single_session_async(self, group, question_text, ground_truths, existing_session=None):
        """
        Orchestrates the lifecycle of a single question across multiple trials.
        Handles retry logic and session-level metadata events for the UI.
        """
        try:
            if existing_session:
                session = existing_session
                # Clean up stalled/incomplete trials
                def cleanup():
                    session.trials.exclude(status='completed').delete()
                    return session.trials.filter(status='completed').count()
                completed_count = await sync_to_async(cleanup)()
                trial_number = completed_count + 1
            else:
                session = await sync_to_async(self.create_session)(self.llm_settings, question_text, ground_truths, group)
                trial_number = 1

            # Session lifecycle: setup resources (e.g., browser instance)
            await self._on_session_start(session)

            is_session_completed = False
            final_is_correct_llm = False
            final_answer = ""
            final_is_correct_llm_rule = False
            session_had_error = False

            try:
                yield {
                    'is_meta': True, 'type': 'session_created', 'session_id': session.id,
                    'question': question_text, 'group_id': group.id, 'group_name': group.name
                }

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
                        # AsyncTrialGuard already marked the trial as 'error' and saved partial trace
                        # Yield error event and abandon session, move to next question
                        print_debug(f"Trial {trial_number} failed with error: {e}")
                        yield {
                            'is_meta': True, 'type': 'trial_error', 'session_id': session.id,
                            'trial_id': trial.id, 'trial_number': trial_number,
                            'error': str(e), 'group_id': group.id
                        }
                        # Mark that session had an error (don't mark as completed)
                        session_had_error = True
                        break

                    yield {
                        'is_meta': True, 'type': 'trial_completed', 'session_id': session.id,
                        'trial_number': trial_number, 'is_correct_llm': is_correct_llm,
                        'is_correct_rule': trial.is_correct_rule, 'answer': parsed_answer,
                        'group_id': group.id
                    }

                    final_answer = parsed_answer
                    final_is_correct_llm = is_correct_llm
                    final_is_correct_llm_rule = trial.is_correct_rule
                    if is_correct_llm: is_session_completed = True
                    else: trial_number += 1

                # Determine why the loop exited
                pipeline_stopped = not await sync_to_async(self.check_active)()
                total_trials = await sync_to_async(lambda: session.trials.filter(status='completed').count())()

                if session_had_error:
                    # Error during trial - don't mark completed, yield error summary
                    yield {
                        'question': question_text, 'is_correct_llm': False, 'is_correct_rule': False,
                        'trials': total_trials, 'session_id': session.id, 'final_answer': None,
                        'ground_truths': ground_truths, 'max_retries': self.max_retries,
                        'group_name': group.name, 'group_id': group.id, 'session_error': True
                    }
                elif pipeline_stopped:
                    # Pipeline stopped mid-session - don't mark completed, will be resumed later
                    pass
                else:
                    # Success or exhausted retries - mark completed
                    session.is_completed = True
                    await sync_to_async(session.save)()

                    # Reload session with prefetched trials to ensure fresh data for metrics
                    # This is critical: session.refresh_from_db() does NOT refresh related objects
                    def reload_session_with_trials():
                        return MultiTurnSession.objects.prefetch_related('trials').get(pk=session.id)
                    fresh_session = await sync_to_async(reload_session_with_trials)()

                    # Extract full session metrics for live dashboard display
                    enriched = await sync_to_async(extract_session_metrics)(fresh_session)
                    enriched.update({
                        'max_retries': self.max_retries,
                        'group_name': group.name,
                        'group_id': group.id
                    })
                    yield enriched
            finally:
                # Session lifecycle: cleanup resources (e.g., browser instance)
                await self._on_session_end(session)
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
        incomplete_sessions = []

        if self.group_id:
            try:
                group = await sync_to_async(MultiTurnRun.objects.get)(pk=self.group_id)

                def collect_sessions_to_process():
                    # Collect incomplete sessions + fix any incorrectly completed ones
                    sessions_to_process = list(group.sessions.filter(is_completed=False).prefetch_related('trials'))

                    for session in group.sessions.filter(is_completed=True).prefetch_related('trials'):
                        completed_trials = list(session.trials.filter(status='completed'))
                        has_success = any(t.is_correct_llm for t in completed_trials)
                        if not has_success and len(completed_trials) < self.max_retries:
                            session.is_completed = False
                            session.save()
                            sessions_to_process.append(session)
                            print_debug(f"Reset incorrectly completed session #{session.id} ({len(completed_trials)} trials, no success)")

                    completed_qs = set(s.question for s in group.sessions.filter(is_completed=True))
                    return sessions_to_process, completed_qs

                incomplete_sessions, completed_questions = await sync_to_async(collect_sessions_to_process)()
            except MultiTurnRun.DoesNotExist:
                 yield {'error': f"Group with ID {self.group_id} not found."}
                 return
        else:
            group = await sync_to_async(create_run_obj)()

        # Set run_id for memory isolation (used by agent pipelines)
        if hasattr(self, '_current_run_id'):
            self._current_run_id = group.id

        file_path = await sync_to_async(self.get_questions_file_path)()
        total_questions = await sync_to_async(count_questions_in_file)(file_path)
        yield {'is_meta': True, 'type': 'total_count', 'count': total_questions}

        # PHASE 1: Resume ALL incomplete sessions first
        for session in incomplete_sessions:
            if not await sync_to_async(self.check_active)():
                break

            # Add to completed set so we don't process again in phase 2
            completed_questions.add(session.question)

            async for event in self._process_single_session_async(
                group,
                session.question,
                session.ground_truths,
                existing_session=session
            ):
                yield event

        # PHASE 2: Process new questions from dataset
        from .agent import question_file_iterator
        questions_iterator = question_file_iterator(file_path)

        while True:
            if not await sync_to_async(self.check_active)():
                break
            try:
                data = await sync_to_async(next)(questions_iterator)
            except StopIteration:
                break

            question_text = data['question']

            # Skip if already completed or processed in phase 1
            if question_text in completed_questions:
                continue

            ground_truths = data.get('ground_truths', [])

            async for event in self._process_single_session_async(group, question_text, ground_truths, existing_session=None):
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
                # Retry logic: ensure agent is alive
                if not hasattr(self, 'active_agent') or not self.active_agent:
                    self.active_agent = await self._init_agent()
                    await self._populate_agent_memory(session, self.active_agent)

                # Check if we should clear short-term memory (when long-term memory is enabled)
                if self._should_clear_memory_on_retry():
                    # Clear short-term memory - agent should use long-term memory for context
                    await self._clear_short_term_memory()
                    turn_start_index = 0
                else:
                    try:
                        current_mem = await self.active_agent.memory.get_memory()
                        turn_start_index = len(current_mem) if current_mem else 0
                    except: turn_start_index = 0

                # Use shared retry prompt for all baselines
                last_trial = await sync_to_async(lambda: session.trials.filter(status='completed').last())()
                feedback = last_trial.feedback if last_trial else "Incorrect"
                retry_prompt = self._get_retry_prompt_key()
                current_msg = Msg(name="User", role="user", content=PROMPTS[retry_prompt].format(question=session.question))

            if not hasattr(self, 'active_agent') or not self.active_agent:
                self.active_agent = await self._init_agent()

            # The update hook allows real-time trace streaming to the frontend.
            # Use asyncio.create_task to properly schedule the async function
            def create_update_hook(t, idx):
                def hook():
                    try:
                        loop = asyncio.get_running_loop()
                        asyncio.ensure_future(self._update_trace(t, idx), loop=loop)
                    except RuntimeError:
                        # No running loop - create task in default loop
                        asyncio.create_task(self._update_trace(t, idx))
                return hook
            self.active_agent.memory._update_hook = create_update_hook(trial, turn_start_index)

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
                    system_prompt_step = {"role": "system", "content": self._get_actual_system_prompt(), "step_type": "text"}
                    trace_data = [system_prompt_step] + trace_data

                # 4. Save - pass raw messages and parsed trace
                answer, is_correct_llm = await sync_to_async(self.save_trial_result)(
                    session, trial, answer, relevant_trace_msgs, trace_data
                )
            except Exception as e:
                # Save partial trace from agent memory before error propagates
                # This ensures we have the trace even if Redis cache is empty/stale
                try:
                    if hasattr(self, 'active_agent') and self.active_agent and hasattr(self.active_agent, 'memory'):
                        trace_msgs = await self.active_agent.memory.get_memory()
                        relevant_msgs = trace_msgs[turn_start_index:] if len(trace_msgs) > turn_start_index else []
                        if relevant_msgs:
                            trace_data, _ = self._serialize_trace(relevant_msgs)
                            # Add system prompt to trace
                            if not trace_data or trace_data[0].get('role') != 'system':
                                system_prompt_step = {"role": "system", "content": self._get_actual_system_prompt(), "step_type": "text"}
                                trace_data = [system_prompt_step] + trace_data
                            # Save trace to Redis so AsyncTrialGuard can pick it up
                            key = RedisKeys.trial_trace(trial.id)
                            await asyncio.to_thread(lambda: redis_client.set(key, json.dumps(trace_data), ex=RedisKeys.DEFAULT_TTL))
                            print_debug(f"Saved {len(trace_data)} trace steps before error propagation")
                except Exception as trace_err:
                    print_debug(f"Failed to save partial trace on error: {trace_err}")
                raise  # Re-raise the original exception
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

    def _get_actual_system_prompt(self):
        """Get the actual system prompt used by this pipeline.

        Subclasses can override this to return modified prompts (e.g., with memory tools).
        Default implementation returns the base prompt from PROMPTS dict.
        """
        return PROMPTS[self._get_system_prompt_key()]

    def _should_clear_memory_on_retry(self):
        """Whether to clear short-term memory on retry trials.

        When True, short-term memory is cleared and agent must use long-term memory.
        Default is False (naive behavior - inherit full context).
        Subclasses with long-term memory should override to return True.
        """
        return False

    async def _clear_short_term_memory(self):
        """Clear the agent's short-term memory.

        Called before retry trials when long-term memory is enabled.
        """
        if hasattr(self, 'active_agent') and self.active_agent and hasattr(self.active_agent, 'memory'):
            try:
                # Clear memory - InMemoryMemory stores messages in a list
                if hasattr(self.active_agent.memory, 'clear'):
                    await self.active_agent.memory.clear()
                elif hasattr(self.active_agent.memory, '_messages'):
                    self.active_agent.memory._messages = []
                print_debug("Cleared short-term memory for retry trial")
            except Exception as e:
                print_debug(f"Failed to clear short-term memory: {e}")
    
    def _parse_answer(self, response_msg):
        """Extracts text answer from multi-modal or structured responses."""
        raw_content = response_msg.content
        if isinstance(raw_content, list):
            try:
                texts = [c.get('text', '') if isinstance(c, dict) else str(c) for c in raw_content]
                return "".join(texts)
            except: return json.dumps(raw_content)
        return str(raw_content) if raw_content is not None else ""

    async def _update_trace(self, trial, turn_start_index):
        """Updates the real-time trace in Redis for frontend rendering."""
        try:
            msgs = await self.active_agent.memory.get_memory()
            relevant_msgs = msgs[turn_start_index:] if len(msgs) > turn_start_index else []
            trace_data, _ = self._serialize_trace(relevant_msgs)
            if not trace_data or trace_data[0].get('role') != 'system':
                system_prompt_step = {"role": "system", "content": self._get_actual_system_prompt(), "step_type": "text"}
                trace_data = [system_prompt_step] + trace_data
            # Mark last step as streaming for frontend optimization
            if trace_data:
                trace_data[-1]['is_streaming'] = True
            key = RedisKeys.trial_trace(trial.id)
            await asyncio.to_thread(lambda: redis_client.set(key, json.dumps(trace_data), ex=RedisKeys.DEFAULT_TTL))
        except Exception as e: print_debug(f"Trace update failed: {e}")

    def save_trial_result(self, session, trial, answer, messages, trace_data):
        """
        Saves the trial result to DB and caches status in Redis.
        Args:
            messages: Raw Msg objects (list) - the authentic agent context
            trace_data: Parsed trace for UI rendering
        Returns: (answer, is_correct_llm)
        """
        # Uses judge client/model, not generation model
        is_correct_llm = check_answer_llm(session.question, session.ground_truths, answer, client=self.judge_client, model=self.judge_model)
        is_correct_rule = check_answer_rule(session.question, session.ground_truths, answer)

        trial.answer = answer
        trial.is_correct_llm = is_correct_llm
        trial.is_correct_rule = is_correct_rule
        trial.feedback = "Correct" if is_correct_llm else "Incorrect"

        # Store raw messages (authentic agent context)
        trial.log = trial.log or {}
        trial.log['messages'] = [m.to_dict() if hasattr(m, 'to_dict') else m for m in messages]

        # Store system prompt separately for database fallback when Redis expires
        trial.log['system_prompt'] = self._get_actual_system_prompt()

        # Store baseline-specific metadata (e.g., memory operations for agent baselines)
        trial_meta = self._get_trial_meta(trial)
        if trial_meta:
            trial.log['meta'] = trial_meta

        # Extract and store token usage from agent's model wrapper
        if hasattr(self, 'active_agent') and hasattr(self.active_agent, '_usage_tracker'):
            usage = self.active_agent._usage_tracker.get_usage()
            if usage and usage.get('call_count', 0) > 0:
                trial.log['token_usage'] = usage
            # Reset tracker for next trial
            self.active_agent._usage_tracker.reset_usage()

        # Extract and store search queries from trace data (for agent pipelines)
        search_queries = self._extract_search_queries_from_trace(trace_data)
        if search_queries:
            trial.log['search_queries'] = search_queries

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
            }
            redis_client.set(RedisKeys.trial_status(trial.id), json.dumps(status_data), ex=RedisKeys.DEFAULT_TTL)
            # Cache trace separately for live UI rendering
            redis_client.set(RedisKeys.trial_trace(trial.id), json.dumps(trace_data), ex=RedisKeys.DEFAULT_TTL)
        except Exception as e:
            print_debug(f"Failed to cache agent trial status: {e}")

        return answer, is_correct_llm