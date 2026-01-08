import json
import asyncio
from decouple import config
from openai import AsyncOpenAI
from django.core.management.base import BaseCommand
from task_manager.utils import _normalize


class Command(BaseCommand):
    help = "Tests the reasonability of LLM-as-a-judge for answer validation."

    def add_arguments(self, parser):
        parser.add_argument(
            "--concurrent",
            action="store_true",
            help="Generate and validate answers concurrently.",
        )
        parser.add_argument(
            "--source_path", type=str, help="Path to the source QA dataset."
        )
        parser.add_argument(
            "--output_path",
            type=str,
            help="(Optional) Path to save the detailed results jsonl file.",
        )
        parser.add_argument(
            "--workers", type=int, default=5, help="Number of concurrent workers."
        )
        parser.add_argument(
            "--retries",
            type=int,
            default=3,
            help="Number of retries for failed API calls.",
        )

    def handle(self, *args, **options):
        if options["concurrent"]:
            if not options["source_path"]:
                self.stderr.write(
                    self.style.ERROR(
                        "For --concurrent, you must provide --source_path."
                    )
                )
                return
            asyncio.run(
                self.run_concurrently(
                    options["source_path"],
                    options["output_path"],
                    options["workers"],
                    options["retries"],
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING("This command now only supports --concurrent mode.")
            )

    async def run_concurrently(
        self, source_path, output_path, num_workers, max_retries
    ):
        self.stdout.write(
            f"Starting concurrent generation and validation with {num_workers} workers and {max_retries} retries."
        )

        try:
            with open(source_path, "r") as f:
                questions = [json.loads(line) for line in f]
        except FileNotFoundError:
            self.stderr.write(
                self.style.ERROR(f"Dataset file not found at: {source_path}")
            )
            return

        client = AsyncOpenAI(
            base_url=config("LLM_BASE_URL", default=None),
            api_key=config("LLM_API_KEY", default=None),
        )
        model = config("LLM_MODEL", default="gpt-4o")

        queue = asyncio.Queue()
        for i, q in enumerate(questions):
            queue.put_nowait((i + 1, q))

        results = {"agreements": 0, "disagreements": 0, "errors": 0}

        output_file = open(output_path, "w") if output_path else None
        file_lock = asyncio.Lock() if output_file else None

        tasks = [
            asyncio.create_task(
                self.worker(
                    f"worker-{i}",
                    client,
                    model,
                    queue,
                    results,
                    output_file,
                    file_lock,
                    max_retries,
                )
            )
            for i in range(num_workers)
        ]

        await queue.join()

        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

        if output_file:
            output_file.close()
            self.stdout.write(
                self.style.SUCCESS(f"Detailed results saved to {output_path}")
            )

        self.stdout.write(self.style.SUCCESS("\n--- Concurrent Run Summary ---"))
        total_processed = results["agreements"] + results["disagreements"]
        self.stdout.write(f"Total questions processed: {total_processed}")
        self.stdout.write(f"Errors: {results['errors']}")
        self.stdout.write(f"Agreements: {results['agreements']}")
        self.stdout.write(f"Disagreements: {results['disagreements']}")
        if total_processed > 0:
            agreement_rate = (results["agreements"] / total_processed) * 100
            self.stdout.write(f"Agreement Rate: {agreement_rate:.2f}%")

    async def worker(
        self, name, client, model, queue, results, output_file, file_lock, max_retries
    ):
        while True:
            try:
                item_idx, item = await queue.get()
                question = item["question"]
                authentic_answers = item["answer"]

                self.stdout.write(
                    f"[{name}] Processing question #{item_idx}: {question}"
                )

                # 1. Generate Answer
                generated_answer = await self.generate_llm_answer(
                    client, model, question, max_retries
                )
                if generated_answer is None:
                    results["errors"] += 1
                    queue.task_done()
                    continue

                # 2. Rule-based check
                is_correct_rule = self.check_answer_rule_sync(
                    question, authentic_answers, generated_answer
                )

                # 3. LLM-as-a-judge check
                is_correct_llm = await self.check_answer_llm_async(
                    client,
                    model,
                    question,
                    authentic_answers,
                    generated_answer,
                    max_retries,
                )

                # 4. Compare and log
                if is_correct_rule == is_correct_llm:
                    results["agreements"] += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"-> AGREEMENT on question #{item_idx} (Rule: {is_correct_rule}, LLM: {is_correct_llm})"
                        )
                    )
                else:
                    results["disagreements"] += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f"-> DISAGREEMENT on question #{item_idx} (Rule: {is_correct_rule}, LLM: {is_correct_llm})"
                        )
                    )

                # 5. Write to output file if provided
                if output_file and file_lock:
                    output_record = {
                        "question": question,
                        "authentic_answers": authentic_answers,
                        "llm_generated_answer": generated_answer,
                        "rule_based_correct": is_correct_rule,
                        "llm_judge_correct": is_correct_llm,
                        "agreement": is_correct_rule == is_correct_llm,
                    }
                    async with file_lock:
                        output_file.write(json.dumps(output_record) + "\n")

                queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.stderr.write(
                    self.style.ERROR(f"[{name}] Error processing item: {e}")
                )
                results["errors"] += 1
                queue.task_done()

    async def generate_llm_answer(self, client, model, question_text, max_retries):
        prompt = f"""Your task is to answer the following question. Follow these rules strictly:
1.  Your answer must be an exact match to the correct answer.
2.  Do not include any punctuation.
3.  Do not include any extra words or sentences.
Question: {question_text}
Answer:"""
        for attempt in range(max_retries + 1):
            try:
                completion = await client.chat.completions.create(
                    model=model, messages=[{"role": "user", "content": prompt}], temperature=0
                )
                if (
                    completion.choices
                    and completion.choices[0].message
                    and completion.choices[0].message.content
                ):
                    return completion.choices[0].message.content.strip()
                else:
                    self.stderr.write(
                        self.style.ERROR(
                            f"Error: LLM returned empty content for question '{question_text}'"
                        )
                    )
                    # This is considered a final failure for this attempt, but we can still retry
            except Exception as e:
                self.stderr.write(
                    self.style.WARNING(
                        f"Attempt {attempt + 1}/{max_retries + 1} failed for '{question_text}': {e}"
                    )
                )

            if attempt < max_retries:
                wait_time = 2**attempt
                self.stdout.write(f"Retrying in {wait_time} seconds...")
                await asyncio.sleep(wait_time)

        self.stderr.write(
            self.style.ERROR(
                f"All {max_retries + 1} attempts failed for question '{question_text}'."
            )
        )
        return None

    def check_answer_rule_sync(self, question, authentic_answers, user_answer):
        normalized_user_answer = _normalize(user_answer)
        for answer in authentic_answers:
            if normalized_user_answer == _normalize(answer):
                return True
        return False

    async def check_answer_llm_async(
        self, client, model, question, authentic_answers, user_answer, max_retries
    ):
        authentic_answers_formatted = "\n- ".join(authentic_answers)
        prompt = f"""You are a meticulous and fair evaluator. Your task is to compare a `User's Answer` to a list of `Authentic Answers` for a given `Question` and determine if it is correct.

**Instructions:**
1.  **Correctness Criteria:** The `User's Answer` is correct if it is semantically equivalent to **any one** of the answers in the `Authentic Answers` list.
2.  **Tolerances:** Your comparison must be case-insensitive. You should ignore minor differences in punctuation (e.g., commas, periods) and whitespace. For example, "New York NY" should be considered a match for "New York, NY".
3.  **Completeness:** The user's answer must not be missing essential information. For example, if an authentic answer is "Michael Jordan", "Jordan" would be considered incorrect because it is incomplete.
4.  **Strict Adherence:** Base your judgment *only* on the provided text. Do not use external knowledge.
5.  **Output Format:** Your response must be a single word: `yes` or `no`.

**Evaluation Task:**

**Question:** "{question}"

**Authentic Answers (any of the following are correct):**
- {authentic_answers_formatted}

**User's Answer:** "{user_answer}"

Is the user's answer correct?"""
        for attempt in range(max_retries + 1):
            try:
                completion = await client.chat.completions.create(
                    model=model, messages=[{"role": "user", "content": prompt}], temperature=0
                )
                if (
                    completion.choices
                    and completion.choices[0].message
                    and completion.choices[0].message.content
                ):
                    judgment = completion.choices[0].message.content.strip().lower()
                    return judgment == "yes"
            except Exception as e:
                self.stderr.write(
                    self.style.WARNING(
                        f"LLM Judge Attempt {attempt + 1}/{max_retries + 1} failed for '{question}': {e}"
                    )
                )

            if attempt < max_retries:
                wait_time = 2**attempt
                self.stdout.write(f"Retrying LLM Judge in {wait_time} seconds...")
                await asyncio.sleep(wait_time)

        self.stderr.write(
            self.style.ERROR(
                f"LLM Judge failed for question '{question}' after {max_retries + 1} attempts."
            )
        )
        return False
