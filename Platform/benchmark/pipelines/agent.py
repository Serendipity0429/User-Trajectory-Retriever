import json
import asyncio
import threading
from concurrent import futures
from datetime import datetime
from asgiref.sync import sync_to_async
from agentscope.message import Msg
from ..models import LLMSettings, SearchSettings, MultiTurnRun, MultiTurnSession, MultiTurnTrial, AgentSettings
from ..utils import print_debug, count_questions_in_file
from ..agent_utils import VanillaAgentFactory, BrowserAgentFactory
from ..mcp_manager import MCPManager
from .base import BaseAgentPipeline, REDIS_PREFIX_BROWSER_AGENT
from task_manager.utils import redis_client

class VanillaAgentPipeline(BaseAgentPipeline):
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
        agent_settings = AgentSettings.get_effective_settings()
        snapshot = super().get_settings_snapshot()
        snapshot['pipeline_type'] = 'vanilla_agent'
        snapshot['agent_config'] = {
            'model_name': self.agent_model.model_name if hasattr(self.agent_model, 'model_name') else 'unknown',
            'memory_type': agent_settings.memory_type
        }
        return snapshot

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

    async def _run_single_turn_async(self, session, trial):
        completed_trials = await sync_to_async(list)(
            session.trials.filter(trial_number__lt=trial.trial_number, status='completed').order_by('trial_number')
        )
        
        history_msgs = []
        if trial.trial_number > 1:
            history_msgs.append(Msg(name="User", role="user", content=f"Task: {session.question}"))
            for pt in completed_trials:
                if pt.answer:
                    history_msgs.append(Msg(name="Assistant", role="assistant", content=pt.full_response))
                history_msgs.append(Msg(name="User", role="user", content=f"Incorrect. Feedback: {pt.feedback}"))
            
            last_pt = completed_trials[-1]
            current_msg = Msg(name="User", role="user", content=f"Your previous attempt was incorrect. Feedback: {last_pt.feedback}. Please re-evaluate the task and try again.")
        else:
            current_msg = Msg(name="User", role="user", content=f"Task: {session.question}")

        initial_history_len = len(history_msgs)

        def on_memory_update(msgs):
            try:
                relevant_msgs = msgs[initial_history_len:] if len(msgs) > initial_history_len else []
                trace_data, _ = self._serialize_trace(relevant_msgs)
                key = f"trial_trace:{trial.id}"
                
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(asyncio.to_thread(redis_client.set, key, json.dumps(trace_data), ex=3600))
                except RuntimeError:
                     threading.Thread(target=redis_client.set, args=(key, json.dumps(trace_data)), kwargs={'ex': 3600}).start()
            except Exception as e:
                print_debug(f"Redis update failed: {e}")

        # Create Agent
        agent = await sync_to_async(VanillaAgentFactory.create_agent)(self.agent_model, update_callback=on_memory_update)
        
        # Inject History
        if history_msgs:
            await agent.memory.add(history_msgs)

        # Run Agent
        response_msg = await agent(current_msg)
        
        # Process Response
        trace_msgs = await agent.memory.get_memory()
        
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
                 "name": "Vanilla Agent Debug", 
                 "content": answer
             }])

        # Save Result
        answer, is_correct = await sync_to_async(self.save_trial_result)(session, trial, answer, full_response)
        
        return answer, is_correct, []

    def run_single_turn(self, session, trial):
        return asyncio.run(self._run_single_turn_async(session, trial))


# Helper for reading questions file safely in chunks/lines without DB access
def question_file_iterator(file_path):
    if not file_path:
        return
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                if 'answer' in data and 'ground_truths' not in data:
                    data['ground_truths'] = data['answer']
                yield data
            except json.JSONDecodeError:
                continue

class BrowserAgentPipeline(BaseAgentPipeline):
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
        self.mcp_manager = MCPManager() # Decoupled MCP Manager
        self.mcp_client = None # Set after connection
        self.redis_prefix = REDIS_PREFIX_BROWSER_AGENT

    @classmethod
    async def create(cls, base_url, api_key, model, max_retries, pipeline_id=None, dataset_id=None):
        try:
            print_debug("BrowserAgentPipeline: Creating instance (lightweight)...")
            instance = await sync_to_async(cls)(base_url, api_key, model, max_retries, pipeline_id, dataset_id)
            return instance
        except Exception as e:
            print_debug(f"BrowserAgentPipeline: Error in create: {e}")
            raise e

    def __str__(self):
        return "Browser Agent Pipeline"

    def get_settings_snapshot(self):
        agent_settings = AgentSettings.get_effective_settings()
        snapshot = super().get_settings_snapshot()
        snapshot['pipeline_type'] = 'browser_agent'
        snapshot['agent_config'] = {
            'model_name': self.agent_model.model_name if hasattr(self, 'agent_model') and self.agent_model and hasattr(self.agent_model, 'model_name') else 'unknown',
            'memory_type': agent_settings.memory_type
        }
        return snapshot

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
        await self.mcp_manager.disconnect()
        self.mcp_client = None

    async def run(self):
        yield {'is_meta': True, 'type': 'info', 'message': 'Pipeline started. Initializing AgentScope...'}
        await asyncio.sleep(0.1) # Yield control to ensure message flushes
        
        try:
            # Lazy Init of AgentScope here to allow feedback
            if not self.agent_model or not self.agent_toolkit:
                 # Run in separate thread to avoid blocking event loop
                 self.agent_model, self.agent_toolkit = await sync_to_async(BrowserAgentFactory.init_agentscope, thread_sensitive=False)(self.temp_settings)
                 yield {'is_meta': True, 'type': 'info', 'message': 'AgentScope initialized.'}
                 await asyncio.sleep(0.1)
        except Exception as e:
            print_debug(f"BrowserAgentPipeline: Error initializing AgentScope: {e}")
            yield {'error': f"Failed to initialize AgentScope: {e}"}
            return

        def create_run_obj():
            name = f"{str(self)}- {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}" 
            snapshot = self.get_settings_snapshot()
            return MultiTurnRun.objects.create(name=name, settings_snapshot=snapshot)

        try:
            group = await sync_to_async(create_run_obj)()
            yield {'is_meta': True, 'type': 'info', 'message': f'Run object created: {group.name}'}
        except Exception as e:
             print_debug(f"BrowserAgentPipeline: Error creating run object: {e}")
             yield {'error': f"Failed to initialize run: {e}"}
             return
        
        file_path = None
        total_questions = 0
        
        try:
            yield {'is_meta': True, 'type': 'info', 'message': 'Resolving questions file...'}
            # 1. Resolve File Path (DB Access)
            file_path = await sync_to_async(self.get_questions_file_path)()
            print_debug(f"BrowserAgentPipeline: Using questions file at {file_path}")
            
            # 2. Get Total Count (File I/O)
            total_questions = await sync_to_async(count_questions_in_file)(file_path)
            print_debug(f"BrowserAgentPipeline: Total questions: {total_questions}")
            yield {'is_meta': True, 'type': 'info', 'message': f'Loaded {total_questions} questions.'}

        except Exception as e:
            print_debug(f"BrowserAgentPipeline: Error initializing: {e}")
            yield {'error': str(e)}
            await sync_to_async(self.stop_token)()
            return

        yield {'is_meta': True, 'type': 'total_count', 'count': total_questions}
        
        # 3. Create Iterator (No DB Access)
        questions_iterator = question_file_iterator(file_path)
        
        count = 0
        try:
            yield {'is_meta': True, 'type': 'info', 'message': 'Starting execution loop...'}
            while True:
                if not await sync_to_async(self.check_active)():
                    yield {'is_meta': True, 'type': 'info', 'message': 'Pipeline stopped by user.'}
                    break
                
                try:
                    # Use sync_to_async(next) to fetch the next item from the file
                    # This runs the file reading in a thread
                    data = await sync_to_async(next)(questions_iterator)
                    count += 1
                except StopIteration:
                    yield {'is_meta': True, 'type': 'info', 'message': 'All questions processed.'}
                    break # Generator is exhausted
                except Exception as e:
                    print_debug(f"BrowserAgentPipeline: Error reading next question: {e}")
                    yield {'error': f"Error reading question: {e}"}
                    break

                question_text = data['question']
                ground_truths = data.get('ground_truths', [])
                
                yield {'is_meta': True, 'type': 'info', 'message': f'Processing question {count}/{total_questions}: {question_text[:30]}...'}

                async for event in self._process_single_session_async(group, question_text, ground_truths):
                    yield event
        except Exception as e:
            print_debug(f"BrowserAgentPipeline: Unexpected error in run loop: {e}")
            yield {'error': f"Unexpected pipeline error: {e}"}
        finally:
            await self.cleanup()
            await sync_to_async(self.stop_token)()

    async def run_single_turn_async(self, session, trial, auto_cleanup=False):
        # Lazy init for MCP client (handle loop changes or delayed init)
        if not self.mcp_client:
             self.mcp_client = await self.mcp_manager.connect(self.agent_toolkit)
        
        # NOTE: self.mcp_client might still be None if connection failed.
        # But we proceed, as the agent might still work with basic tools.

        # The agent_model, toolkit are already initialized in __init__
        
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
                
                # Use the running loop to schedule the Redis write in a thread pool
                # This avoids spawning a new thread for every update and doesn't block the loop
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(
                        asyncio.to_thread(redis_client.set, key, json.dumps(trace_data), ex=3600)
                    )
                except RuntimeError:
                     # Fallback if no loop is running (unlikely here)
                     threading.Thread(
                        target=redis_client.set, 
                        args=(key, json.dumps(trace_data)), 
                        kwargs={'ex': 3600},
                        daemon=True
                    ).start()
                
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

        # Async DB access for saving result using BaseAgentPipeline helper
        def save_result():
            # self.save_trial_result is inherited from BaseAgentPipeline
            return self.save_trial_result(session, trial, answer, full_response)

        answer, is_correct = await sync_to_async(save_result)()

        return answer, is_correct, []

    def run_single_turn(self, session, trial):
        # Auto-cleanup when running via sync wrapper (one-off execution)
        return asyncio.run(self.run_single_turn_async(session, trial, auto_cleanup=True))
