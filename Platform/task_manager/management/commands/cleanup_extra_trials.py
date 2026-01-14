from django.core.management.base import BaseCommand
from django.db.models import Min
from task_manager.models import Task, TaskTrial, TaskDataset
from tqdm import tqdm
import sys


class Command(BaseCommand):
    help = 'Delete trials that occur after the first successful trial (systematic error cleanup).'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Show what would be deleted without actually deleting')
        parser.add_argument('--dataset', type=str, default='nq_hard_questions', help='Dataset name to clean up')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        dataset_name = options['dataset']

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE - No changes will be made"))

        self.stdout.write(self.style.MIGRATE_HEADING(f"Cleaning up extra trials after first success in '{dataset_name}'..."))

        # Get the dataset
        try:
            dataset = TaskDataset.objects.get(name=dataset_name)
        except TaskDataset.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Dataset '{dataset_name}' not found."))
            return

        # Get all completed tasks in the dataset
        tasks = Task.objects.filter(
            content__belong_dataset=dataset,
            active=False
        ).prefetch_related('tasktrial_set')

        total_deleted = 0
        affected_tasks = 0
        deletion_details = []

        for task in tqdm(tasks, desc="Scanning tasks", file=sys.stdout):
            trials = list(task.tasktrial_set.all().order_by('num_trial'))

            if not trials:
                continue

            # Find the first successful trial
            first_success_trial = None
            for trial in trials:
                if trial.is_correct:
                    first_success_trial = trial.num_trial
                    break

            if first_success_trial is None:
                continue  # No successful trial, nothing to clean

            # Find trials after the first success
            trials_to_delete = [t for t in trials if t.num_trial > first_success_trial]

            if trials_to_delete:
                affected_tasks += 1
                for t in trials_to_delete:
                    deletion_details.append({
                        'task_id': task.id,
                        'trial_id': t.id,
                        'trial_num': t.num_trial,
                        'first_success': first_success_trial,
                        'answer': t.answer[:50] if t.answer else None
                    })
                    total_deleted += 1

                if not dry_run:
                    # Delete the trials
                    trial_ids = [t.id for t in trials_to_delete]
                    TaskTrial.objects.filter(id__in=trial_ids).delete()

        # Print summary
        self.stdout.write(self.style.MIGRATE_HEADING("\n=== Cleanup Summary ==="))
        self.stdout.write(f"Tasks affected: {affected_tasks}")
        self.stdout.write(f"Trials {'to delete' if dry_run else 'deleted'}: {total_deleted}")

        if deletion_details and len(deletion_details) <= 50:
            self.stdout.write(self.style.MIGRATE_HEADING("\nDetails:"))
            for d in deletion_details:
                self.stdout.write(
                    f"  Task {d['task_id']}: Deleted trial #{d['trial_num']} "
                    f"(first success: #{d['first_success']}, answer: {d['answer']})"
                )
        elif deletion_details:
            self.stdout.write(self.style.MIGRATE_HEADING(f"\nShowing first 20 of {len(deletion_details)} deletions:"))
            for d in deletion_details[:20]:
                self.stdout.write(
                    f"  Task {d['task_id']}: Deleted trial #{d['trial_num']} "
                    f"(first success: #{d['first_success']}, answer: {d['answer']})"
                )

        if dry_run:
            self.stdout.write(self.style.WARNING("\nThis was a DRY RUN. Run without --dry-run to actually delete."))
        else:
            self.stdout.write(self.style.SUCCESS(f"\nSuccessfully deleted {total_deleted} extra trials."))
