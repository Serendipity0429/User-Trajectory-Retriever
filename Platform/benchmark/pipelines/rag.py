import json
from task_manager.utils import check_answer_rule, check_answer_llm, redis_client
from ..utils import (
    get_search_engine, print_debug, extract_final_answer, extract_query,
    RedisKeys, PipelinePrefix, TraceFormatter, SimpleMsg, PROMPTS, TrialGuard
)
from ..models import (
    BenchmarkSettings, MultiTurnSession
)
from .base import BaseMultiTurnPipeline


class RagMultiTurnPipeline(BaseMultiTurnPipeline):
    def __init__(self, base_url, api_key, model, max_retries, pipeline_id=None, dataset_id=None, group_id=None):
        super().__init__(base_url, api_key, model, max_retries, pipeline_id, dataset_id, group_id)
        self.search_engine = get_search_engine()
        self.redis_prefix = PipelinePrefix.RAG

    def __str__(self):
        return "RAG Multi-Turn Pipeline"

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

    def create_session(self, settings, question_text, ground_truths, group):
        return MultiTurnSession.objects.create(
            question=question_text,
            ground_truths=ground_truths,
            run=group,
            run_tag=self.pipeline_id,
            pipeline_type='rag'
        )

    def _construct_messages(self, session, trial, completed_trials=None):
        """
        Builds the conversation history from past trials.
        Unified pattern: system prompt + past trials' full conversations.
        """
        if completed_trials is None:
            completed_trials = list(session.trials.filter(status='completed').order_by('trial_number'))

        allow_reasoning = session.run.settings.allow_reasoning if session.run and session.run.settings else False

        # System prompt
        system_prompt = PROMPTS["rag_system_prompt"]
        if allow_reasoning:
            system_prompt += PROMPTS["shared_reasoning_instruction_no_agent"]

        messages = [{"role": "system", "content": system_prompt}]

        # Append past trials' messages (excluding system prompts)
        for past_trial in completed_trials:
            past_msgs = past_trial.log.get('messages', [])
            for m in past_msgs:
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
            allow_reasoning = session.run.settings.allow_reasoning if session.run and session.run.settings else False

            # Build base history from past trials
            history = self._construct_messages(session, trial, completed_trials)

            trial.log = trial.log or {}
            turn_messages = []  # Messages added during this turn

            # Helper for trace updates
            def build_trace_msgs(all_messages):
                trace_msgs = []
                for m in all_messages:
                    trace_msgs.append(SimpleMsg(m["role"], m["content"]))
                return trace_msgs

            def update_redis_trace(all_messages):
                trace_msgs = build_trace_msgs(all_messages)
                trace_data, _ = TraceFormatter.serialize(trace_msgs)
                redis_client.set(RedisKeys.trial_trace(trial.id), json.dumps(trace_data), ex=RedisKeys.DEFAULT_TTL)

            # === Phase 1: Query Generation ===
            if trial.trial_number == 1:
                query_instruction = PROMPTS["rag_query_gen_cot_prompt" if allow_reasoning else "rag_query_gen_prompt"].format(question=session.question)
            else:
                # Add retry message to turn_messages only (not history, to avoid duplication in final_messages)
                retry_msg = {"role": "user", "content": PROMPTS["shared_retry_request"].format(question=session.question)}
                turn_messages.append(retry_msg)
                query_instruction = PROMPTS["rag_query_reform_cot_prompt" if allow_reasoning else "rag_query_reform_prompt"]

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
            results_instruction += PROMPTS["shared_reasoning_instruction_no_agent" if allow_reasoning else "shared_answer_request"]

            results_msg = {"role": "user", "content": results_instruction}
            turn_messages.append(results_msg)

            # Build full message list for answer generation
            answer_messages = history + turn_messages

            # Update trace before streaming
            update_redis_trace(answer_messages)

            # Stream the answer (track token usage)
            full_response = ""
            chunk_count = 0
            for partial_response, usage in self.get_llm_response_stream(answer_messages):
                full_response = partial_response
                if usage:  # Usage is provided in final yield
                    trial_usage = self._accumulate_usage(trial_usage, usage, "answer_synthesis")
                chunk_count += 1
                if chunk_count % 5 == 0:
                    update_redis_trace(answer_messages + [{"role": "assistant", "content": full_response}])

            # Final trace update
            assistant_msg = {"role": "assistant", "content": full_response}
            turn_messages.append(assistant_msg)
            final_messages = history + turn_messages
            update_redis_trace(final_messages)

            # Extract answer
            if allow_reasoning:
                answer = extract_final_answer(full_response)
            else:
                answer = full_response

            # === Phase 3: Finalize (uses judge client/model, not generation model) ===
            is_correct_llm = check_answer_llm(session.question, session.ground_truths, answer, client=self.judge_client, model=self.judge_model)
            is_correct_rule = check_answer_rule(session.question, session.ground_truths, answer)

            trial.answer = answer
            trial.is_correct_llm = is_correct_llm
            trial.is_correct_rule = is_correct_rule
            trial.feedback = "Correct" if is_correct_llm else "Incorrect"
            trial.status = 'completed'

            # Store only this turn's messages (not full history) for clean reconstruction
            trial.log["messages"] = turn_messages
            trial.log["meta"] = self._get_trial_meta(trial)
            # Store token usage
            if trial_usage:
                trial.log["token_usage"] = trial_usage
            trial.save()

            # Cache status for UI
            try:
                trace_msgs = build_trace_msgs(final_messages)
                trace, _ = TraceFormatter.serialize(trace_msgs)
                status_data = {
                    "id": trial.id, "status": "completed", "answer": answer, "feedback": trial.feedback,
                    "is_correct_llm": is_correct_llm, "is_correct_rule": is_correct_rule,
                }
                redis_client.set(RedisKeys.trial_status(trial.id), json.dumps(status_data), ex=RedisKeys.DEFAULT_TTL)
                redis_client.set(RedisKeys.trial_trace(trial.id), json.dumps(trace), ex=RedisKeys.DEFAULT_TTL)
            except Exception as e:
                print_debug(f"Failed to cache RAG trace: {e}")

            return answer, is_correct_llm, search_results
