import os
import numpy as np
import matplotlib.pyplot as plt
from django.core.management.base import BaseCommand
from task_manager.models import Task, TaskTrial, Justification, TaskDatasetEntry


class Command(BaseCommand):
    help = "Output statistics of tasks"

    def add_arguments(self, parser):
        parser.add_argument(
            "--by",
            type=str,
            default="overall",
            choices=["overall", "question", "task_id", "question_summary"],
            help='Group statistics by "question", "task_id", get a "question_summary", or show "overall" stats.',
        )

    def handle(self, *args, **kwargs):
        group_by = kwargs["by"]

        self.stdout.write(self.style.SUCCESS("=" * 30))
        self.stdout.write(
            self.style.SUCCESS(
                f"Task Statistics Report (By {group_by.title().replace('_', ' ')})"
            )
        )
        self.stdout.write(self.style.SUCCESS("=" * 30))

        if group_by == "overall":
            self.overall_stats()
        elif group_by == "question":
            self.stats_by_question()
        elif group_by == "task_id":
            self.stats_by_task_id()
        elif group_by == "question_summary":
            self.question_summary_stats()

    def overall_stats(self):
        finished_tasks = Task.objects.filter(active=False)
        if not finished_tasks.exists():
            self.stdout.write(self.style.WARNING("No finished tasks to analyze."))
            return

        self.display_comprehensive_stats(finished_tasks, "Overall", "tempFiles/overall")

    def stats_by_question(self):
        questions = TaskDatasetEntry.objects.filter(task__isnull=False).distinct()
        if not questions.exists():
            self.stdout.write(
                self.style.WARNING("No questions with associated tasks found.")
            )
            return

        for question in questions:
            self.stdout.write(
                self.style.SUCCESS(f"\n{'='*20} Question ID: {question.id} {'='*20}")
            )
            self.stdout.write(f"{question.question}")
            tasks_for_question = Task.objects.filter(content=question, active=False)
            if tasks_for_question.exists():
                output_dir = f"tempFiles/by_question/q_{question.id}"
                self.display_comprehensive_stats(
                    tasks_for_question, f"Question {question.id}", output_dir
                )
            else:
                self.stdout.write(
                    self.style.WARNING("No finished tasks for this question.")
                )

    def stats_by_task_id(self):
        tasks = Task.objects.filter(active=False).order_by("id")
        if not tasks.exists():
            self.stdout.write(self.style.WARNING("No finished tasks to analyze."))
            return

        for task in tasks:
            self.stdout.write(
                self.style.SUCCESS(f"\n{'='*20} Task ID: {task.id} {'='*20}")
            )
            self.stdout.write(f"User: {task.user.username}")
            status = "Correct" if not task.cancelled else "Cancelled"
            self.stdout.write(f"Status: {status}")

            if not task.cancelled:
                duration_min = (
                    task.end_timestamp - task.start_timestamp
                ).total_seconds() / 60
                self.stdout.write(f"Duration: {duration_min:.2f} minutes")
                self.stdout.write(f"Number of Trials: {task.num_trial}")

                trials = TaskTrial.objects.filter(belong_task=task).order_by(
                    "num_trial"
                )
                for trial in trials:
                    trial_duration_min = (
                        trial.end_timestamp - trial.start_timestamp
                    ).total_seconds() / 60
                    self.stdout.write(
                        f"  - Trial {trial.num_trial}: {trial_duration_min:.2f} minutes, Justifications: {Justification.objects.filter(belong_task_trial=trial).count()}"
                    )

    def question_summary_stats(self):
        questions = TaskDatasetEntry.objects.filter(task__active=False).distinct()
        if not questions.exists():
            self.stdout.write(
                self.style.WARNING("No questions with associated tasks found.")
            )
            return

        avg_durations = []
        avg_trials = []
        success_rates = []

        for question in questions:
            tasks_for_question = Task.objects.filter(content=question, active=False)
            total_tasks = tasks_for_question.count()
            if total_tasks == 0:
                continue

            correct_tasks = tasks_for_question.filter(cancelled=False)
            correct_count = correct_tasks.count()

            success_rates.append((correct_count / total_tasks) * 100)

            if correct_count > 0:
                avg_duration = np.mean(
                    [
                        (t.end_timestamp - t.start_timestamp).total_seconds() / 60
                        for t in correct_tasks
                    ]
                )
                avg_durations.append(avg_duration)

                avg_trial = np.mean([t.num_trial for t in correct_tasks])
                avg_trials.append(avg_trial)

        output_dir = "tempFiles/question_summary"
        self.stdout.write(
            self.style.HTTP_INFO("\n--- Statistics of Per-Question Averages ---")
        )
        self.display_stats(
            "Average Task Completion Time Across Questions (minutes)", avg_durations
        )
        self.display_stats(
            "Average Number of Trials Across Questions", avg_trials, is_time=False
        )
        self.display_stats(
            "Success Rate Across Questions (%)", success_rates, is_time=False
        )

        self.generate_histograms(
            avg_durations, "avg_task_completion_time_across_questions", output_dir
        )
        self.generate_histograms(
            avg_trials, "avg_num_trials_across_questions", output_dir
        )
        self.generate_histograms(
            success_rates,
            "success_rate_across_questions",
            output_dir,
            xlabel="Success Rate (%)",
        )

    def display_comprehensive_stats(self, tasks_queryset, title_prefix, output_dir):
        # 1. Task counts
        total_finished = tasks_queryset.count()
        correct_tasks_q = tasks_queryset.filter(cancelled=False)
        correct_tasks_count = correct_tasks_q.count()
        cancelled_tasks_count = tasks_queryset.filter(cancelled=True).count()

        self.stdout.write(self.style.HTTP_INFO(f"\n--- {title_prefix} Task Counts ---"))
        self.stdout.write(f"Total finished tasks: {total_finished}")
        self.stdout.write(f"  - Correctly completed: {correct_tasks_count}")
        self.stdout.write(f"  - Cancelled: {cancelled_tasks_count}")
        if total_finished > 0:
            success_rate = (correct_tasks_count / total_finished) * 100
            self.stdout.write(f"Success rate: {success_rate:.2f}%")

        if correct_tasks_count == 0:
            self.stdout.write(
                self.style.WARNING("\nNo correctly completed tasks to analyze further.")
            )
            return

        # 2. Task time statistics
        task_durations = [
            (task.end_timestamp - task.start_timestamp).total_seconds() / 60
            for task in correct_tasks_q
        ]
        self.display_stats("Task Completion Time (minutes)", task_durations)

        # 3. Task trial time statistics
        trials = TaskTrial.objects.filter(belong_task__in=correct_tasks_q)
        trial_durations = [
            (trial.end_timestamp - trial.start_timestamp).total_seconds() / 60
            for trial in trials
            if trial.end_timestamp and trial.start_timestamp
        ]
        self.display_stats("Task Trial Time (minutes)", trial_durations)

        # 4. Histograms
        self.generate_histograms(
            task_durations, "task_completion_time_minutes", output_dir
        )
        self.generate_histograms(trial_durations, "task_trial_time_minutes", output_dir)

        # 5. Other valuable info
        self.stdout.write(
            self.style.HTTP_INFO(f"\n--- {title_prefix} Other Valuable Info ---")
        )

        num_trials = [task.num_trial for task in correct_tasks_q]
        self.display_stats(
            "Number of Trials per Correct Task", num_trials, is_time=False
        )

        justifications_per_trial = [
            Justification.objects.filter(belong_task_trial=trial).count()
            for trial in trials
        ]
        self.display_stats(
            "Justifications per Trial", justifications_per_trial, is_time=False
        )

    def display_stats(self, title, data, is_time=True):
        if not data:
            self.stdout.write(self.style.WARNING(f"\nNo data for {title}"))
            return

        unit = "m" if is_time else ""
        self.stdout.write(self.style.HTTP_INFO(f"\n--- {title} ---"))
        self.stdout.write(f"Average: {np.mean(data):.2f}{unit}")
        self.stdout.write(f"Median: {np.median(data):.2f}{unit}")
        self.stdout.write(f"Standard Deviation: {np.std(data):.2f}")
        self.stdout.write(f"Min: {np.min(data):.2f}{unit}")
        self.stdout.write(f"Max: {np.max(data):.2f}{unit}")

    def generate_histograms(self, data, name, output_dir, xlabel=None):
        if not data:
            return

        os.makedirs(output_dir, exist_ok=True)

        plt.figure(figsize=(10, 6))
        plt.hist(data, bins=20, color="skyblue", edgecolor="black")
        plt.title(f'Histogram of {name.replace("_", " ").title()}')
        plt.xlabel(xlabel if xlabel else "Value (minutes)")
        plt.ylabel("Frequency")
        plt.grid(True)
        filename = os.path.join(output_dir, f"{name}_histogram.png")
        plt.savefig(filename)
        self.stdout.write(
            self.style.SUCCESS(f"\nGenerated histogram and saved as {filename}")
        )
        plt.close()

        log_data = np.log1p(data)
        plt.figure(figsize=(10, 6))
        plt.hist(log_data, bins=20, color="lightgreen", edgecolor="black")
        plt.title(f'Histogram of Log-transformed {name.replace("_", " ").title()}')
        plt.xlabel("Log(Value + 1)")
        plt.ylabel("Frequency")
        plt.grid(True)
        log_filename = os.path.join(output_dir, f"log_{name}_histogram.png")
        plt.savefig(log_filename)
        self.stdout.write(
            self.style.SUCCESS(
                f"Generated log-transformed histogram and saved as {log_filename}"
            )
        )
        plt.close()
