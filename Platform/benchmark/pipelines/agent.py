import inspect
import json
from asgiref.sync import sync_to_async
from ..models import BenchmarkSettings, MultiTurnRun, MultiTurnSession
from ..utils import (
    print_debug,
    VanillaAgentFactory, BrowserAgentFactory
)
from ..utils.mcp_manager import ChromeDevToolsMCPManager
from .base import BaseAgentPipeline, REDIS_PREFIX_VANILLA_AGENT, REDIS_PREFIX_BROWSER_AGENT


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
    def __init__(self, base_url, api_key, model, max_retries, pipeline_id=None, dataset_id=None, group_id=None, rerun_errors=True):
        super().__init__(base_url, api_key, model, max_retries, pipeline_id, dataset_id, group_id, rerun_errors)
        # Initialize AgentScope
        self.temp_settings = BenchmarkSettings(
            llm_base_url=base_url,
            llm_api_key=api_key,
            llm_model=model,
            temperature=0.0
        )
        self.agent_model = VanillaAgentFactory.init_agentscope(self.temp_settings)
        self.redis_prefix = REDIS_PREFIX_VANILLA_AGENT
        self.long_term_memory = None  # Will be set in _init_agent
        self._current_run_id = None  # Set when processing starts, used for memory isolation

    @classmethod
    async def create(cls, base_url, api_key, model, max_retries, pipeline_id=None, dataset_id=None, group_id=None, rerun_errors=True):
        try:
            instance = await sync_to_async(cls)(base_url, api_key, model, max_retries, pipeline_id, dataset_id, group_id, rerun_errors)
            return instance
        except Exception as e:
            print_debug(f"VanillaAgentPipeline: Error in create: {e}")
            raise e

    def __str__(self):
        return "Vanilla Agent Pipeline"

    def _get_pipeline_type(self):
        return 'vanilla_agent'

    def create_session(self, settings, question_text, ground_truths, group):
        return MultiTurnSession.objects.create(
            question=question_text,
            ground_truths=ground_truths,
            run=group,
            run_tag=self.pipeline_id,
            pipeline_type='vanilla_agent'
        )

    # Hooks for BaseAgentPipeline template
    async def _init_agent(self):
        # Pass run_id for memory isolation (set by base pipeline before agent creation)
        agent, long_term_memory = await sync_to_async(VanillaAgentFactory.create_agent)(
            self.agent_model,
            run_id=self._current_run_id
        )
        self.long_term_memory = long_term_memory
        return agent

    async def _execute_agent(self, msg):
        """Execute agent with static_control long-term memory mode.

        The system automatically retrieves from LTM before each reply
        and records the full conversation to LTM after reply.
        """
        async with self._get_memory_context():
            response = await self.active_agent(msg)
            return response

    def _get_trial_meta(self, trial):
        """Return memory-related metadata for this trial.

        With static_control mode, memory operations are handled automatically.
        We only record the memory type here for reference.
        """
        meta = {}
        if self.long_term_memory:
            meta['memory_type'] = type(self.long_term_memory).__name__
        return meta

    def _get_system_prompt_key(self):
        return "vanilla_agent_system_prompt"

    def _get_retry_prompt_key(self):
        return "shared_retry_request"

    def _get_actual_system_prompt(self):
        """Return the actual system prompt from the agent."""
        if hasattr(self, 'active_agent') and self.active_agent:
            return getattr(self.active_agent, 'sys_prompt', None) or super()._get_actual_system_prompt()
        return super()._get_actual_system_prompt()

    def _should_clear_memory_on_retry(self):
        """Clear short-term memory on retry when long-term memory is enabled."""
        return self.long_term_memory is not None


class BrowserAgentPipeline(BaseAgentPipeline):
    def __init__(self, base_url, api_key, model, max_retries, pipeline_id=None, dataset_id=None, group_id=None, rerun_errors=True):
        super().__init__(base_url, api_key, model, max_retries, pipeline_id, dataset_id, group_id, rerun_errors)
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
        self._current_run_id = None  # Set when processing starts, used for memory isolation

    @classmethod
    async def create(cls, base_url, api_key, model, max_retries, pipeline_id=None, dataset_id=None, group_id=None, rerun_errors=True):
        try:
            print_debug("BrowserAgentPipeline: Creating instance (lightweight)...")
            instance = await sync_to_async(cls)(base_url, api_key, model, max_retries, pipeline_id, dataset_id, group_id, rerun_errors)
            return instance
        except Exception as e:
            print_debug(f"BrowserAgentPipeline: Error in create: {e}")
            raise e

    def __str__(self):
        return "Browser Agent Pipeline"

    def _get_pipeline_type(self):
        return 'browser_agent'

    def create_session(self, settings, question_text, ground_truths, group):
        return MultiTurnSession.objects.create(
            question=question_text,
            ground_truths=ground_truths,
            run=group,
            run_tag=self.pipeline_id,
            pipeline_type='browser_agent'
        )

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
            BrowserAgentFactory.init_agentscope
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
                BrowserAgentFactory.init_agentscope
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

    async def _execute_agent(self, msg):
        """Execute agent with static_control long-term memory mode.

        The system automatically retrieves from LTM before each reply
        and records the full conversation to LTM after reply.
        """
        async with self._get_memory_context():
            # Execute agent (handle async generator for browser agent)
            response = await self.active_agent(msg)
            if inspect.isasyncgen(response):
                final_res = None
                async for x in response:
                    final_res = x
                response = final_res

            return response

    def _get_trial_meta(self, trial):
        """Return memory-related metadata for this trial.

        With static_control mode, memory operations are handled automatically.
        We only record the memory type here for reference.
        """
        meta = {}
        if self.long_term_memory:
            meta['memory_type'] = type(self.long_term_memory).__name__
        return meta

    def _get_system_prompt_key(self):
        return "browser_agent_system_prompt"

    def _get_retry_prompt_key(self):
        return "shared_retry_request"

    def _get_actual_system_prompt(self):
        """Return the actual system prompt from the agent."""
        if hasattr(self, 'active_agent') and self.active_agent:
            return getattr(self.active_agent, 'sys_prompt', None) or super()._get_actual_system_prompt()
        return super()._get_actual_system_prompt()

    def _should_clear_memory_on_retry(self):
        """Clear short-term memory on retry when long-term memory is enabled."""
        return self.long_term_memory is not None
