import json
import asyncio
import threading
from concurrent import futures
from datetime import datetime
from asgiref.sync import sync_to_async
from agentscope.message import Msg
try:
    from agentscope.memory import ReMePersonalLongTermMemory
except ImportError:
    ReMePersonalLongTermMemory = None
from ..models import BenchmarkSettings, MultiTurnRun, MultiTurnSession, MultiTurnTrial
from ..utils import (
    print_debug,
    VanillaAgentFactory, BrowserAgentFactory,
    clear_trial_cache
)
from ..utils.mcp_manager import ChromeDevToolsMCPManager
from .base import BaseAgentPipeline, REDIS_PREFIX_BROWSER_AGENT
import inspect


class _AsyncNullContext:
    """Async null context manager for non-ReMe memories."""
    async def __aenter__(self):
        return None
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None

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

class VanillaAgentPipeline(BaseAgentPipeline):
    def __init__(self, base_url, api_key, model, max_retries, pipeline_id=None, dataset_id=None, group_id=None):
        super().__init__(base_url, api_key, model, max_retries, pipeline_id, dataset_id, group_id)
        # Initialize AgentScope
        self.temp_settings = BenchmarkSettings(
            llm_base_url=base_url,
            llm_api_key=api_key,
            llm_model=model,
            temperature=0.0
        )
        self.agent_model = VanillaAgentFactory.init_agentscope(self.temp_settings)
        self.redis_prefix = f"vanilla_agent_pipeline_active"
        self.long_term_memory = None  # Will be set in _init_agent
        # Memory operation tracking for trial metadata
        self._last_retrieved_memories = None
        self._last_recorded_observations = None
        self._current_run_id = None  # Set when processing starts

    @classmethod
    async def create(cls, base_url, api_key, model, max_retries, pipeline_id=None, dataset_id=None, group_id=None):
        try:
            instance = await sync_to_async(cls)(base_url, api_key, model, max_retries, pipeline_id, dataset_id, group_id)
            return instance
        except Exception as e:
            print_debug(f"VanillaAgentPipeline: Error in create: {e}")
            raise e

    def __str__(self):
        return "Vanilla Agent Pipeline"

    def get_settings_snapshot(self):
        settings = BenchmarkSettings.get_effective_settings()
        snapshot = super().get_settings_snapshot()
        snapshot['pipeline_type'] = 'vanilla_agent'
        snapshot['agent'] = {
            'model_name': self.agent_model.model_name if hasattr(self.agent_model, 'model_name') else 'unknown',
            'memory_type': settings.memory_type
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
        trial = MultiTurnTrial.objects.create(
            session=session,
            trial_number=trial_number,
            status='processing'
        )
        # Clear any stale Redis cache for this trial ID (prevents data leakage from reused IDs)
        clear_trial_cache(trial.id)
        return trial

    # Hooks for BaseAgentPipeline template
    async def _init_agent(self):
        # Pass run_id for memory isolation (set by base pipeline before agent creation)
        agent, long_term_memory = await sync_to_async(VanillaAgentFactory.create_agent)(
            self.agent_model,
            run_id=self._current_run_id
        )
        self.long_term_memory = long_term_memory
        return agent

    def _get_memory_context(self):
        """Returns async context manager for long-term memory (ReMe needs it, others don't)."""
        if ReMePersonalLongTermMemory and isinstance(self.long_term_memory, ReMePersonalLongTermMemory):
            return self.long_term_memory
        return _AsyncNullContext()

    async def _retrieve_memories(self, msg):
        """Retrieve relevant memories before agent execution (static_control mode)."""
        if not self.long_term_memory:
            return None
        try:
            # Wrap in sync_to_async to avoid SQLite threading issues
            # Both Mem0 and ReMe have retrieve() method
            retrieve_func = sync_to_async(self.long_term_memory.retrieve, thread_sensitive=False)
            result = await retrieve_func(msg)
            return result
        except Exception as e:
            print_debug(f"Error retrieving from long-term memory: {e}")
            return None

    async def _record_findings(self, observations):
        """Record observations to long-term memory after agent execution (static_control mode)."""
        if not self.long_term_memory or not observations:
            return
        try:
            # Wrap in sync_to_async to avoid SQLite threading issues
            # Both Mem0 and ReMe have record() method
            record_func = sync_to_async(self.long_term_memory.record, thread_sensitive=False)
            await record_func(observations)
            print_debug(f"Recorded {len(observations)} observations to long-term memory")
        except Exception as e:
            print_debug(f"Error recording to long-term memory: {e}")

    async def _extract_observations(self):
        """Extract tool observations from agent's short-term memory for recording."""
        if not self.active_agent or not hasattr(self.active_agent, 'memory'):
            return []
        try:
            memory = self.active_agent.memory
            # Get all messages from short-term memory
            messages = memory.get_memory()
            if asyncio.iscoroutine(messages):
                messages = await messages

            # Filter for observation/tool result messages
            # These typically have role='assistant' with tool results or specific observation markers
            observations = []
            for m in messages:
                # Check for tool observations (search results, page content)
                role = getattr(m, 'role', None) or m.get('role', '') if isinstance(m, dict) else ''
                content = getattr(m, 'content', None) or m.get('content', '') if isinstance(m, dict) else str(m)

                # Record assistant messages that contain tool results (observations)
                if 'observation' in str(role).lower() or 'tool' in str(role).lower():
                    observations.append(m)
                # Also record messages with search results or page content
                elif content and any(marker in content.lower() for marker in ['search results', 'http://', 'https://']):
                    observations.append(m)

            return observations
        except Exception as e:
            print_debug(f"Error extracting observations: {e}")
            return []

    def _format_retrieved_context(self, retrieved):
        """Format retrieved memories for injection into the message."""
        if not retrieved:
            return ""
        if isinstance(retrieved, str):
            return retrieved
        if isinstance(retrieved, list):
            formatted = []
            for item in retrieved:
                if hasattr(item, 'content'):
                    formatted.append(str(item.content))
                elif isinstance(item, dict) and 'content' in item:
                    formatted.append(str(item['content']))
                else:
                    formatted.append(str(item))
            return "\n".join(formatted)
        return str(retrieved)

    async def _execute_agent(self, msg):
        """Execute agent with static long-term memory control."""
        # Reset tracking for this execution
        self._last_retrieved_memories = None
        self._last_recorded_observations = None

        async with self._get_memory_context():
            # 1. Retrieve relevant past findings before execution
            retrieved = await self._retrieve_memories(msg)

            # 2. Track and inject retrieved context
            effective_msg = msg
            if retrieved:
                context_text = self._format_retrieved_context(retrieved)
                if context_text.strip():
                    # Track for metadata
                    self._last_retrieved_memories = context_text
                    enhanced_content = f"{msg.content}\n\n[Relevant prior findings from memory:\n{context_text}]"
                    effective_msg = Msg(role=msg.role, content=enhanced_content, name=getattr(msg, 'name', None))
                    print_debug(f"Injected {len(context_text)} chars of retrieved context")

            # 3. Execute agent
            response = await self.active_agent(effective_msg)

            # 4. Record observations to long-term memory for future retrieval
            observations = await self._extract_observations()
            if observations:
                # Track for metadata (serialize observations)
                self._last_recorded_observations = [
                    m.to_dict() if hasattr(m, 'to_dict') else str(m) for m in observations
                ]
            await self._record_findings(observations)

            return response

    def _get_trial_meta(self, trial):
        """Return memory-related metadata for this trial."""
        meta = {}
        if self._last_retrieved_memories:
            meta['memory_retrieved'] = self._last_retrieved_memories
        if self._last_recorded_observations:
            meta['memory_recorded'] = self._last_recorded_observations
        if self.long_term_memory:
            meta['memory_type'] = type(self.long_term_memory).__name__
        return meta

    def _get_system_prompt_key(self):
        return "vanilla_agent_system_prompt"

    def _get_retry_prompt_key(self):
        return "shared_retry_request"


class BrowserAgentPipeline(BaseAgentPipeline):
    def __init__(self, base_url, api_key, model, max_retries, pipeline_id=None, dataset_id=None, group_id=None):
        super().__init__(base_url, api_key, model, max_retries, pipeline_id, dataset_id, group_id)
        self.temp_settings = BenchmarkSettings(
            llm_base_url=base_url,
            llm_api_key=api_key,
            llm_model=model,
            temperature=0.0 # Default for agent
        )
        # These are initialized per-session in _on_session_start
        self.agent_model = None
        self.agent_toolkit = None
        self.mcp_manager = None
        self.mcp_client = None
        self.redis_prefix = REDIS_PREFIX_BROWSER_AGENT
        self.long_term_memory = None  # Will be set in _init_agent
        # Memory operation tracking for trial metadata
        self._last_retrieved_memories = None
        self._last_recorded_observations = None
        self._current_run_id = None  # Set when processing starts

    @classmethod
    async def create(cls, base_url, api_key, model, max_retries, pipeline_id=None, dataset_id=None, group_id=None):
        try:
            print_debug("BrowserAgentPipeline: Creating instance (lightweight)...")
            instance = await sync_to_async(cls)(base_url, api_key, model, max_retries, pipeline_id, dataset_id, group_id)
            return instance
        except Exception as e:
            print_debug(f"BrowserAgentPipeline: Error in create: {e}")
            raise e

    def __str__(self):
        return "Browser Agent Pipeline"

    def get_settings_snapshot(self):
        settings = BenchmarkSettings.get_effective_settings()
        snapshot = super().get_settings_snapshot()
        snapshot['pipeline_type'] = 'browser_agent'
        snapshot['agent'] = {
            'model_name': self.agent_model.model_name if hasattr(self, 'agent_model') and self.agent_model and hasattr(self.agent_model, 'model_name') else 'unknown',
            'memory_type': settings.memory_type
        }
        return snapshot

    def create_session(self, settings, question_text, ground_truths, group):
        return MultiTurnSession.objects.create(
            question=question_text,
            ground_truths=ground_truths,
            run=group,
            run_tag=self.pipeline_id,
            pipeline_type='browser_agent'
        )

    def create_trial(self, session, trial_number):
        trial = MultiTurnTrial.objects.create(
            session=session,
            trial_number=trial_number,
            status='processing'
        )
        # Clear any stale Redis cache for this trial ID (prevents data leakage from reused IDs)
        clear_trial_cache(trial.id)
        return trial

    async def cleanup(self):
        """Final cleanup at end of pipeline run."""
        await self._disconnect_mcp()

    async def _on_session_start(self, session):
        """
        Initialize a fresh browser instance for each session.
        This ensures isolation between different questions.
        """
        print_debug(f"BrowserAgentPipeline: Starting session {session.id} with fresh browser instance")

        # Initialize fresh model and toolkit for this session
        self.agent_model, self.agent_toolkit = await sync_to_async(
            BrowserAgentFactory.init_agentscope, thread_sensitive=False
        )(self.temp_settings)

        # Create fresh MCP manager and connect
        self.mcp_manager = ChromeDevToolsMCPManager()
        self.mcp_client = await self.mcp_manager.connect(self.agent_toolkit)

        # Reset active agent so it gets recreated with new toolkit
        if hasattr(self, 'active_agent'):
            self.active_agent = None

    async def _on_session_end(self, session):
        """
        Clean up browser instance when session ends.
        """
        print_debug(f"BrowserAgentPipeline: Ending session {session.id}, disconnecting browser")
        await self._disconnect_mcp()

        # Reset agent state for next session
        self.active_agent = None
        self.agent_model = None
        self.agent_toolkit = None

    async def _disconnect_mcp(self):
        """Safely disconnect MCP client."""
        if self.mcp_manager:
            try:
                await self.mcp_manager.disconnect()
            except Exception as e:
                print_debug(f"Error disconnecting MCP: {e}")
            finally:
                self.mcp_manager = None
                self.mcp_client = None

    # Hooks for BaseAgentPipeline template
    async def _init_agent(self):
        # Model and toolkit should already be initialized in _on_session_start
        if not self.agent_model or not self.agent_toolkit:
            print_debug("Warning: Model/toolkit not initialized, initializing now")
            self.agent_model, self.agent_toolkit = await sync_to_async(
                BrowserAgentFactory.init_agentscope, thread_sensitive=False
            )(self.temp_settings)
            self.mcp_manager = ChromeDevToolsMCPManager()
            self.mcp_client = await self.mcp_manager.connect(self.agent_toolkit)

        # Pass run_id for memory isolation (set by base pipeline before agent creation)
        agent, long_term_memory = await BrowserAgentFactory.create_agent(
            self.agent_model,
            self.agent_toolkit,
            self.mcp_client,
            run_id=self._current_run_id
        )
        self.long_term_memory = long_term_memory
        return agent

    def _get_memory_context(self):
        """Returns async context manager for long-term memory (ReMe needs it, others don't)."""
        if ReMePersonalLongTermMemory and isinstance(self.long_term_memory, ReMePersonalLongTermMemory):
            return self.long_term_memory
        return _AsyncNullContext()

    async def _retrieve_memories(self, msg):
        """Retrieve relevant memories before agent execution (static_control mode)."""
        if not self.long_term_memory:
            return None
        try:
            # Wrap in sync_to_async to avoid SQLite threading issues
            retrieve_func = sync_to_async(self.long_term_memory.retrieve, thread_sensitive=False)
            result = await retrieve_func(msg)
            return result
        except Exception as e:
            print_debug(f"Error retrieving from long-term memory: {e}")
            return None

    async def _record_findings(self, observations):
        """Record observations to long-term memory after agent execution (static_control mode)."""
        if not self.long_term_memory or not observations:
            return
        try:
            # Wrap in sync_to_async to avoid SQLite threading issues
            record_func = sync_to_async(self.long_term_memory.record, thread_sensitive=False)
            await record_func(observations)
            print_debug(f"Recorded {len(observations)} observations to long-term memory")
        except Exception as e:
            print_debug(f"Error recording to long-term memory: {e}")

    async def _extract_observations(self):
        """Extract tool observations from agent's short-term memory for recording."""
        if not self.active_agent or not hasattr(self.active_agent, 'memory'):
            return []
        try:
            memory = self.active_agent.memory
            messages = memory.get_memory()
            if asyncio.iscoroutine(messages):
                messages = await messages

            observations = []
            for m in messages:
                role = getattr(m, 'role', None) or m.get('role', '') if isinstance(m, dict) else ''
                content = getattr(m, 'content', None) or m.get('content', '') if isinstance(m, dict) else str(m)

                if 'observation' in str(role).lower() or 'tool' in str(role).lower():
                    observations.append(m)
                elif content and any(marker in content.lower() for marker in ['search results', 'http://', 'https://']):
                    observations.append(m)

            return observations
        except Exception as e:
            print_debug(f"Error extracting observations: {e}")
            return []

    def _format_retrieved_context(self, retrieved):
        """Format retrieved memories for injection into the message."""
        if not retrieved:
            return ""
        if isinstance(retrieved, str):
            return retrieved
        if isinstance(retrieved, list):
            formatted = []
            for item in retrieved:
                if hasattr(item, 'content'):
                    formatted.append(str(item.content))
                elif isinstance(item, dict) and 'content' in item:
                    formatted.append(str(item['content']))
                else:
                    formatted.append(str(item))
            return "\n".join(formatted)
        return str(retrieved)

    async def _execute_agent(self, msg):
        """Execute agent with static long-term memory control."""
        # Reset tracking for this execution
        self._last_retrieved_memories = None
        self._last_recorded_observations = None

        async with self._get_memory_context():
            # 1. Retrieve relevant past findings before execution
            retrieved = await self._retrieve_memories(msg)

            # 2. Track and inject retrieved context
            effective_msg = msg
            if retrieved:
                context_text = self._format_retrieved_context(retrieved)
                if context_text.strip():
                    # Track for metadata
                    self._last_retrieved_memories = context_text
                    enhanced_content = f"{msg.content}\n\n[Relevant prior findings from memory:\n{context_text}]"
                    effective_msg = Msg(role=msg.role, content=enhanced_content, name=getattr(msg, 'name', None))
                    print_debug(f"Injected {len(context_text)} chars of retrieved context")

            # 3. Execute agent (handle async generator for browser agent)
            response = await self.active_agent(effective_msg)
            if inspect.isasyncgen(response):
                final_res = None
                async for x in response:
                    final_res = x
                response = final_res

            # 4. Record observations to long-term memory for future retrieval
            observations = await self._extract_observations()
            if observations:
                # Track for metadata (serialize observations)
                self._last_recorded_observations = [
                    m.to_dict() if hasattr(m, 'to_dict') else str(m) for m in observations
                ]
            await self._record_findings(observations)

            return response

    def _get_trial_meta(self, trial):
        """Return memory-related metadata for this trial."""
        meta = {}
        if self._last_retrieved_memories:
            meta['memory_retrieved'] = self._last_retrieved_memories
        if self._last_recorded_observations:
            meta['memory_recorded'] = self._last_recorded_observations
        if self.long_term_memory:
            meta['memory_type'] = type(self.long_term_memory).__name__
        return meta

    def _get_system_prompt_key(self):
        return "browser_agent_system_prompt"

    def _get_retry_prompt_key(self):
        return "shared_retry_request"
