from datetime import datetime
import json
from task_manager.utils import check_answer_rule, check_answer_llm, redis_client
from ..search_utils import get_search_engine
from ..prompts import PROMPTS
from ..models import (
    BenchmarkSettings, MultiTurnSession, MultiTurnTrial
)
from ..utils import print_debug, extract_final_answer
from ..trace_formatter import TraceFormatter
from .base import BaseMultiTurnPipeline

class RagMultiTurnPipeline(BaseMultiTurnPipeline):
    def __init__(self, base_url, api_key, model, max_retries, pipeline_id=None, dataset_id=None, group_id=None):
        super().__init__(base_url, api_key, model, max_retries, pipeline_id, dataset_id, group_id)
        self.search_engine = get_search_engine()
        self.redis_prefix = "rag_pipeline_active"

    def __str__(self):
        return "RAG Multi-Turn Pipeline"

    def get_settings_snapshot(self):
        settings = BenchmarkSettings.get_effective_settings()
        snapshot = super().get_settings_snapshot()
        snapshot['search'] = {
            'search_provider': settings.search_provider,
            'search_limit': settings.search_limit,
            'serper_fetch_full_content': settings.fetch_full_content
        }
        return snapshot

    def create_session(self, settings, question_text, ground_truths, group):
        return MultiTurnSession.objects.create(
            question=question_text,
            ground_truths=ground_truths,
            run=group,
            run_tag=self.pipeline_id,
            pipeline_type='rag'
        )

    def create_trial(self, session, trial_number):
        return MultiTurnTrial.objects.create(
            session=session,
            trial_number=trial_number,
            status='processing'
        )

    def _get_history_key(self, session_id):
        return f"{self.redis_prefix}:history:{session_id}"

    def _construct_messages(self, session, trial, completed_trials=None):
        """
        Builds the conversation history including the current turn's query and results.
        This is what the LLM sees when generating the final answer.
        """
        history_key = self._get_history_key(session.id)
        cached_history_json = redis_client.get(history_key)
        
        if cached_history_json:
            messages = json.loads(cached_history_json)
        else:
            messages = self._reconstruct_history(session, completed_trials)

        final_messages = messages.copy() 
        
        # If the trial has already performed its search, append the conversational steps
        trial_log = trial.log or {}
        search_query = trial_log.get('search_query')
        if search_query:
            allow_reasoning = session.run.settings.allow_reasoning if session.run and session.run.settings else False
            
            if trial.trial_number == 1:
                instruction = PROMPTS["rag_query_gen_cot_prompt" if allow_reasoning else "rag_query_gen_prompt"].format(question=session.question)
            else:
                instruction = PROMPTS["rag_query_reform_cot_prompt" if allow_reasoning else "rag_query_reform_prompt"]
            
            search_results = trial_log.get('search_results') or []
            formatted_results = self.search_engine.format_results(search_results)
            
            # Add the query generation "exchange"
            final_messages.append({"role": "user", "content": instruction})
            final_messages.append({"role": "assistant", "content": f"Search Query: {search_query}"})
            
            # Add the result providing "exchange"
            final_instr = "Search Results:\n" + PROMPTS["rag_context_wrapper"].format(formatted_results=formatted_results)
            final_instr += PROMPTS["shared_reasoning_format" if allow_reasoning else "shared_answer_request"]

            final_messages.append({"role": "user", "content": final_instr})
            
        return final_messages

    def _reconstruct_history(self, session, completed_trials=None):
        """
        Reconstructs the full conversational trajectory from past trials.
        """
        if completed_trials is None:
            completed_trials = list(session.trials.filter(status='completed').order_by('trial_number'))
            
        messages = []
        allow_reasoning = session.run.settings.allow_reasoning if session.run and session.run.settings else False
        
        system_prompt = PROMPTS["rag_system_prompt"]
        if allow_reasoning:
            system_prompt += PROMPTS["shared_reasoning_instruction_no_agent"]
            
        messages.append({"role": "system", "content": system_prompt})
        
        for past_trial in completed_trials:
            past_log = past_trial.log or {}
            search_query = past_log.get('search_query')
            search_results = past_log.get('search_results') or []

            # 1. Query Instruction
            if past_trial.trial_number == 1:
                instruction = PROMPTS["rag_query_gen_cot_prompt" if allow_reasoning else "rag_query_gen_prompt"].format(question=session.question)
            else:
                instruction = PROMPTS["rag_query_reform_cot_prompt" if allow_reasoning else "rag_query_reform_prompt"]
            
            # 2. Assistant's Query
            messages.append({"role": "user", "content": instruction})
            messages.append({"role": "assistant", "content": f"Search Query: {search_query}"})
            
            # 3. Search Results and Answer Instruction
            formatted_results = self.search_engine.format_results(search_results)
            final_instr = "Search Results:\n" + PROMPTS["rag_context_wrapper"].format(formatted_results=formatted_results)
            final_instr += PROMPTS["shared_reasoning_format" if allow_reasoning else "shared_answer_request"]
            
            messages.append({"role": "user", "content": final_instr})
            
            # 4. Assistant's Answer
            messages.append({"role": "assistant", "content": past_trial.full_response or past_trial.answer})
            
        return messages

    def run_single_turn(self, session, trial, completed_trials=None):
        from ..utils import TrialGuard
        with TrialGuard(trial):
            allow_reasoning = session.run.settings.allow_reasoning if session.run and session.run.settings else False
            
            history_key = self._get_history_key(session.id)
            history_json = redis_client.get(history_key)
            history = json.loads(history_json) if history_json else self._reconstruct_history(session, completed_trials)

            trial.log = trial.log or {}

            # Prepare trace using TraceFormatter
            class SimpleMsg:
                def __init__(self, role, content):
                    self.role = role
                    self.content = content
                    self.name = None
                def to_dict(self):
                    return {"role": self.role, "content": self.content}

            def update_redis_trace(messages_to_serialize):
                trace_data, _ = TraceFormatter.serialize(messages_to_serialize)
                redis_client.set(f"trial_trace:{trial.id}", json.dumps(trace_data), ex=3600)

            # 1. Query Reformulation / Generation
            if trial.trial_number == 1:
                instruction = PROMPTS["rag_query_gen_cot_prompt" if allow_reasoning else "rag_query_gen_prompt"].format(question=session.question)
            else:
                history.append({"role": "user", "content": PROMPTS["rag_retry_prefix"]})
                instruction = PROMPTS["rag_query_reform_cot_prompt" if allow_reasoning else "rag_query_reform_prompt"]

            if not trial.log.get("search_query"):
                reformulation_messages = history + [{"role": "user", "content": instruction}]
                raw_query_response, _ = self.get_llm_response(reformulation_messages, temperature=0.0, allow_reasoning=False)

                if allow_reasoning:
                    from ..utils import extract_query
                    trial.log["search_query"] = extract_query(raw_query_response)
                    trial.log["query_full_response"] = raw_query_response
                else:
                    trial.log["search_query"] = raw_query_response.strip().strip('"').strip("'")
                
                trial.log["search_results"] = self.search_engine.search(trial.log["search_query"])
                trial.save()
                
                # Initial Trace update after search
                initial_msgs = self._construct_messages(session, trial, completed_trials)
                
                # Apply enhancement for rich rendering, but keep FULL HISTORY
                trace_msgs_for_update = []
                for idx, m in enumerate(initial_msgs):
                    role = m.get('role')
                    content = m.get('content')
                    
                    if role == 'system' and idx == 0:
                        trace_msgs_for_update.append(SimpleMsg('system', content))
                        continue
                    
                    # Enhance ONLY the current turn's result message (the last one)
                    is_current_results = (idx == len(initial_msgs) - 1) and role == 'user' and isinstance(content, str) and content.strip().startswith("Search Results:")
                    
                    if is_current_results:
                        results = trial.log.get("search_results")
                        if results:
                            wrapper_intro = PROMPTS["rag_context_wrapper"].split("{formatted_results}")[0].strip()
                            formatted_str = self.search_engine.format_results(results)
                            instruction_text = PROMPTS["shared_reasoning_format" if allow_reasoning else "shared_answer_request"]
                            
                            full_combined_content = f"{wrapper_intro}\n\n{formatted_str}\n\n{instruction_text}"
                            trace_msgs_for_update.append(SimpleMsg(role, full_combined_content))
                            continue
                    
                    if role != 'system':
                        trace_msgs_for_update.append(SimpleMsg(role, content))

                update_redis_trace(trace_msgs_for_update)

            # 2. Answer Question (Synthesize with Streaming)
            messages = self._construct_messages(session, trial, completed_trials)
            
            # Identify ALL messages for TRACE (Cumulative)
            current_turn_static_msgs = []
            if messages:
                for idx, m in enumerate(messages):
                    role = m.get('role')
                    content = m.get('content')
                    
                    if role == 'system' and idx == 0:
                        current_turn_static_msgs.append(SimpleMsg('system', content))
                        continue
                    
                    # Enhance ONLY the current turn's result message (the last one)
                    is_current_results = (idx == len(messages) - 1) and role == 'user' and isinstance(content, str) and content.strip().startswith("Search Results:")
                    
                    if is_current_results:
                        results = trial.log.get("search_results")
                        if results:
                            wrapper_intro = PROMPTS["rag_context_wrapper"].split("{formatted_results}")[0].strip()
                            formatted_str = self.search_engine.format_results(results)
                            instruction_text = PROMPTS["shared_reasoning_format" if allow_reasoning else "shared_answer_request"]
                            
                            full_combined_content = f"{wrapper_intro}\n\n{formatted_str}\n\n{instruction_text}"
                            current_turn_static_msgs.append(SimpleMsg(role, full_combined_content))
                            continue

                    if role != 'system':
                        current_turn_static_msgs.append(SimpleMsg(role, content))

            full_response = ""
            
            chunk_count = 0
            for partial_response in self.get_llm_response_stream(messages):
                full_response = partial_response
                chunk_count += 1
                if chunk_count % 5 == 0:
                    update_redis_trace(current_turn_static_msgs + [SimpleMsg("assistant", full_response)])
            
            # Final trace update for synthesising phase
            update_redis_trace(current_turn_static_msgs + [SimpleMsg("assistant", full_response)])
            
            if allow_reasoning:
                answer = extract_final_answer(full_response)
            else:
                answer = full_response
            
            # 3. Finalize
            trace, _ = TraceFormatter.serialize(current_turn_static_msgs + [SimpleMsg("assistant", full_response)])
            
            is_correct_llm = check_answer_llm(session.question, session.ground_truths, answer, client=self.client, model=self.model)
            is_correct_rule = check_answer_rule(session.question, session.ground_truths, answer)
            
            trial.answer = answer
            trial.full_response = full_response
            trial.is_correct_llm = is_correct_llm
            trial.is_correct_rule = is_correct_rule
            trial.feedback = "Correct" if is_correct_llm else "Incorrect"
            trial.status = 'completed'
            trial.log["trace"] = trace
            trial.save()

            # 4. Update Persistence Cache
            new_history = messages + [{"role": "assistant", "content": full_response or answer}]
            redis_client.set(history_key, json.dumps(new_history), ex=3600)

            # 5. Cache for UI
            try:
                status_data = {
                    "id": trial.id, "status": "completed", "answer": answer, "feedback": trial.feedback,
                    "is_correct_llm": is_correct_llm, "is_correct_rule": is_correct_rule,
                    "full_response": full_response, "trace": trace
                }
                redis_client.set(f"trial_status:{trial.id}", json.dumps(status_data), ex=3600)
                redis_client.set(f"trial_trace:{trial.id}", json.dumps(trace), ex=3600)
            except Exception as e:
                print_debug(f"Failed to cache RAG trace: {e}")

            return answer, is_correct_llm, trial.log.get("search_results", [])
