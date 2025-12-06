import os
import json
import openai
import traceback
from datetime import datetime
from task_manager.utils import check_answer_rule, check_answer_llm, redis_client
from .search_utils import get_search_engine
from .models import (
    LLMSettings, 
    RagSettings, 
    InteractiveSession, 
    InteractiveTrial, 
    InteractiveSessionGroup,
    AdhocRun,
    AdhocSessionResult,
    RagBenchmarkRun,
    RagBenchmarkResult
)

# Constants
HARD_QUESTIONS_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'hard_questions_refined.jsonl')

def load_questions(file_path=None):
    """
    Generator that yields question data from a JSONL file.
    """
    if file_path is None:
        file_path = HARD_QUESTIONS_PATH
        
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            for line in f:
                data = json.loads(line)
                # Normalize ground truths
                if 'answer' in data and 'ground_truths' not in data:
                    data['ground_truths'] = data['answer']
                yield data

def check_pipeline_active(pipeline_id, prefix):
    """
    Checks if the pipeline cancellation token exists in Redis.
    """
    if not pipeline_id:
        return True
    return redis_client.get(f"{prefix}:{pipeline_id}")

def stop_pipeline_token(pipeline_id, prefix):
    """
    Deletes the pipeline cancellation token from Redis.
    """
    if pipeline_id:
        redis_client.delete(f"{prefix}:{pipeline_id}")

def adhoc_pipeline_stream(base_url, api_key, model, pipeline_id=None):
    """
    Stream generator for the Ad-hoc QA pipeline.
    """
    client = openai.OpenAI(base_url=base_url, api_key=api_key)
    prefix = "adhoc_pipeline_active"
    
    # Create Run
    settings = LLMSettings.load()
    run_name = f"Adhoc Run {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    run = AdhocRun.objects.create(
        name=run_name,
        settings=settings,
        total_questions=0,
        correct_answers=0
    )
    
    # Yield info
    yield json.dumps({'is_meta': True, 'type': 'run_created', 'run_id': run.id, 'name': run_name}) + "\n"
    
    total_count = 0
    correct_count = 0

    def process_line(data):
        if not check_pipeline_active(pipeline_id, prefix):
            return None

        question = data['question']
        ground_truths = data.get('answer', data.get('ground_truths', []))

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
            
            if not check_pipeline_active(pipeline_id, prefix):
                return None

            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": answer_prompt}]
            )
            answer = response.choices[0].message.content
            
            rule_result = check_answer_rule(question, ground_truths, answer)

            if not check_pipeline_active(pipeline_id, prefix):
                return None

            llm_result = check_answer_llm(question, ground_truths, answer, client=client, model=model)

            # Save result
            AdhocSessionResult.objects.create(
                run=run,
                question=question,
                ground_truths=ground_truths,
                answer=answer,
                is_correct_rule=rule_result,
                is_correct_llm=llm_result
            )

            result_data = {
                'question': question,
                'answer': answer,
                'ground_truths': ground_truths,
                'rule_result': rule_result,
                'llm_result': llm_result
            }
            
            return result_data

        except Exception as e:
            error_data = {'error': str(e), 'question': question}
            return error_data

    for data in load_questions():
        result = process_line(data)
        if result is None:
            break
            
        if 'error' not in result:
            total_count += 1
            if result.get('llm_result'):
                correct_count += 1
                
        yield json.dumps(result) + "\n"
    
    # Update Run stats
    run.total_questions = total_count
    run.correct_answers = correct_count
    run.accuracy = (correct_count / total_count * 100) if total_count > 0 else 0
    run.save()

    stop_pipeline_token(pipeline_id, prefix)

def rag_pipeline_stream(base_url, api_key, model, prompt_template, pipeline_id=None):
    """
    Stream generator for the RAG pipeline.
    """
    client = openai.OpenAI(base_url=base_url, api_key=api_key)
    search_engine = get_search_engine()
    prefix = "rag_pipeline_active"
    
    # Create Run
    llm_settings = LLMSettings.load()
    rag_settings = RagSettings.load()
    run_name = f"RAG Run {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    run = RagBenchmarkRun.objects.create(
        name=run_name,
        llm_settings=llm_settings,
        rag_settings=rag_settings,
        total_questions=0,
        correct_answers=0
    )
    
    # Yield info
    yield json.dumps({'is_meta': True, 'type': 'run_created', 'run_id': run.id, 'name': run_name}) + "\n"
    
    total_count = 0
    correct_count = 0

    def process_line(data):
        if not check_pipeline_active(pipeline_id, prefix):
            return None

        question = data['question']
        ground_truths = data.get('answer', data.get('ground_truths', []))

        try:
            # 1. Web Search
            if not check_pipeline_active(pipeline_id, prefix): return None
            search_results = search_engine.search(question)
            formatted_results = "\n".join([f"{i+1}. {r.get('title', '')}\n{r.get('snippet', '')}" for i, r in enumerate(search_results)]) if search_results else "No results found."
            
            # 2. Construct Prompt
            if not check_pipeline_active(pipeline_id, prefix): return None
            prompt = prompt_template.replace('{question}', question).replace('{search_results}', formatted_results)
            
            # 3. Call LLM
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}]
            )
            answer = response.choices[0].message.content
            
            # 4. Evaluate
            rule_result = check_answer_rule(question, ground_truths, answer)
            llm_result = check_answer_llm(question, ground_truths, answer, client=client, model=model)

            # Save result
            RagBenchmarkResult.objects.create(
                run=run,
                question=question,
                ground_truths=ground_truths,
                answer=answer,
                is_correct_rule=rule_result,
                is_correct_llm=llm_result,
                num_docs_used=len(search_results),
                search_results=search_results
            )

            result_data = {
                'question': question,
                'answer': answer,
                'ground_truths': ground_truths,
                'rule_result': rule_result,
                'llm_result': llm_result,
                'num_docs_used': len(search_results),
                'search_results': search_results
            }
            
            return result_data

        except Exception as e:
            error_data = {'error': str(e), 'question': question}
            return error_data

    for data in load_questions():
        result = process_line(data)
        if result is None:
            break
        
        if 'error' not in result:
            total_count += 1
            if result.get('llm_result'):
                correct_count += 1

        yield json.dumps(result) + "\n"

    # Update Run stats
    run.total_questions = total_count
    run.correct_answers = correct_count
    run.accuracy = (correct_count / total_count * 100) if total_count > 0 else 0
    run.save()

    stop_pipeline_token(pipeline_id, prefix)

def interactive_pipeline_stream(base_url, api_key, model, max_retries, pipeline_id=None):
    """
    Stream generator for the Interactive pipeline (saves to DB).
    """
    client = openai.OpenAI(base_url=base_url, api_key=api_key)
    prefix = "interactive_pipeline_active"
    
    group_name = f"Pipeline Run - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    group = InteractiveSessionGroup.objects.create(name=group_name)
    
    def process_question(data):
        if not check_pipeline_active(pipeline_id, prefix):
            return None

        question_text = data['question']
        ground_truths = data.get('answer', data.get('ground_truths', []))
        
        try:
            # Create Session
            settings = LLMSettings.load() 
            session = InteractiveSession.objects.create(
                settings=settings,
                question=question_text,
                ground_truths=ground_truths,
                pipeline_type='interactive',
                group=group
            )

            is_session_completed = False
            trial_number = 1
            final_is_correct = False
            final_answer = ""
            
            while trial_number <= max_retries and not is_session_completed:
                if not check_pipeline_active(pipeline_id, prefix):
                    return None

                trial = InteractiveTrial.objects.create(
                    session=session,
                    trial_number=trial_number,
                    status='processing'
                )

                # Construct Messages
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

                try:
                    response = client.chat.completions.create(
                        model=model,
                        messages=messages
                    )
                    answer = response.choices[0].message.content
                except Exception as e:
                    trial.status = 'error'
                    trial.save()
                    raise e

                is_correct = check_answer_llm(session.question, session.ground_truths, answer, client=client, model=model)

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

            result_data = {
                'question': question_text,
                'correct': final_is_correct,
                'trials': trial_number if final_is_correct else (trial_number - 1),
                'session_id': session.id,
                'final_answer': final_answer,
                'ground_truths': ground_truths,
                'max_retries': max_retries,
                'group_name': group_name,
                'group_id': group.id
            }
            return json.dumps(result_data) + "\n"

        except Exception as e:
            error_data = {'error': str(e), 'question': question_text}
            return json.dumps(error_data) + "\n"

    for data in load_questions():
        result = process_question(data)
        if result is None:
            break
        yield result
    
    stop_pipeline_token(pipeline_id, prefix)
