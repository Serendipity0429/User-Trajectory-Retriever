import json
import os
import openai
from datetime import datetime
from task_manager.utils import check_answer_rule, check_answer_llm, redis_client
from .search_utils import get_search_engine
from .models import (
    LLMSettings, RagSettings, BenchmarkDataset, 
    VanillaLLMAdhocRun, VanillaLLMAdhocResult,
    RagAdhocRun, RagAdhocResult,
    MultiTurnSessionGroup, VanillaLLMMultiTurnSession, VanillaLLMMultiTurnTrial,
    RAGMultiTurnSession, RAGMultiTurnTrial
)

HARD_QUESTIONS_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'hard_questions_refined.jsonl')

class BasePipeline:
    def __init__(self, base_url, api_key, model, pipeline_id=None, dataset_id=None):
        self.client = openai.OpenAI(base_url=base_url, api_key=api_key)
        self.model = model
        self.pipeline_id = pipeline_id
        self.dataset_id = dataset_id
        self.redis_prefix = "pipeline_active"

    def check_active(self):
        if not self.pipeline_id:
            return True
        return redis_client.get(f"{self.redis_prefix}:{self.pipeline_id}")

    def stop_token(self):
        if self.pipeline_id:
            redis_client.delete(f"{self.redis_prefix}:{self.pipeline_id}")

    def load_questions(self):
        file_path = None
        if self.dataset_id:
            try:
                dataset = BenchmarkDataset.objects.get(pk=self.dataset_id)
                if dataset.file and os.path.exists(dataset.file.path):
                    file_path = dataset.file.path
            except BenchmarkDataset.DoesNotExist:
                pass
                
        if file_path is None:
            file_path = HARD_QUESTIONS_PATH
            
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                for line in f:
                    try:
                        data = json.loads(line)
                        if 'answer' in data and 'ground_truths' not in data:
                            data['ground_truths'] = data['answer']
                        yield data
                    except json.JSONDecodeError:
                        continue

    def run(self):
        """
        Generator that yields JSON string responses (one per line)
        """
        yield json.dumps({'is_meta': True, 'type': 'info', 'message': 'Pipeline started'}) + "\n"
        # Subclasses should override this and yield results
        pass

class VanillaLLMAdhocPipeline(BasePipeline):
    def __init__(self, base_url, api_key, model, pipeline_id=None, dataset_id=None):
        super().__init__(base_url, api_key, model, pipeline_id, dataset_id)
        self.redis_prefix = "vanilla_llm_adhoc_pipeline_active"

    def run(self):
        settings = LLMSettings.load()
        run_name = f"Vanilla LLM Ad-hoc Run {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        run = VanillaLLMAdhocRun.objects.create(
            name=run_name,
            llm_settings=settings,
            total_questions=0,
            correct_answers=0
        )
        
        yield json.dumps({'is_meta': True, 'type': 'run_created', 'run_id': run.id, 'name': run_name}) + "\n"
        
        total_count = 0
        correct_count = 0

        for data in self.load_questions():
            if not self.check_active():
                break

            question = data['question']
            ground_truths = data.get('ground_truths', [])

            try:
                answer_prompt = f"""Your task is to answer the following question. Follow these rules strictly:
1.  Your answer must be an exact match to the correct answer.
2.  Do not include any punctuation.
3.  Do not include any extra words or sentences.

For example:
Question: What is the capital of France?
Correct Answer: Paris

Incorrect Answers:
- \"The capital of France is Paris.\" (contains extra words)
- \"Paris is the capital of France.\" (contains extra words)
- \"Paris.\" (contains a period)

Now, answer the following question:
Question: {question}
Answer:"""
                
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": answer_prompt}]
                )
                answer = response.choices[0].message.content
                
                rule_result = check_answer_rule(question, ground_truths, answer)
                llm_result = check_answer_llm(question, ground_truths, answer, client=self.client, model=self.model)

                VanillaLLMAdhocResult.objects.create(
                    run=run,
                    question=question,
                    ground_truths=ground_truths,
                    answer=answer,
                    is_correct_rule=rule_result,
                    is_correct_llm=llm_result
                )

                if llm_result:
                    correct_count += 1
                total_count += 1

                yield json.dumps({
                    'question': question,
                    'answer': answer,
                    'ground_truths': ground_truths,
                    'rule_result': rule_result,
                    'llm_result': llm_result
                }) + "\n"

            except Exception as e:
                yield json.dumps({'error': str(e), 'question': question}) + "\n"

        run.total_questions = total_count
        run.correct_answers = correct_count
        run.accuracy = (correct_count / total_count * 100) if total_count > 0 else 0
        run.save()
        self.stop_token()


class RagAdhocPipeline(BasePipeline):
    def __init__(self, base_url, api_key, model, rag_prompt_template, pipeline_id=None, dataset_id=None):
        super().__init__(base_url, api_key, model, pipeline_id, dataset_id)
        self.prompt_template = rag_prompt_template
        self.search_engine = get_search_engine()
        self.redis_prefix = "rag_adhoc_pipeline_active"

    def run(self):
        llm_settings = LLMSettings.load()
        rag_settings = RagSettings.load()
        run_name = f"RAG Ad-hoc Run {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        run = RagAdhocRun.objects.create(
            name=run_name,
            llm_settings=llm_settings,
            rag_settings=rag_settings,
            total_questions=0,
            correct_answers=0
        )
        
        yield json.dumps({'is_meta': True, 'type': 'run_created', 'run_id': run.id, 'name': run_name}) + "\n"
        
        total_count = 0
        correct_count = 0

        for data in self.load_questions():
            if not self.check_active():
                break

            question = data['question']
            ground_truths = data.get('ground_truths', [])

            try:
                search_results = self.search_engine.search(question)
                formatted_results = "\n".join([f"{i+1}. {r.get('title', '')}\n{r.get('snippet', '')}" for i, r in enumerate(search_results)]) if search_results else "No results found."
                
                prompt = self.prompt_template.replace('{question}', question).replace('{search_results}', formatted_results)
                
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}]
                )
                answer = response.choices[0].message.content
                
                rule_result = check_answer_rule(question, ground_truths, answer)
                llm_result = check_answer_llm(question, ground_truths, answer, client=self.client, model=self.model)

                RagAdhocResult.objects.create(
                    run=run,
                    question=question,
                    ground_truths=ground_truths,
                    answer=answer,
                    is_correct_rule=rule_result,
                    is_correct_llm=llm_result,
                    num_docs_used=len(search_results),
                    search_results=search_results
                )

                if llm_result:
                    correct_count += 1
                total_count += 1

                yield json.dumps({
                    'question': question,
                    'answer': answer,
                    'ground_truths': ground_truths,
                    'rule_result': rule_result,
                    'llm_result': llm_result,
                    'num_docs_used': len(search_results),
                    'search_results': search_results
                }) + "\n"

            except Exception as e:
                yield json.dumps({'error': str(e), 'question': question}) + "\n"

        run.total_questions = total_count
        run.correct_answers = correct_count
        run.accuracy = (correct_count / total_count * 100) if total_count > 0 else 0
        run.save()
        self.stop_token()


class BaseMultiTurnPipeline(BasePipeline):
    def __init__(self, base_url, api_key, model, max_retries, pipeline_id=None, dataset_id=None):
        super().__init__(base_url, api_key, model, pipeline_id, dataset_id)
        self.max_retries = max_retries
        self.redis_prefix = "multi_turn_pipeline_active"

    def create_session(self, settings, question_text, ground_truths, group):
        raise NotImplementedError("Subclasses must implement create_session")

    def create_trial(self, session, trial_number):
        raise NotImplementedError("Subclasses must implement create_trial")

    def run(self):
        group_name = f"Pipeline Run ({self.__class__.__name__}) - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        group = MultiTurnSessionGroup.objects.create(name=group_name)
        settings = LLMSettings.load()

        for data in self.load_questions():
            if not self.check_active():
                break

            question_text = data['question']
            ground_truths = data.get('ground_truths', [])
            
            try:
                session = self.create_session(settings, question_text, ground_truths, group)

                is_session_completed = False
                trial_number = 1
                final_is_correct = False
                final_answer = ""
                
                while trial_number <= self.max_retries and not is_session_completed:
                    if not self.check_active():
                        break

                    trial = self.create_trial(session, trial_number)
                    messages = self._construct_messages(session, trial)
                    
                    try:
                        response = self.client.chat.completions.create(
                            model=self.model,
                            messages=messages
                        )
                        answer = response.choices[0].message.content
                    except Exception as e:
                        trial.status = 'error'
                        trial.save()
                        raise e

                    is_correct = check_answer_llm(session.question, session.ground_truths, answer, client=self.client, model=self.model)

                    trial.answer = answer
                    trial.is_correct = is_correct
                    trial.feedback = "Correct" if is_correct else "Incorrect"
                    trial.status = 'completed'
                    trial.save()

                    final_answer = answer
                    final_is_correct = is_correct

                    if is_correct:
                        is_session_completed = True
                    else:
                        trial_number += 1
                
                session.is_completed = True
                session.save()

                yield json.dumps({
                    'question': question_text,
                    'correct': final_is_correct,
                    'trials': trial_number if final_is_correct else (trial_number - 1),
                    'session_id': session.id,
                    'final_answer': final_answer,
                    'ground_truths': ground_truths,
                    'max_retries': self.max_retries,
                    'group_name': group_name,
                    'group_id': group.id
                }) + "\n"

            except Exception as e:
                yield json.dumps({'error': str(e), 'question': question_text}) + "\n"
        
        self.stop_token()

    def run_single_turn(self, session, trial):
        """
        Executes a single turn for a given session and trial object.
        """
        messages = self._construct_messages(session, trial)
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages
            )
            answer = response.choices[0].message.content
        except Exception as e:
            trial.status = 'error'
            trial.save()
            raise e

        # Logic for checking answer
        is_correct = check_answer_llm(session.question, session.ground_truths, answer, client=self.client, model=self.model)

        trial.answer = answer
        trial.is_correct = is_correct
        trial.feedback = "Correct" if is_correct else "Incorrect"
        trial.status = 'completed'
        trial.save()
        
        return answer, is_correct, getattr(trial, 'search_results', [])

    def _construct_messages(self, session, trial):
        raise NotImplementedError("Subclasses must implement _construct_messages")


class VanillaLLMMultiTurnPipeline(BaseMultiTurnPipeline):
    def __init__(self, base_url, api_key, model, max_retries, pipeline_id=None, dataset_id=None):
        super().__init__(base_url, api_key, model, max_retries, pipeline_id, dataset_id)
        self.redis_prefix = "vanilla_llm_multi_turn_pipeline_active"

    def create_session(self, settings, question_text, ground_truths, group):
        return VanillaLLMMultiTurnSession.objects.create(
            llm_settings=settings,
            question=question_text,
            ground_truths=ground_truths,
            group=group,
            run_tag=self.pipeline_id
        )

    def create_trial(self, session, trial_number):
        return VanillaLLMMultiTurnTrial.objects.create(
            session=session,
            trial_number=trial_number,
            status='processing'
        )

    def _construct_messages(self, session, trial):
        trial_number = trial.trial_number
        messages = []
        
        if trial_number == 1:
            answer_prompt = f"""Your task is to answer the following question. Follow these rules strictly:
1.  Your answer must be an exact match to the correct answer.
2.  Do not include any punctuation.
3.  Do not include any extra words or sentences.
Question: {session.question}
Answer:"""
            messages.append({"role": "user", "content": answer_prompt})
        else:
            messages.append({"role": "user", "content": f"Question: {session.question}"})
            prev_trials = session.trials.filter(trial_number__lt=trial_number).order_by('trial_number')
            for prev_trial in prev_trials:
                if prev_trial.answer:
                    messages.append({"role": "assistant", "content": prev_trial.answer})
                if prev_trial.is_correct == False:
                    messages.append({"role": "user", "content": "Your previous answer was incorrect."})
            
            strict_rules = """Your task is to answer the question again. Follow these rules strictly:
1.  Your answer must be an exact match to the correct answer.
2.  Do not include any punctuation.
3.  Do not include any extra words or sentences.
Answer:"""
            messages.append({"role": "user", "content": strict_rules})
            
        return messages


class RagMultiTurnPipeline(BaseMultiTurnPipeline):
    def __init__(self, base_url, api_key, model, max_retries, reformulation_strategy='no_reform', pipeline_id=None, dataset_id=None):
        super().__init__(base_url, api_key, model, max_retries, pipeline_id, dataset_id)
        self.search_engine = get_search_engine()
        self.reformulation_strategy = reformulation_strategy
        self.redis_prefix = f"rag_multi_turn_{self.reformulation_strategy}_pipeline_active"

    def create_session(self, settings, question_text, ground_truths, group):
        rag_settings = RagSettings.load()
        return RAGMultiTurnSession.objects.create(
            llm_settings=settings,
            rag_settings=rag_settings,
            question=question_text,
            ground_truths=ground_truths,
            group=group,
            reformulation_strategy=self.reformulation_strategy,
            run_tag=self.pipeline_id
        )

    def create_trial(self, session, trial_number):
        return RAGMultiTurnTrial.objects.create(
            session=session,
            trial_number=trial_number,
            status='processing'
        )

    def _construct_messages(self, session, trial):
        trial_number = trial.trial_number
        messages = []
        current_search_query = session.question
        
        if self.reformulation_strategy == 'reform' and trial_number > 1:
            reform_messages = [{"role": "system", "content": "You are a helpful assistant that reformulates search queries based on conversation history."}]
            reform_messages.append({"role": "user", "content": f"Original Question: {session.question}"})
            
            prev_trials = session.trials.filter(trial_number__lt=trial_number).order_by('trial_number')
            for prev_trial in prev_trials:
                if prev_trial.answer:
                    reform_messages.append({"role": "assistant", "content": f"Previous Answer: {prev_trial.answer}"})
                reform_messages.append({"role": "user", "content": "The previous answer was incorrect."})
            
            reform_messages.append({"role": "user", "content": "Based on the history, provide a better search query to find the correct answer. Output ONLY the query."})
            
            try:
                reform_response = self.client.chat.completions.create(
                    model=self.model,
                    messages=reform_messages
                )
                current_search_query = reform_response.choices[0].message.content.strip()
            except Exception as e:
                print(f"Reformulation failed: {e}")
                pass

        search_results = self.search_engine.search(current_search_query)
        formatted_results = "\n".join([f"{i+1}. {r.get('title', '')}\n{r.get('snippet', '')}" for i, r in enumerate(search_results)]) if search_results else "No results found."
        
        # Save search info to the passed trial object directly
        trial.search_query = current_search_query
        trial.search_results = search_results
        trial.save()

        system_prompt = f"Context from web search (Query: {current_search_query}):\n{formatted_results}\n\n"
        messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": f"Question: {session.question}"})
        
        prev_trials = session.trials.filter(trial_number__lt=trial_number).order_by('trial_number')
        for prev_trial in prev_trials:
            if prev_trial.answer:
                messages.append({"role": "assistant", "content": prev_trial.answer})
            if prev_trial.is_correct == False:
                messages.append({"role": "user", "content": "Your previous answer was incorrect."})

        messages.append({"role": "user", "content": "Answer the question based on the context. Return ONLY the exact answer."})
        
        return messages