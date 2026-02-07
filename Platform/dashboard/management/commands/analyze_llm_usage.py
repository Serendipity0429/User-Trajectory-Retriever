"""
Django management command to analyze LLM usage in task trajectories.

Searches for LLM service URLs in:
  - Evidence URLs (Justification.url)
  - Visited URLs (Webpage.url)

Usage:
    python manage.py analyze_llm_usage
    python manage.py analyze_llm_usage --summary-only
    python manage.py analyze_llm_usage --output json
"""

import re
import json
from collections import defaultdict

from django.core.management.base import BaseCommand

from task_manager.models import Task, Justification, Webpage


# URL patterns for LLM services (only match URLs to avoid false positives)
# e.g., "gemini" could be zodiac sign, "claude" could be a person's name
LLM_URL_PATTERNS = {
    # Major LLMs
    "chatgpt": r"chat\.openai\.com|chatgpt\.com|openai\.com",
    "claude": r"claude\.ai|anthropic\.com",
    "gemini": r"gemini\.google\.com|bard\.google\.com|aistudio\.google\.com",
    "copilot": r"copilot\.microsoft\.com|bing\.com/chat",

    # Chinese LLMs
    "doubao": r"doubao\.com",
    "deepseek": r"deepseek\.com|chat\.deepseek\.com",
    "qwen": r"tongyi\.aliyun\.com|qianwen\.com|qwen\.",
    "kimi": r"kimi\.moonshot\.cn|moonshot\.cn",
    "wenxin": r"yiyan\.baidu\.com",
    "zhipu": r"chatglm\.cn|zhipuai\.cn",
    "spark": r"xinghuo\.xfyun\.cn",
    "yuanbao": r"yuanbao\.tencent\.com",

    # Other AI assistants
    "perplexity": r"perplexity\.ai",
    "poe": r"poe\.com",
    "phind": r"phind\.com",
    "you.com": r"you\.com/search",
}


class Command(BaseCommand):
    help = "Analyze which users refer to LLMs for answering questions"

    def add_arguments(self, parser):
        parser.add_argument(
            "--summary-only",
            action="store_true",
            help="Only show summary statistics, skip detailed results",
        )
        parser.add_argument(
            "--output",
            choices=["text", "json"],
            default="text",
            help="Output format (default: text)",
        )

    def handle(self, *args, **options):
        summary_only = options["summary_only"]
        output_format = options["output"]

        if output_format == "json":
            self._run_json_output()
        else:
            self._run_text_output(summary_only)

    def _search_in_url(self, url):
        """Search for LLM URL patterns, return matched patterns."""
        if not url:
            return []

        url_lower = url.lower()
        matches = []
        for name, pattern in LLM_URL_PATTERNS.items():
            if re.search(pattern, url_lower, re.IGNORECASE):
                matches.append(name)
        return matches

    def _analyze_justifications(self):
        """Analyze Justification URLs for LLM services."""
        results = defaultdict(list)

        justifications = Justification.objects.select_related(
            "belong_task_trial__belong_task__user"
        ).all()

        for j in justifications:
            url = j.url or ""
            url_matches = self._search_in_url(url)

            if url_matches:
                user = j.belong_task_trial.belong_task.user
                results[user.username].append({
                    "justification_id": j.id,
                    "trial_id": j.belong_task_trial.id,
                    "task_id": j.belong_task_trial.belong_task.id,
                    "url": url,
                    "llm_matches": url_matches,
                })

        return dict(results)

    def _analyze_webpages(self):
        """Analyze Webpage URLs for LLM service visits."""
        results = defaultdict(list)

        # Optimize: only load required fields, exclude large JSON fields
        webpages = Webpage.objects.select_related("user", "belong_task").only(
            'id', 'url', 'title', 'dwell_time',
            'user__id', 'user__username',
            'belong_task__id'
        ).iterator(chunk_size=500)

        for wp in webpages:
            url = wp.url or ""
            url_matches = self._search_in_url(url)

            if url_matches:
                results[wp.user.username].append({
                    "webpage_id": wp.id,
                    "task_id": wp.belong_task.id,
                    "url": url,
                    "title": wp.title or "",
                    "llm_matches": url_matches,
                    "dwell_time": wp.dwell_time,
                })

        return dict(results)

    def _generate_statistics(self, justification_results, webpage_results):
        """Generate summary statistics."""
        all_users = set(justification_results.keys()) | set(webpage_results.keys())

        llm_counts = defaultdict(int)
        user_llm_map = defaultdict(set)
        tasks_with_llm = set()
        user_tasks_with_llm = defaultdict(set)

        for username, items in justification_results.items():
            for item in items:
                for llm in item["llm_matches"]:
                    llm_counts[llm] += 1
                    user_llm_map[username].add(llm)
                tasks_with_llm.add(item["task_id"])
                user_tasks_with_llm[username].add(item["task_id"])

        for username, items in webpage_results.items():
            for item in items:
                for llm in item["llm_matches"]:
                    llm_counts[llm] += 1
                    user_llm_map[username].add(llm)
                tasks_with_llm.add(item["task_id"])
                user_tasks_with_llm[username].add(item["task_id"])

        total_tasks = Task.objects.count()

        return {
            "total_users_with_llm": len(all_users),
            "total_tasks_with_llm": len(tasks_with_llm),
            "total_tasks": total_tasks,
            "percentage": len(tasks_with_llm) / total_tasks * 100 if total_tasks > 0 else 0,
            "llm_counts": dict(llm_counts),
            "user_llm_map": {k: list(v) for k, v in user_llm_map.items()},
            "user_tasks_with_llm": {k: list(v) for k, v in user_tasks_with_llm.items()},
            "users": list(all_users),
        }

    def _run_json_output(self):
        """Output results as JSON."""
        justification_results = self._analyze_justifications()
        webpage_results = self._analyze_webpages()
        stats = self._generate_statistics(justification_results, webpage_results)

        output = {
            "statistics": stats,
            "justifications": justification_results,
            "webpages": webpage_results,
        }

        self.stdout.write(json.dumps(output, indent=2, ensure_ascii=False))

    def _run_text_output(self, summary_only):
        """Output results as formatted text."""
        self.stdout.write(self.style.SUCCESS("LLM Usage Analysis (URL-based only)"))
        self.stdout.write("=" * 60)
        self.stdout.write("Searching for LLM service URLs: ChatGPT, Gemini, Claude, Doubao, DeepSeek, etc.")
        self.stdout.write("(Only matching URLs to avoid false positives)\n")

        self.stdout.write("Analyzing justifications...")
        justification_results = self._analyze_justifications()

        self.stdout.write("Analyzing webpages...")
        webpage_results = self._analyze_webpages()

        if not summary_only:
            self._print_detailed_results("JUSTIFICATIONS WITH LLM URLs", justification_results)
            self._print_detailed_results("WEBPAGES WITH LLM URLs", webpage_results)

        self._print_summary(justification_results, webpage_results)

    def _print_detailed_results(self, title, results):
        """Print detailed results for each user."""
        self.stdout.write(f"\n{'=' * 60}")
        self.stdout.write(self.style.SUCCESS(title))
        self.stdout.write("=" * 60)

        if not results:
            self.stdout.write("No LLM references found.")
            return

        for username, items in sorted(results.items()):
            self.stdout.write(f"\n--- User: {username} ({len(items)} occurrences) ---")
            for item in items[:5]:
                self.stdout.write(f"  LLMs: {', '.join(item['llm_matches'])}")
                if "url" in item:
                    self.stdout.write(f"  URL: {item['url'][:100]}...")
                if "title" in item:
                    self.stdout.write(f"  Title: {item['title']}")
                self.stdout.write("")
            if len(items) > 5:
                self.stdout.write(f"  ... and {len(items) - 5} more occurrences")

    def _print_summary(self, justification_results, webpage_results):
        """Print summary statistics."""
        stats = self._generate_statistics(justification_results, webpage_results)

        self.stdout.write(f"\n{'=' * 60}")
        self.stdout.write(self.style.SUCCESS("SUMMARY"))
        self.stdout.write("=" * 60)

        self.stdout.write(f"\nTotal unique users with LLM URL references: {stats['total_users_with_llm']}")
        self.stdout.write(f"Total unique tasks with LLM usage: {stats['total_tasks_with_llm']}")

        self.stdout.write("\nLLM reference counts (total URL occurrences):")
        for llm, count in sorted(stats["llm_counts"].items(), key=lambda x: -x[1]):
            self.stdout.write(f"  {llm}: {count}")

        self.stdout.write(f"\n{'-' * 60}")
        self.stdout.write(self.style.SUCCESS("DETAILED USER LIST"))
        self.stdout.write("-" * 60)

        for username in sorted(stats["users"]):
            llms_used = stats["user_llm_map"].get(username, [])
            just_count = len(justification_results.get(username, []))
            webpage_count = len(webpage_results.get(username, []))
            task_count = len(stats["user_tasks_with_llm"].get(username, []))

            self.stdout.write(f"\nUser: {username}")
            self.stdout.write(f"  LLMs referenced: {', '.join(sorted(llms_used))}")
            self.stdout.write(f"  Tasks with LLM: {task_count}, Justification URLs: {just_count}, Webpage URLs: {webpage_count}")

        self.stdout.write(f"\n{'-' * 60}")
        self.stdout.write(self.style.SUCCESS("TASK STATISTICS"))
        self.stdout.write("-" * 60)
        self.stdout.write(f"Total tasks in database: {stats['total_tasks']}")
        self.stdout.write(f"Tasks with LLM usage: {stats['total_tasks_with_llm']}")
        self.stdout.write(f"Percentage: {stats['percentage']:.1f}%")

        self.stdout.write(f"\n{'=' * 60}")
        self.stdout.write(self.style.SUCCESS("Analysis complete!"))
        self.stdout.write("=" * 60)
