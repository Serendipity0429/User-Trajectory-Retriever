from django.core.management.base import BaseCommand
from django.db.models import Count, Avg, Q
from task_manager.models import Task, Webpage, PreTaskAnnotation, PostTaskAnnotation, TaskTrial
from user_system.models import User
from collections import defaultdict, Counter
from tqdm import tqdm
import statistics

class Command(BaseCommand):
    help = 'Detect potentially sloppy annotators based on heuristics'

    def add_arguments(self, parser):
        # Existing arguments
        parser.add_argument('--min-task-duration', type=int, default=20, help='Minimum task duration in seconds (default: 30)')
        parser.add_argument('--min-pages', type=int, default=2, help='Minimum webpages visited (default: 2)')
        parser.add_argument('--min-annotation-time', type=int, default=5, help='Minimum time spent on annotation forms (default: 5)')
        
        # New arguments
        parser.add_argument('--max-trial-duration', type=int, default=3600, help='Maximum duration for a single trial in seconds (default: 3600)')
        parser.add_argument('--min-completion-rate', type=float, default=0.2, help='Minimum task completion rate (completed/started) to avoid flagging (default: 0.2)')
        parser.add_argument('--check-repetitive', action='store_true', default=True, help='Check for repetitive answers')
        
        # New arguments for deeper analysis
        parser.add_argument('--min-rel-duration', type=float, default=0.3, help='Minimum relative duration vs median (default: 0.3)')
        parser.add_argument('--max-rel-duration', type=float, default=4.0, help='Maximum relative duration vs median (default: 4.0)')

    def handle(self, *args, **options):
        min_task_dur = options['min_task_duration']
        min_pages = options['min_pages']
        min_anno_time = options['min_annotation_time']
        max_trial_dur = options['max_trial_duration']
        min_completion_rate = options['min_completion_rate']
        min_rel_dur = options['min_rel_duration']
        max_rel_dur = options['max_rel_duration']

        self.stdout.write(self.style.MIGRATE_HEADING("Analyzing user behavior for anomalies..."))
        
        user_flags = defaultdict(list)

        # --- PRE-PHASE: Calculate Median Durations Per Task Content ---
        self.stdout.write("Calculating task duration benchmarks...")
        content_durations = defaultdict(list)
        completed_tasks_qs = Task.objects.filter(
            active=False, cancelled=False, end_timestamp__isnull=False, content__isnull=False
        ).values('content_id', 'start_timestamp', 'end_timestamp')

        for t_val in completed_tasks_qs:
            if t_val['start_timestamp'] and t_val['end_timestamp']:
                dur = (t_val['end_timestamp'] - t_val['start_timestamp']).total_seconds()
                content_durations[t_val['content_id']].append(dur)
        
        content_medians = {}
        for cid, durs in content_durations.items():
            if len(durs) >= 3: # Need at least a few samples for a valid median
                content_medians[cid] = statistics.median(durs)
        
        self.stdout.write(f"Established benchmarks for {len(content_medians)} tasks.")
        
        # --- PHASE 1: Analyze Completed Tasks (Per Task Analysis) ---
        # We check completed tasks AND any task with trials (to catch repetitive answers in abandoned tasks)
        analyzed_tasks = Task.objects.filter(
            Q(active=False, cancelled=False, end_timestamp__isnull=False) | 
            Q(tasktrial__isnull=False)
        ).distinct().select_related('user').prefetch_related('tasktrial_set')
        
        for task in tqdm(analyzed_tasks, desc="Analyzing Tasks"):
            reasons = []
            is_completed = not task.active and not task.cancelled and task.end_timestamp is not None
            task_duration = 0
            if task.start_timestamp and task.end_timestamp:
                task_duration = (task.end_timestamp - task.start_timestamp).total_seconds()

            # 1. Short Task Duration (Only for completed tasks)
            if is_completed and task_duration > 0:
                if task_duration < min_task_dur:
                    reasons.append(f"Short Task Duration ({int(task_duration)}s)")
                
                # Check against median
                if task.content_id in content_medians:
                    median_dur = content_medians[task.content_id]
                    if task_duration < median_dur * min_rel_dur:
                         reasons.append(f"Abruptly Short vs Median ({int(task_duration)}s vs {int(median_dur)}s)")
                    elif task_duration > median_dur * max_rel_dur:
                         reasons.append(f"Abnormally Long vs Median ({int(task_duration)}s vs {int(median_dur)}s)")
            
            # 2. Low Page Visits (Only for completed tasks)
            if is_completed:
                pages = Webpage.objects.filter(belong_task=task)
                page_count = pages.count()
                if page_count < min_pages:
                    reasons.append(f"Low Page Visits ({page_count})")
                
                # Check Interaction Depth
                total_mouse_moves = 0
                total_rrweb_events = 0
                has_suspicious_empty_page = False
                
                import json
                def count_items(val):
                    if isinstance(val, list):
                        return len(val)
                    if isinstance(val, dict):
                        if 'data' in val and val['data']:
                            return 1 # Payload exists
                        return len(val)
                    if isinstance(val, str) and val.strip():
                        try:
                            data = json.loads(val)
                            if isinstance(data, list):
                                return len(data)
                            if isinstance(data, dict):
                                if 'data' in data and data['data']:
                                    return 1
                                return len(data)
                        except:
                            return 0
                    return 0

                for p in pages:
                    m_count = count_items(p.mouse_moves)
                    r_count = count_items(p.rrweb_record)
                    e_count = count_items(p.event_list)
                    
                    total_mouse_moves += m_count
                    total_rrweb_events += max(r_count, e_count)
                    
                    # Flag if a page was visited for > 5s (5000ms) but has NO recorded interaction
                    if p.dwell_time and p.dwell_time > 5000 and (m_count == 0 and r_count == 0 and e_count == 0):
                        has_suspicious_empty_page = True

                if total_mouse_moves < 10 and total_rrweb_events < 10:
                     reasons.append(f"Minimal Interaction (Moves: {total_mouse_moves}, Events: {total_rrweb_events})")
                
                if has_suspicious_empty_page:
                    reasons.append("Idle Page Visits (Dwell time > 5s with no events)")

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
                ordered_trials = trials.order_by('num_trial')
                consecutive_repeats = 0
                prev_answer = None
                
                for t in ordered_trials:
                    curr_answer = t.answer.strip().lower() if t.answer else ""
                    if not curr_answer or curr_answer == "undefined":
                        prev_answer = None
                        continue
                        
                    if prev_answer and curr_answer == prev_answer:
                        consecutive_repeats += 1
                    
                    prev_answer = curr_answer
                
                if consecutive_repeats > 0:
                    reasons.append(f"Identical Answers in Succeeding Trials ({consecutive_repeats} repeats)")

            if reasons:
                user_flags[task.user.username].append({
                    'type': 'task',
                    'id': task.id,
                    'reasons': reasons
                })

        # --- PHASE 2: User-Level Stats (Global Analysis) ---
        all_users = User.participants.all()
        
        for user in tqdm(all_users, desc="Global User Analysis"):
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

