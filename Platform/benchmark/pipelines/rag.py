import json
from task_manager.utils import redis_client
from ..utils import (
    get_search_engine, extract_final_answer, extract_query,
    RedisKeys, PipelinePrefix, TraceFormatter, SimpleMsg, PROMPTS, TrialGuard,
    has_builtin_thinking
)
from ..models import BenchmarkSettings, MultiTurnSession
from .base import BaseMultiTurnPipeline


class RagMultiTurnPipeline(BaseMultiTurnPipeline):
    def __init__(self, base_url, api_key, model, max_retries, pipeline_id=None, dataset_id=None, group_id=None, rerun_errors=True):
        super().__init__(base_url, api_key, model, max_retries, pipeline_id, dataset_id, group_id, rerun_errors)
        self.search_engine = get_search_engine()
        self.redis_prefix = PipelinePrefix.RAG

    def __str__(self):
        return "RAG Multi-Turn Pipeline"

    def create_session(self, settings, question_text, ground_truths, group):
        return MultiTurnSession.objects.create(
            question=question_text,
            ground_truths=ground_truths,
            run=group,
            run_tag=self.pipeline_id,
            pipeline_type='rag'
        )

    def _get_pipeline_settings(self):
        """Returns RAG-specific settings (search configuration)."""
        settings = BenchmarkSettings.get_effective_settings()
        return {
            'search': {
                'search_provider': settings.search_provider,
                'search_limit': settings.search_limit,
                'serper_fetch_full_content': settings.fetch_full_content
            }
        }

    def get_pipeline_type_name(self):
        return 'rag'

    def _construct_messages(self, session, trial, completed_trials=None):
        """Builds conversation history from past trials."""
        if completed_trials is None:
            completed_trials = list(session.trials.filter(status='completed').order_by('trial_number'))

        settings = session.run.settings if session.run else None
        allow_reasoning = settings.allow_reasoning if settings else False

        # System prompt - add CoT instructions only for non-thinking models
        system_prompt = PROMPTS["rag_system_prompt"]
        model_name = settings.llm_model if settings else ""
        if allow_reasoning and not has_builtin_thinking(model_name):
            system_prompt += PROMPTS["shared_reasoning_instruction"]

        messages = [{"role": "system", "content": system_prompt}]

        # Append past trials' messages
        for past_trial in completed_trials:
            for m in past_trial.log.get('messages', []):
                if m.get('role') != 'system':
                    messages.append(m)

        return messages

    def _get_trial_meta(self, trial) -> dict:
        """Return RAG-specific metadata for export/analytics."""
        log = trial.log or {}
        return {
            'search_query': log.get('search_query'),
            'search_results': log.get('search_results'),
        }

    def run_single_turn(self, session, trial, completed_trials=None):
        with TrialGuard(trial):
            settings = session.run.settings if session.run else None
            allow_reasoning = settings.allow_reasoning if settings else False
            # For thinking models, skip explicit CoT - they think natively
            use_cot = allow_reasoning and not has_builtin_thinking(settings.llm_model if settings else "")

            # Build base history
            if completed_trials is None:
                completed_trials = list(session.trials.filter(
                    trial_number__lt=trial.trial_number,
                    status='completed'
                ).order_by('trial_number'))
            history = self._construct_messages(session, trial, completed_trials)

            trial.log = trial.log or {}
            turn_messages = []

            system_prompt = history[0].get('content', '') if history and history[0].get('role') == 'system' else ''

            def build_trace_msgs(messages):
                return [SimpleMsg(m["role"], m["content"]) for m in messages]

            def update_redis_trace(current_turn_messages):
                trace_msgs = [SimpleMsg("system", system_prompt)] if system_prompt else []
                trace_msgs.extend(build_trace_msgs(current_turn_messages))
                trace_data, _ = TraceFormatter.serialize(trace_msgs)
                redis_client.set(RedisKeys.trial_trace(trial.id), json.dumps(trace_data), ex=RedisKeys.DEFAULT_TTL)

            # === Phase 1: Query Generation ===
            if trial.trial_number == 1:
                prompt_key = "rag_query_gen_cot_prompt" if use_cot else "rag_query_gen_prompt"
                query_instruction = PROMPTS[prompt_key].format(question=session.question)
            else:
                turn_messages.append({"role": "user", "content": PROMPTS["shared_retry_request"].format(question=session.question)})
                query_instruction = PROMPTS["rag_query_reform_cot_prompt" if use_cot else "rag_query_reform_prompt"]

            # Add query instruction
            query_instruction_msg = {"role": "user", "content": query_instruction}
            query_messages = history + turn_messages + [query_instruction_msg]

            # Get query from LLM (track token usage)
            trial_usage = None
            raw_query_response, _, query_usage = self.get_llm_response(query_messages, temperature=0.0, allow_reasoning=False)
            trial_usage = self._accumulate_usage(trial_usage, query_usage, "query_generation")

            if allow_reasoning:
                search_query = extract_query(raw_query_response)
                trial.log["query_full_response"] = raw_query_response
            else:
                search_query = raw_query_response.strip().strip('"').strip("'")

            trial.log["search_query"] = search_query

            # Perform search
            search_results = self.search_engine.search(search_query)
            trial.log["search_results"] = search_results
            trial.save()

            # Record the query exchange
            turn_messages.append(query_instruction_msg)
            turn_messages.append({"role": "assistant", "content": f"Search Query: {search_query}"})

            # === Phase 2: Answer Synthesis ===
            formatted_results = self.search_engine.format_results(search_results)
            results_instruction = "Search Results:\n" + PROMPTS["rag_context_wrapper"].format(formatted_results=formatted_results)
            results_instruction += PROMPTS["shared_reasoning_instruction"] if use_cot else PROMPTS["shared_answer_request"]

            results_msg = {"role": "user", "content": results_instruction}
            turn_messages.append(results_msg)

            # Build full message list for answer generation (includes history for LLM context)
            answer_messages = history + turn_messages

            # Update trace before streaming (only current turn's messages)
            update_redis_trace(turn_messages)

            # Stream the answer (track token usage)
            full_response = ""
            chunk_count = 0
            for partial_response, usage in self.get_llm_response_stream(answer_messages):
                full_response = partial_response
                if usage:  # Usage is provided in final yield
                    trial_usage = self._accumulate_usage(trial_usage, usage, "answer_synthesis")
                chunk_count += 1
                if chunk_count % 5 == 0:
                    # Show current turn messages + streaming response
                    update_redis_trace(turn_messages + [{"role": "assistant", "content": full_response}])

            # Final trace update (current turn only)
            assistant_msg = {"role": "assistant", "content": full_response}
            turn_messages.append(assistant_msg)
            update_redis_trace(turn_messages)

            # Extract answer
            if allow_reasoning:
                answer = extract_final_answer(full_response)
            else:
                answer = full_response

            # === Phase 3: Finalize using shared helpers ===
            is_correct_llm, is_correct_rule = self._evaluate_trial(session, answer)

            # Build trial messages (system prompt + turn messages)
            trial_messages = []
            if system_prompt:
                trial_messages.append({"role": "system", "content": system_prompt})
            trial_messages.extend(turn_messages)

            # Finalize trial (preserves existing search_query/search_results in trial.log)
            self._finalize_trial(
                trial, answer, is_correct_llm, is_correct_rule,
                messages=trial_messages,
                system_prompt=system_prompt,
                token_usage=trial_usage
            )

            # Build trace and cache to Redis
            trace_msgs = []
            if system_prompt:
                trace_msgs.append(SimpleMsg("system", system_prompt))
            trace_msgs.extend(build_trace_msgs(turn_messages))
            trace, _ = TraceFormatter.serialize(trace_msgs)
            self._cache_trial_to_redis(trial, trace)

            return answer, is_correct_llm, search_results
