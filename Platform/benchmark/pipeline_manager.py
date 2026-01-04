import asyncio
import threading
from asgiref.sync import sync_to_async
from .pipelines.agent import BrowserAgentPipeline
from .models import MultiTurnSession, MultiTurnTrial

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
            answer, is_correct, search_results = await pipeline.run_single_turn_async(session, trial)
            return answer, is_correct, search_results, None
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
