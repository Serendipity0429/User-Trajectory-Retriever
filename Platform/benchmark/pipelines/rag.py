from datetime import datetime
import json
from task_manager.utils import check_answer_rule, check_answer_llm, redis_client
from ..search_utils import get_search_engine
from ..prompts import PROMPTS
from ..models import (
    SearchSettings, AdhocRun, AdhocResult, MultiTurnSession, MultiTurnTrial
)
from ..utils import print_debug
from .base import BaseAdhocPipeline, BaseMultiTurnPipeline, REDIS_PREFIX_RAG_ADHOC

class RagAdhocPipeline(BaseAdhocPipeline):
    def __init__(self, base_url, api_key, model, pipeline_id=None, dataset_id=None):
        super().__init__(base_url, api_key, model, pipeline_id, dataset_id)
        self.search_engine = get_search_engine()
        self.redis_prefix = REDIS_PREFIX_RAG_ADHOC
        self.search_settings = SearchSettings.get_effective_settings()

    def __str__(self):
        return "RAG Ad-hoc Pipeline"

    def get_settings_snapshot(self):
        snapshot = super().get_settings_snapshot()
        snapshot['search_settings'] = {
            'search_provider': self.search_settings.search_provider,
            'search_limit': self.search_settings.search_limit,
            'serper_fetch_full_content': self.search_settings.fetch_full_content
        }
        return snapshot

    def create_run_object(self):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        return AdhocRun.objects.create(
            name=f"RAG Ad-hoc Run {timestamp}",
            settings_snapshot=self.get_settings_snapshot(),
            total_questions=0,
            correct_answers=0,
            run_type='rag'
        )

    def process_question(self, run, question, ground_truths):
        # 1. Generate Search Query (Step 1 of dialogue)
        query_instruction = PROMPTS["rag_query_generation"].format(question=question)
        search_query, _ = self.get_llm_response(
            [{"role": "user", "content": query_instruction}],
            temperature=0.0,
            allow_reasoning=False
        )
        search_query = search_query.strip().strip('"').strip("'")

        # 2. Perform Search
        search_results = self.search_engine.search(search_query)
        formatted_results = self.search_engine.format_results(search_results)

        # 3. Construct Full Conversational Prompt (Step 2 of dialogue)
        system_prompt = PROMPTS["rag_system"]
        if self.llm_settings.allow_reasoning:
            system_prompt += PROMPTS["reasoning_instruction"]

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query_instruction},
            {"role": "assistant", "content": f"Search Query: {search_query}"},
            {"role": "user", "content": f"Search Results:\n{formatted_results}Please provide the final answer."}
        ]

        # 4. Get Final Answer
        answer, full_response = self.get_llm_response(messages)
        is_correct_rule = check_answer_rule(question, ground_truths, answer)
        is_correct_llm = check_answer_llm(
            question, ground_truths, answer, 
            client=self.client, 
            model=self.model
        )

        # 5. Save Result
        AdhocResult.objects.create(
            run=run,
            question=question,
            ground_truths=ground_truths,
            answer=answer,
            full_response=full_response,
            is_correct_rule=is_correct_rule,
            is_correct_llm=is_correct_llm,
            search_query=search_query,
            num_docs_used=len(search_results),
            search_results=search_results
        )

        return {
            'question': question,
            'answer': answer,
            'full_response': full_response,
            'ground_truths': ground_truths,
            'rule_result': is_correct_rule,
            'llm_result': is_correct_llm,
            'search_query': search_query,
            'num_docs_used': len(search_results),
            'search_results': search_results
        }, is_correct_llm

class RagMultiTurnPipeline(BaseMultiTurnPipeline):
    def __init__(self, base_url, api_key, model, max_retries, pipeline_id=None, dataset_id=None):
        super().__init__(base_url, api_key, model, max_retries, pipeline_id, dataset_id)
        self.search_engine = get_search_engine()
        self.redis_prefix = "rag_multi_turn_pipeline_active"

    def __str__(self):
        return "RAG Multi-Turn Pipeline"

    def get_settings_snapshot(self):
        search_settings = SearchSettings.get_effective_settings()
        snapshot = super().get_settings_snapshot()
        snapshot['search_settings'] = {
            'search_provider': search_settings.search_provider,
            'search_limit': search_settings.search_limit,
            'serper_fetch_full_content': search_settings.fetch_full_content
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
        if trial.search_query:
            if trial.trial_number == 1:
                instruction = PROMPTS["rag_query_generation"].format(question=session.question)
            else:
                instruction = PROMPTS["rag_reformulation"]
            
            formatted_results = self.search_engine.format_results(trial.search_results or [])
            
            # Add the query generation "exchange"
            final_messages.append({"role": "user", "content": instruction})
            final_messages.append({"role": "assistant", "content": f"Search Query: {trial.search_query}"})
            
            # Add the result providing "exchange"
            final_instr = PROMPTS["rag_answer_instruction"].format(formatted_results=formatted_results)
            
            # Re-inject reasoning instruction if enabled (as models tend to forget distant system prompts)
            allow_reasoning = session.run.settings_snapshot.get('llm_settings', {}).get('allow_reasoning', False)
            if allow_reasoning:
                final_instr += PROMPTS["reasoning_reminder"]
                final_instr += "\n\nStart your response with 'Reasoning:'."
            else:
                final_instr += PROMPTS["simple_answer_instruction"]

            final_messages.append({
                "role": "user", 
                "content": final_instr
            })
            
        return final_messages

    def _reconstruct_history(self, session, completed_trials=None):
        """
        Reconstructs the full conversational trajectory from past trials.
        Includes both query generation instructions and final answer answers.
        """
        if completed_trials is None:
            completed_trials = list(session.trials.filter(status='completed').order_by('trial_number'))
            
        messages = []
        allow_reasoning = session.run.settings_snapshot.get('llm_settings', {}).get('allow_reasoning', False)
        
        system_prompt = PROMPTS["rag_system"]
        if allow_reasoning:
            system_prompt += PROMPTS["reasoning_instruction"]
            
        messages.append({"role": "system", "content": system_prompt})
        
        for past_trial in completed_trials:
            # 1. Query Instruction
            if past_trial.trial_number == 1:
                instruction = PROMPTS["rag_query_generation"].format(question=session.question)
            else:
                instruction = PROMPTS["rag_reformulation"]
            
            # 2. Assistant's Query
            messages.append({"role": "user", "content": instruction})
            messages.append({"role": "assistant", "content": f"Search Query: {past_trial.search_query}"})
            
            # 3. Search Results and Answer Instruction
            formatted_results = self.search_engine.format_results(past_trial.search_results or [])
            
            final_instr = PROMPTS["rag_answer_instruction"].format(formatted_results=formatted_results)
            if allow_reasoning:
                final_instr += PROMPTS["reasoning_reminder"]
                final_instr += "\n\nStart your response with 'Reasoning:'."
            else:
                final_instr += PROMPTS["simple_answer_instruction"]
            
            messages.append({
                "role": "user", 
                "content": final_instr
            })
            
            # 4. Assistant's Answer
            messages.append({"role": "assistant", "content": past_trial.full_response or past_trial.answer})
            
        return messages

    def run_single_turn(self, session, trial, completed_trials=None):
        settings_snapshot = session.run.settings_snapshot
        allow_reasoning = settings_snapshot.get('llm_settings', {}).get('allow_reasoning', False)
        
        history_key = self._get_history_key(session.id)
        history_json = redis_client.get(history_key)
        
        if history_json:
            history = json.loads(history_json)
        else:
            history = self._reconstruct_history(session, completed_trials)

        # 1. Query Reformulation / Generation
        system_prompt = PROMPTS["rag_system"]
        if allow_reasoning:
            system_prompt += PROMPTS["reasoning_instruction"]

        if trial.trial_number == 1:
            if allow_reasoning:
                instruction = PROMPTS["rag_query_generation_cot"].format(question=session.question)
            else:
                instruction = PROMPTS["rag_query_generation"].format(question=session.question)
        else:
            # Add a "correction" context if it's a retry
            history.append({"role": "user", "content": "Your previous answer was incorrect."})
            if allow_reasoning:
                 instruction = PROMPTS["rag_reformulation_cot"]
            else:
                 instruction = PROMPTS["rag_reformulation"]

        # Save instruction (System + User) if not already saved
        if not trial.query_instruction:
            full_instr = f"*** SYSTEM PROMPT ***\n{system_prompt}\n\n*** USER INPUT ***\n{instruction}"
            trial.query_instruction = full_instr
            trial.save()
            print(f"DEBUG: Saved instruction for trial {trial.id}: {full_instr[:50]}...")
        else:
            print(f"DEBUG: Instruction already exists for trial {trial.id}")

        if not trial.search_query:
            # The model sees the history of instructions and previous answers
            reformulation_messages = history + [{"role": "user", "content": instruction}]
            
            # Use allow_reasoning=False here because we want to handle extraction manually for 'Query:'
            raw_query_response, _ = self.get_llm_response(
                reformulation_messages, 
                temperature=0.0, 
                allow_reasoning=False 
            )

            if allow_reasoning:
                from ..utils import extract_query
                trial.search_query = extract_query(raw_query_response)
                trial.query_full_response = raw_query_response
            else:
                trial.search_query = raw_query_response.strip().strip('"').strip("'")
            
            trial.search_results = self.search_engine.search(trial.search_query)
            trial.query_instruction = instruction
            trial.save()

        # 2. Answer Question
        messages = self._construct_messages(session, trial, completed_trials)
        
        # Capture the last user message (the answer instruction)
        answer_instruction = ""
        if messages and messages[-1]["role"] == "user":
            answer_instruction = messages[-1]["content"]
        trial.final_answer_instruction = answer_instruction

        print(f"DEBUG: run_single_turn allow_reasoning={allow_reasoning}")
        if allow_reasoning and messages:
             print(f"DEBUG: Last message content: {messages[-1]['content'][-200:]}")

        answer, full_response = self.get_llm_response(messages, allow_reasoning=allow_reasoning)
        
        print(f"DEBUG: full_response start: {full_response[:100]}")
        
        is_correct = check_answer_llm(
            session.question, 
            session.ground_truths, 
            answer, 
            client=self.client, 
            model=self.model
        )
        
        # 3. Update Trial State
        trial.answer = answer
        trial.full_response = full_response
        trial.is_correct = is_correct
        trial.feedback = "Correct" if is_correct else "Incorrect"
        trial.status = 'completed'
        trial.save()

        # 4. Update Persistence Cache
        # We save the full turn sequence (Query Instruction -> Assistant Query -> Results -> Assistant Answer)
        new_history = messages + [{"role": "assistant", "content": full_response or answer}]
        redis_client.set(history_key, json.dumps(new_history), ex=3600)

        return answer, is_correct, trial.search_results