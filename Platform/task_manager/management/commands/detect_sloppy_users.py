from django.core.management.base import BaseCommand
from django.db.models import Count, Avg, Q
from task_manager.models import Task, Webpage, PreTaskAnnotation, PostTaskAnnotation, TaskTrial
from user_system.models import User
from collections import defaultdict, Counter

class Command(BaseCommand):
    help = 'Detect potentially sloppy annotators based on heuristics'

    def add_arguments(self, parser):
        # Existing arguments
        parser.add_argument('--min-task-duration', type=int, default=30, help='Minimum task duration in seconds (default: 30)')
        parser.add_argument('--min-pages', type=int, default=2, help='Minimum webpages visited (default: 2)')
        parser.add_argument('--min-annotation-time', type=int, default=5, help='Minimum time spent on annotation forms (default: 5)')
        
        # New arguments
        parser.add_argument('--max-trial-duration', type=int, default=3600, help='Maximum duration for a single trial in seconds (default: 3600)')
        parser.add_argument('--min-completion-rate', type=float, default=0.2, help='Minimum task completion rate (completed/started) to avoid flagging (default: 0.2)')
        parser.add_argument('--check-repetitive', action='store_true', default=True, help='Check for repetitive answers')

    def handle(self, *args, **options):
        min_task_dur = options['min_task_duration']
        min_pages = options['min_pages']
        min_anno_time = options['min_annotation_time']
        max_trial_dur = options['max_trial_duration']
        min_completion_rate = options['min_completion_rate']

        self.stdout.write(self.style.MIGRATE_HEADING("Analyzing user behavior for anomalies..."))
        
        user_flags = defaultdict(list)
        
        # --- PHASE 1: Analyze Completed Tasks (Per Task Analysis) ---
        completed_tasks = Task.objects.filter(active=False, cancelled=False, end_timestamp__isnull=False).select_related('user').prefetch_related('tasktrial_set')
        
        for task in completed_tasks:
            reasons = []
            
            # 1. Short Task Duration
            if task.end_timestamp and task.start_timestamp:
                duration = (task.end_timestamp - task.start_timestamp).total_seconds()
                if duration < min_task_dur:
                    reasons.append(f"Short Task Duration ({int(duration)}s)")
            
            # 2. Low Page Visits
            page_count = Webpage.objects.filter(belong_task=task).count()
            if page_count < min_pages:
                reasons.append(f"Low Page Visits ({page_count})")
            
            # 3. Rushed Annotations
            try:
                pre = PreTaskAnnotation.objects.filter(belong_task=task).first()
                if pre and pre.duration is not None and pre.duration < min_anno_time:
                     reasons.append(f"Rushed Pre-Task ({pre.duration}s)")
            except Exception: pass
            
            try:
                post = PostTaskAnnotation.objects.filter(belong_task=task).first()
                if post and post.duration is not None and post.duration < min_anno_time:
                     reasons.append(f"Rushed Post-Task ({post.duration}s)")
            except Exception: pass

            # 4. Excessive Trial Duration
            trials = task.tasktrial_set.all()
            for trial in trials:
                if trial.end_timestamp and trial.start_timestamp:
                    t_dur = (trial.end_timestamp - trial.start_timestamp).total_seconds()
                    if t_dur > max_trial_dur:
                        reasons.append(f"Excessive Trial Duration ({int(t_dur)}s)")
                        break # Flag task once

            # 5. Repetitive Answers (Within Task)
            if options['check_repetitive'] and trials.count() > 1:
                answers = [t.answer.strip().lower() for t in trials if t.answer]
                if answers:
                    most_common = Counter(answers).most_common(1)
                    if most_common and most_common[0][1] == len(answers) and len(answers) > 1:
                        reasons.append(f"Identical Answers in All {len(answers)} Trials")

            if reasons:
                user_flags[task.user.username].append({
                    'type': 'task',
                    'id': task.id,
                    'reasons': reasons
                })

        # --- PHASE 2: User-Level Stats (Global Analysis) ---
        all_users = User.participants.all()
        
        for user in all_users:
            user_tasks = Task.objects.filter(user=user)
            total_started = user_tasks.count()
            
            if total_started >= 5: # Only check users with significant activity
                completed = user_tasks.filter(active=False, cancelled=False, end_timestamp__isnull=False).count()
                completion_rate = completed / total_started
                
                if completion_rate < min_completion_rate:
                    user_flags[user.username].append({
                        'type': 'global',
                        'id': 'N/A',
                        'reasons': [f"High Abandonment Rate ({completed}/{total_started} completed, {int(completion_rate*100)}%)"]
                    })

        # --- Report Generation ---
        total_flagged_users = len(user_flags)
        
        if total_flagged_users == 0:
            self.stdout.write(self.style.SUCCESS("No suspicious behavior detected."))
            return

        sorted_users = sorted(user_flags.items(), key=lambda x: len(x[1]), reverse=True)

        for username, flags in sorted_users:
            self.stdout.write(self.style.ERROR(f"User: {username} - {len(flags)} Issues"))
            for item in flags:
                reasons_str = ", ".join(item['reasons'])
                if item['type'] == 'task':
                    self.stdout.write(f"  Task {item['id']}: {reasons_str}")
                else:
                    self.stdout.write(f"  Global Warning: {reasons_str}")
            self.stdout.write("")

        self.stdout.write(self.style.SUCCESS(f"Analysis complete. Found {total_flagged_users} users with potential issues."))
