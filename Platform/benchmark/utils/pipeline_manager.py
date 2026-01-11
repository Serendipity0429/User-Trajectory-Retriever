import asyncio
import threading
from asgiref.sync import sync_to_async
from ..models import MultiTurnSession, MultiTurnTrial


class PipelineRegistry:
    """
    Centralized registry for pipeline type mappings.
    Eliminates scattered if-elif chains and duplicate mapping definitions.
    """

    # Lazy-loaded pipeline classes to avoid circular imports
    _pipeline_classes = None

    @classmethod
    def _get_pipeline_classes(cls):
        """Lazy-load pipeline classes to avoid circular imports."""
        if cls._pipeline_classes is None:
            from ..pipelines.vanilla import VanillaLLMMultiTurnPipeline
            from ..pipelines.rag import RagMultiTurnPipeline
            from ..pipelines.agent import VanillaAgentPipeline, BrowserAgentPipeline
            cls._pipeline_classes = {
                'vanilla_llm': VanillaLLMMultiTurnPipeline,
                'rag': RagMultiTurnPipeline,
                'vanilla_agent': VanillaAgentPipeline,
                'browser_agent': BrowserAgentPipeline,
            }
        return cls._pipeline_classes

    # Redis prefix mappings for pipeline control signals
    REDIS_PREFIXES = {
        'vanilla_llm': 'vanilla_llm_pipeline_active',
        'rag': 'rag_pipeline_active',
        'vanilla_agent': 'vanilla_agent_pipeline_active',
        'browser_agent': 'browser_agent_pipeline_active',
    }

    # Async pipeline types (require async wrapper)
    ASYNC_PIPELINE_TYPES = {'vanilla_agent', 'browser_agent'}

    @classmethod
    def get_pipeline_class(cls, pipeline_type):
        """Get the pipeline class for a given type."""
        classes = cls._get_pipeline_classes()
        if pipeline_type not in classes:
            raise ValueError(f"Unknown pipeline type: {pipeline_type}")
        return classes[pipeline_type]

    @classmethod
    def get_redis_prefix(cls, pipeline_type):
        """Get the Redis prefix for a given pipeline type."""
        if pipeline_type not in cls.REDIS_PREFIXES:
            raise ValueError(f"Unknown pipeline type: {pipeline_type}")
        return cls.REDIS_PREFIXES[pipeline_type]

    @classmethod
    def is_async_pipeline(cls, pipeline_type):
        """Check if a pipeline type requires async handling."""
        return pipeline_type in cls.ASYNC_PIPELINE_TYPES

    @classmethod
    def get_all_types(cls):
        """Get all registered pipeline types."""
        return list(cls.REDIS_PREFIXES.keys())

    @classmethod
    def is_valid_type(cls, pipeline_type):
        """Check if a pipeline type is valid."""
        return pipeline_type in cls.REDIS_PREFIXES

class PipelineManager:
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        self.pipelines = {} # session_id -> pipeline instance

    def _run_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    @classmethod
    def get_instance(cls):
        with cls._lock:
            if not cls._instance:
                cls._instance = cls()
        return cls._instance

    def run_trial(self, session_id, trial_id, factory_kwargs, pipeline_class):
        """
        Submit a run_trial task to the background loop and wait for result.
        factory_kwargs: dict containing base_url, api_key, model, max_retries
        """
        future = asyncio.run_coroutine_threadsafe(
            self._run_trial_async(session_id, trial_id, factory_kwargs, pipeline_class),
            self.loop
        )
        return future.result()

    async def _run_trial_async(self, session_id, trial_id, factory_kwargs, pipeline_class):
        # 1. Get or Create Pipeline
        if session_id not in self.pipelines:
            try:
                if hasattr(pipeline_class, 'create'):
                    pipeline = await pipeline_class.create(**factory_kwargs)
                else:
                    pipeline = await sync_to_async(pipeline_class)(**factory_kwargs)
                    
                self.pipelines[session_id] = pipeline
            except Exception as e:
                return None, False, [], f"Pipeline Initialization Error: {str(e)}"
        
        pipeline = self.pipelines[session_id]
        
        # 2. Fetch DB Objects safely
        try:
            session = await sync_to_async(MultiTurnSession.objects.get)(pk=session_id)
            trial = await sync_to_async(MultiTurnTrial.objects.get)(pk=trial_id)
        except Exception as e:
            return None, False, [], f"DB Error: {str(e)}"

        # 3. Run Turn
        # run_single_turn_async(session, trial, auto_cleanup=False) 
        # auto_cleanup=False is default, ensuring connection stays alive.
        try:
            answer, is_correct_llm, search_results = await pipeline.run_single_turn_async(session, trial)
            return answer, is_correct_llm, search_results, None
        except Exception as e:
            def update_error():
                trial.status = 'error'
                trial.save()
            await sync_to_async(update_error)()
            return None, False, [], str(e)

    def close_session(self, session_id):
        """
        Clean up pipeline resources for a session.
        """
        if session_id in self.pipelines:
            asyncio.run_coroutine_threadsafe(
                self._cleanup_async(session_id),
                self.loop
            )

    async def _cleanup_async(self, session_id):
        if session_id in self.pipelines:
            pipeline = self.pipelines[session_id]
            await pipeline.cleanup()
            del self.pipelines[session_id]
