import json
import asyncio
import threading
from concurrent import futures
from datetime import datetime
from asgiref.sync import sync_to_async
from agentscope.message import Msg
from ..models import BenchmarkSettings, MultiTurnRun, MultiTurnSession, MultiTurnTrial
from ..utils import (
    print_debug,
    VanillaAgentFactory, BrowserAgentFactory,
    clear_trial_cache
)
from ..utils.mcp_manager import ChromeDevToolsMCPManager
from .base import BaseAgentPipeline, REDIS_PREFIX_BROWSER_AGENT
import inspect

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
        return await sync_to_async(VanillaAgentFactory.create_agent)(self.agent_model)

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

        return await BrowserAgentFactory.create_agent(
            self.agent_model,
            self.agent_toolkit,
            self.mcp_client
        )

    async def _execute_agent(self, msg):
        response = await self.active_agent(msg)
        if inspect.isasyncgen(response):
            final_res = None
            async for x in response: final_res = x
            response = final_res
        return response

    def _get_system_prompt_key(self):
        return "browser_agent_system_prompt"

    def _get_retry_prompt_key(self):
        return "shared_retry_request"
