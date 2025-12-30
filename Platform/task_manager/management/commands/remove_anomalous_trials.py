from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count, Max, OuterRef, Subquery, Q, F
from task_manager.models import Task, TaskTrial
from tqdm import tqdm
import sys

class Command(BaseCommand):
    help = 'Remove Type 1, 2, and 6 redundant/anomalous trials.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Only show what would be deleted.')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE - No data will be deleted\n"))

        # We'll iterate over all tasks that might have any of these issues
        tasks = Task.objects.all().select_related('user')
        
        total_deleted = 0
        tasks_fixed = 0

        self.stdout.write(f"Analyzing {tasks.count()} tasks...")
        sys.stdout.flush()

        for task in tqdm(tasks.iterator(), total=tasks.count(), desc="Processing tasks", file=sys.stdout):
            trials_to_delete = []
            
            # --- Phase 1: Type 1 & 2 (Post-Success Trials) ---
            first_success = task.tasktrial_set.filter(is_correct=True).order_by('num_trial').first()
            if first_success:
                post_success_trials = task.tasktrial_set.filter(num_trial__gt=first_success.num_trial)
                trials_to_delete.extend(list(post_success_trials.values_list('id', flat=True)))

            # --- Phase 2: Type 6 (Non-last trials with no justifications) ---
            # Exclude trials already marked for deletion in Phase 1
            max_t_val = task.tasktrial_set.aggregate(m=Max('num_trial'))['m']
            if max_t_val:
                type_6_trials = task.tasktrial_set.annotate(
                    nj=Count('justifications')
                ).filter(
                    nj=0, 
                    num_trial__lt=max_t_val
                ).exclude(id__in=trials_to_delete)
                
                trials_to_delete.extend(list(type_6_trials.values_list('id', flat=True)))

            if trials_to_delete:
                trials_to_delete = list(set(trials_to_delete)) # deduplicate
                count = len(trials_to_delete)
                tqdm.write(self.style.NOTICE(
                    f"Task {task.id} (User: {task.user.username}): Deleting {count} anomalous trials (IDs: {trials_to_delete})"
                ))
                
                if dry_run:
                    total_deleted += count
                    tasks_fixed += 1
                else:
                    try:
                        with transaction.atomic():
                            # 1. Delete the trials
                            TaskTrial.objects.filter(id__in=trials_to_delete).delete()
                            
                            # 2. Re-index remaining trials to be contiguous
                            remaining_trials = task.tasktrial_set.all().order_by('num_trial')
                            current_index = 1
                            for t in remaining_trials:
                                if t.num_trial != current_index:
                                    t.num_trial = current_index
                                    t.save()
                                current_index += 1
                            
                            # 3. Update Task's trial counter
                            task.num_trial = current_index - 1
                            task.save()
                            
                            total_deleted += count
                            tasks_fixed += 1
                    except Exception as e:
                        tqdm.write(self.style.ERROR(f"Error cleaning Task {task.id}: {str(e)}"))

        if dry_run:
            self.stdout.write(self.style.SUCCESS(f"\nDry run complete. Would have fixed {tasks_fixed} tasks and deleted {total_deleted} trials."))
        else:
            self.stdout.write(self.style.SUCCESS(f"\nCleanup complete. Fixed {tasks_fixed} tasks and deleted {total_deleted} trials."))
        sys.stdout.flush()