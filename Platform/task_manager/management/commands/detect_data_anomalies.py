from django.core.management.base import BaseCommand
from django.db.models import Count, Q, F, Prefetch, Max, OuterRef, Subquery, Avg
from django.db.models.functions import Length
from task_manager.models import Task, TaskTrial, Webpage, PostTaskAnnotation, PreTaskAnnotation
from user_system.models import User
from core.utils import decompress_json_data
from tqdm import tqdm
from collections import defaultdict
import logging
import sys
import statistics
import json
import difflib

logger = logging.getLogger(__name__)

def flush():
    sys.stdout.flush()
    sys.stderr.flush()

class Command(BaseCommand):
    help = 'Detect and report data anomalies (Single-Process, Memory Efficient).'

    def add_arguments(self, parser):
        parser.add_argument('--max-pages', type=int, default=200)
        parser.add_argument('--min-pages', type=int, default=2)
        parser.add_argument('--min-task-duration', type=int, default=10)
        parser.add_argument('--max-answer-length', type=int, default=500)
        parser.add_argument('--min-dwell-time', type=int, default=10000)
        parser.add_argument('--rapid-gap', type=float, default=5.0)
        parser.add_argument('--include-tutorial', action='store_true', help='Include tutorial tasks in detection.')
        parser.add_argument('--min-annotation-time', type=int, default=5, help='Minimum time spent on annotation forms (default: 5)')
        parser.add_argument('--min-completion-rate', type=float, default=0.2, help='Minimum task completion rate (completed/started) to avoid flagging (default: 0.2)')
        parser.add_argument('--min-rel-duration', type=float, default=0.1, help='Minimum relative duration vs median (default: 0.1)')
        parser.add_argument('--max-rel-duration', type=float, default=8.0, help='Maximum relative duration vs median (default: 8.0)')
        parser.add_argument('--max-inactivity', type=int, default=180, help='Maximum allowed inactivity gap in seconds (default: 180)')
        parser.add_argument('--min-activity-ratio', type=float, default=0.4, help='Minimum ratio of dwell time to total duration for long tasks (default: 0.4)')
        parser.add_argument('--delete', action='store_true', help='Delete all tasks detected as anomalies.')
        parser.add_argument('--max-cancel-rate', type=float, default=0.1, help='Maximum allowed cancellation rate per user (default: 0.1)')

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("Starting Data Anomaly Detection (Efficient Single-Pass)..."))
        flush()
        
        self.user_issues = defaultdict(list)
        self.task_issues = defaultdict(list)
        self.test_findings = defaultdict(list)
        self.test_names = {
            1: "Tasks with Multiple Correct Trials",
            2: "Trials After Success",
            3: "Missing Annotations (Pre/Post)",
            4: "Rapid Submissions (<{rapid_gap}s)",
            5: "No Webpages Recorded",
            6: "Non-Last Trials Missing Justifications",
            7: "Weak Search Queries",
            8: "Long Answers (>{max_answer_length})",
            9: "Idle Pages (>{min_dwell_time}ms)",
            10: "Excessive Navigation (>{max_pages} pages)",
            11: "Short Tasks (<{min_task_duration}s)",
            12: "Repetitive Answers (Consecutive Identical)",
            13: "Temporal-Activity Anomalies (Long & Idle)",
            16: "Minimal Interaction Tasks",
            17: "Rushed Annotations (<{min_annotation_time}s)",
            18: "Global User Performance (Completion & Cancellation)",
            19: "User Task Goal Tracking (Progress)",
            20: "High User Inactivity (>{max_inactivity}s gaps)"
        }

        # Track total tasks per user
        self.user_task_counts = {}
        for u in User.participants.all():
            self.user_task_counts[u.username] = {'total': 0, 'completed': 0, 'cancelled': 0}

        inc_tut = options['include_tutorial']

        # Pre-pass: Content Statistics (IQR for Boxplot)
        self.content_stats = self._get_content_stats(inc_tut)
        self._populate_task_base_stats(inc_tut)

        # Pass 1: Trial Scan (1, 2, 4, 6, 8, 12, 14)
        self.scan_trials_efficiently(options, inc_tut)

        # Pass 2: Interaction Scan (5, 10, 16, 9, 20)
        self.scan_interaction_efficiently(options, inc_tut)

        # Pass 3: Annotation Scan (3, 7, 17)
        self.scan_annotations_efficiently(options['min_annotation_time'], inc_tut)

        # Global Analysis
        self.analyze_global_performance(options['min_completion_rate'], options['max_cancel_rate'])
        self.analyze_task_goals()

        # Sequential Reporting
        for i in sorted(self.test_names.keys()):
            name = self.test_names[i].format(**options)
            self.stdout.write(self.style.MIGRATE_HEADING(f"\n{i}. {name}"))
            findings = self.test_findings[i]
            for f in findings:
                self.stdout.write(self.style.WARNING(f))
            if not findings:
                self.stdout.write("No anomalies found.")
        
        self.report_final_summary()

        if options['delete']:
            problematic_tasks = list(self.task_issues.keys())
            if problematic_tasks:
                self.stdout.write(self.style.MIGRATE_HEADING(f"\nDeleting {len(problematic_tasks)} problematic tasks..."))
                deleted_count, _ = Task.objects.filter(id__in=problematic_tasks).delete()
                self.stdout.write(self.style.SUCCESS(f"Successfully deleted {deleted_count} tasks (including related data)."))
            else:
                self.stdout.write(self.style.SUCCESS("\nNo problematic tasks to delete."))

        self.stdout.write(self.style.SUCCESS("\nDetection complete."))
        flush()

    def _get_content_stats(self, inc_tut):
        content_durations = defaultdict(list)
        qs = Task.objects.filter(active=False, end_timestamp__isnull=False, start_timestamp__isnull=False, content__isnull=False)
        if not inc_tut: qs = qs.exclude(content__belong_dataset__name="tutorial")
        for v in qs.values('content_id', 'start_timestamp', 'end_timestamp'):
            dur = (v['end_timestamp'] - v['start_timestamp']).total_seconds()
            content_durations[v['content_id']].append(dur)
        
        stats = {}
        for cid, durs in content_durations.items():
            if len(durs) >= 5: # IQR is more stable with at least 5 points
                q1, med, q3 = statistics.quantiles(durs, n=4)
                iqr = q3 - q1
                stats[cid] = {
                    'low': max(0, q1 - 3 * iqr),
                    'high': q3 + 3 * iqr,
                    'med': med
                }
        return stats

    def _populate_task_base_stats(self, inc_tut):
        tasks = Task.objects.all()
        if not inc_tut: tasks = tasks.exclude(content__belong_dataset__name="tutorial")
        # Populate user_task_counts
        for t in tasks.values('user__username', 'active', 'cancelled'):
            uname = t['user__username']
            if uname not in self.user_task_counts: continue
            self.user_task_counts[uname]['total'] += 1
            if not t['active']:
                self.user_task_counts[uname]['completed'] += 1
                if t['cancelled']: self.user_task_counts[uname]['cancelled'] += 1

    def scan_trials_efficiently(self, options, inc_tut):
        # We order by belong_task to group trials in memory without N+1
        trials_qs = TaskTrial.objects.annotate(nj=Count('justifications'))
        if not inc_tut: trials_qs = trials_qs.exclude(belong_task__content__belong_dataset__name="tutorial")
        trials_qs = trials_qs.select_related('belong_task', 'belong_task__user').prefetch_related('justifications').only(
            'id', 'num_trial', 'answer', 'start_timestamp', 'end_timestamp', 'is_correct',
            'belong_task__id', 'belong_task__user__username'
        ).order_by('belong_task_id', 'num_trial')

        total = trials_qs.count()
        current_task_id = None
        task_trials = []

        def process_group(task_id, trials):
            if not trials: return
            uname = trials[0].belong_task.user.username
            
            # 1. Multiple Correct
            corrects = [t for t in trials if t.is_correct]
            if len(corrects) > 1:
                msg = f"Task {task_id}: {len(corrects)} correct trials."
                self.test_findings[1].append(f"User {uname}: {msg}")
                self.user_issues[uname].append(msg)
                self.task_issues[task_id].append(msg)
            
            # 2. Trials After Success
            if corrects:
                first_succ = min(t.num_trial for t in corrects)
                after = [t for t in trials if t.num_trial > first_succ]
                if after:
                    msg = f"Task {task_id}: {len(after)} trials after success (Trial #{first_succ})."
                    self.test_findings[2].append(f"User {uname}: {msg}")
                    self.user_issues[uname].append(msg)
                    self.task_issues[task_id].append(msg)
            
            # 4. Rapid Submissions
            for i in range(len(trials)-1):
                if trials[i].end_timestamp and trials[i+1].start_timestamp:
                    g = (trials[i+1].start_timestamp - trials[i].end_timestamp).total_seconds()
                    if 0 <= g < options['rapid_gap']:
                        msg = f"Task {task_id}: Rapid Trial {trials[i].num_trial}->{trials[i+1].num_trial} ({g:.2f}s)."
                        self.test_findings[4].append(f"User {uname}: {msg}")
                        self.user_issues[uname].append(msg)
                        self.task_issues[task_id].append(msg)

            # 6. Justifications (Non-last)
            max_num = max(t.num_trial for t in trials)
            for t in trials:
                if t.num_trial < max_num and t.nj == 0:
                    msg = f"Task {task_id}: Trial #{t.num_trial} missing justifications (not last trial)."
                    self.test_findings[6].append(f"User {uname}: {msg}")
                    self.user_issues[uname].append(msg)
                    self.task_issues[task_id].append(msg)
            
            # 8. Long Answers
            for t in trials:
                if t.answer and len(t.answer) > options['max_answer_length']:
                    msg = f"Task {task_id}: Trial #{t.num_trial} long answer ({len(t.answer)})."
                    self.test_findings[8].append(f"User {uname}: {msg}")
                    self.user_issues[uname].append(msg)
                    self.task_issues[task_id].append(msg)

            # 12. Repetitive Answers
            prev_ans = None
            prev_just_text = ""
            repeats = 0
            just_suspicious = 0
            for t in trials:
                curr_ans = t.answer.strip().lower() if t.answer else ""
                # Join all justification texts for this trial to check similarity
                justs = t.justifications.all()
                curr_just_text = " ".join(sorted([j.text.strip().lower() for j in justs if j.text]))

                if not curr_ans or curr_ans == "undefined": 
                    prev_ans = None
                    prev_just_text = ""
                    continue
                if prev_ans and curr_ans == prev_ans: 
                    repeats += 1
                    # If answers are identical, check if justifications are also too similar
                    if curr_just_text and prev_just_text:
                        if curr_just_text == prev_just_text or self._is_similar(curr_just_text, prev_just_text):
                            just_suspicious += 1
                prev_ans = curr_ans
                prev_just_text = curr_just_text

            if repeats > 0:
                just_note = ""
                if just_suspicious > 0:
                    just_note = f" ({just_suspicious} also had identical/similar justifications)"
                msg = f"Task {task_id}: {repeats} consecutive repetitive answers{just_note}."
                self.test_findings[12].append(f"User {uname}: {msg}")
                self.user_issues[uname].append(msg)
                self.task_issues[task_id].append(msg)

        for t in tqdm(trials_qs.iterator(chunk_size=1000), total=total, desc="Pass 1: Trials", file=sys.stdout):
            if t.belong_task_id != current_task_id:
                process_group(current_task_id, task_trials)
                current_task_id = t.belong_task_id
                task_trials = []
            task_trials.append(t)
        process_group(current_task_id, task_trials)

    def scan_interaction_efficiently(self, options, inc_tut):
        # 1. Get relevant task IDs and metadata first (Efficient) 
        tasks_meta = {} 
        t_meta_qs = Task.objects.filter(active=False)
        if not inc_tut: t_meta_qs = t_meta_qs.exclude(content__belong_dataset__name="tutorial")
        
        for t in t_meta_qs.values('id', 'user__username', 'start_timestamp', 'end_timestamp', 'content_id'):
            tasks_meta[t['id']] = t
        
        relevant_task_ids = list(tasks_meta.keys())
        if not relevant_task_ids:
            self.stdout.write("No tasks found to scan.")
            return

        # 2. Query Webpages using simple ID filter (MUCH faster)
        # Avoid select_related here, use tasks_meta mapping instead
        pages_qs = Webpage.objects.filter(belong_task_id__in=relevant_task_ids).only(
            'id', 'dwell_time', 'mouse_moves', 'event_list', 'rrweb_record', 'is_redirected',
            'belong_task_id'
        ).order_by('belong_task_id')

        total = pages_qs.count()
        current_task_id = None
        task_pages = []
        recorded_task_ids = set()

        def process_group(task_id, pages):
            if not task_id: return
            recorded_task_ids.add(task_id)
            meta = tasks_meta.get(task_id)
            uname = meta['user__username'] if meta else "Unknown"
            
            # 11, 15 Pre-checks
            dur = 0
            is_duration_anomaly_candidate = False
            duration_reason = ""
            
            if meta and meta['start_timestamp'] and meta['end_timestamp']:
                dur = (meta['end_timestamp'] - meta['start_timestamp']).total_seconds()
                
                # 11. Short Tasks (Remain separate)
                if dur < options['min_task_duration']:
                    msg = f"Task {task_id}: Completed very quickly ({dur:.1f}s)."
                    self.test_findings[11].append(f"User {uname}: {msg}")
                    self.user_issues[uname].append(msg)
                
                # Outlier check candidates
                is_boxplot_outlier = False
                cid = meta['content_id']
                if cid in self.content_stats:
                    s = self.content_stats[cid]
                    if dur < s['low'] or dur > s['high']:
                        is_boxplot_outlier = True
                
                if is_boxplot_outlier:
                    is_duration_anomaly_candidate = True
                    duration_reason = "Boxplot Outlier"

            # 10. Excessive Navigation
            if len(pages) > options['max_pages']:
                msg = f"Task {task_id}: Excessive navigation ({len(pages)} pages)."
                self.test_findings[10].append(f"User {uname}: {msg}")
                self.user_issues[uname].append(msg)
                self.task_issues[task_id].append(msg)
            
            # 16. Minimal Interaction & 9. Idle Pages & 20. Inactivity
            total_m, total_e, has_idle = 0, 0, False
            total_dwell_ms = 0
            task_inactivity_gaps = []
            
            should_check_inactivity = is_duration_anomaly_candidate

            for p in pages:
                if p.is_redirected: continue
                total_dwell_ms += (p.dwell_time or 0)
                m = self._count_items(p.mouse_moves)
                
                e_rrweb = 0
                if should_check_inactivity:
                    events = self._get_rrweb_events(p.rrweb_record)
                    e_rrweb = len(events)
                    
                    if events:
                        page_gaps = []
                        last_ts = events[0].get('timestamp')
                        for ev in events:
                            if self._is_interaction_event(ev):
                                curr_ts = ev.get('timestamp')
                                if last_ts and curr_ts:
                                    gap = (curr_ts - last_ts) / 1000.0
                                    if gap > options['max_inactivity']:
                                        page_gaps.append(gap)
                                last_ts = curr_ts
                        
                        if last_ts and events[-1].get('timestamp'):
                            gap = (events[-1].get('timestamp') - last_ts) / 1000.0
                            if gap > options['max_inactivity']:
                                page_gaps.append(gap)
                        
                        if page_gaps:
                            task_inactivity_gaps.extend(page_gaps)
                else:
                    e_rrweb = self._cheap_count_rrweb(p.rrweb_record)

                e_list = self._count_items(p.event_list)
                e = max(e_rrweb, e_list)

                total_m += m
                total_e += e
                if p.dwell_time and p.dwell_time > options['min_dwell_time'] and m == 0 and e == 0:
                    has_idle = True
                    msg = f"Page {p.id} (Task {task_id}): Dwell {p.dwell_time}ms, no interaction."
                    self.test_findings[9].append(f"User {uname}: {msg}")
                    self.user_issues[uname].append(msg)
                    self.task_issues[task_id].append(msg)

            # 13. Consolidated Temporal-Activity Anomaly check
            total_dwell_s = total_dwell_ms / 1000.0
            if is_duration_anomaly_candidate:
                # Flag as anomaly ONLY if it also fails the activity check
                if total_dwell_s < (dur * options['min_activity_ratio']):
                    msg = f"Task {task_id}: Temporal-Activity anomaly ({duration_reason}, Dur: {dur/60:.1f}m, Dwell: {total_dwell_s/60:.1f}m)."
                    self.test_findings[13].append(f"User {uname}: {msg}")
                    self.user_issues[uname].append(msg)
                    self.task_issues[task_id].append(msg)

            if task_inactivity_gaps:
                count = len(task_inactivity_gaps)
                total_gap = sum(task_inactivity_gaps)
                max_gap = max(task_inactivity_gaps)
                msg = f"Task {task_id}: {count} inactivity gaps (Sum: {total_gap/60:.1f}m, Max: {max_gap/60:.1f}m)."
                self.test_findings[20].append(f"User {uname}: {msg}")
                self.user_issues[uname].append(msg)
                self.task_issues[task_id].append(msg)

            if len(pages) > 0 and (total_m < 10 and total_e < 10):
                msg = f"Task {task_id}: Minimal interaction (Moves: {total_m}, Events: {total_e})."
                self.test_findings[16].append(f"User {uname}: {msg}")
                self.user_issues[uname].append(msg)
                self.task_issues[task_id].append(msg)
            elif has_idle:
                msg = f"Task {task_id}: Contains suspicious idle pages."
                self.test_findings[16].append(f"User {uname}: {msg}")
                self.user_issues[uname].append(msg)
                self.task_issues[task_id].append(msg)

        for p in tqdm(pages_qs.iterator(), total=total, desc="Pass 2: Interaction", file=sys.stdout):
            if p.belong_task_id != current_task_id:
                process_group(current_task_id, task_pages)
                current_task_id = p.belong_task_id
                task_pages = []
            task_pages.append(p)
        process_group(current_task_id, task_pages)
        
        # 5. No webpages recorded
        missing_pages = set(relevant_task_ids) - recorded_task_ids
        for tid in missing_pages:
            meta = tasks_meta[tid]
            msg = f"Task {tid}: No webpages recorded."
            self.test_findings[5].append(f"User {meta['user__username']}: {msg}")
            self.user_issues[meta['user__username']].append(msg)

    def scan_annotations_efficiently(self, min_anno, inc_tut):
        # 3. Missing Annotations & 7. Weak Queries & 17. Rushed
        tasks_qs = Task.objects.filter(active=False)
        if not inc_tut: tasks_qs = tasks_qs.exclude(content__belong_dataset__name="tutorial")
        tasks_meta = {t['id']: t for t in tasks_qs.values('id', 'user__username', 'cancelled')}
        relevant_task_ids = list(tasks_meta.keys())

        # Pre-fetch annotations to avoid N+1
        pre_map = {a['belong_task_id']: a for a in PreTaskAnnotation.objects.filter(belong_task_id__in=relevant_task_ids).values('belong_task_id', 'duration', 'first_search_query')}
        post_map = {a['belong_task_id']: a for a in PostTaskAnnotation.objects.filter(belong_task_id__in=relevant_task_ids).values('belong_task_id', 'duration')}
        
        for tid in tqdm(relevant_task_ids, desc="Pass 3: Annotations", file=sys.stdout):
            meta = tasks_meta[tid]
            uname = meta['user__username']
            pre = pre_map.get(tid)
            post = post_map.get(tid)
            
            # 3. Missing
            miss = []
            if not pre: miss.append("Pre")
            if not post and not meta['cancelled']: miss.append("Post")
            if miss:
                msg = f"Task {tid}: Missing {', '.join(miss)} annotations."
                self.test_findings[3].append(f"User {uname}: {msg}")
                self.user_issues[uname].append(msg)
                self.task_issues[tid].append(msg)
            
            # 17. Rushed
            if pre and pre['duration'] < min_anno:
                msg = f"Task {tid}: Rushed Pre-Task ({pre['duration']}s)."
                self.test_findings[17].append(f"User {uname}: {msg}")
                self.user_issues[uname].append(msg)
                self.task_issues[tid].append(msg)
            if post and post['duration'] < min_anno:
                msg = f"Task {tid}: Rushed Post-Task ({post['duration']}s)."
                self.test_findings[17].append(f"User {uname}: {msg}")
                self.user_issues[uname].append(msg)
                self.task_issues[tid].append(msg)
            
            # 7. Weak Query
            if pre:
                q = (pre['first_search_query'] or "").strip()
                if not q or len(q) <= 2:
                    msg = f"Task {tid}: Weak search query '{q or '[Empty]'}'."
                    self.test_findings[7].append(f"User {uname}: {msg}")
                    self.user_issues[uname].append(msg)
                    self.task_issues[tid].append(msg)

    def analyze_global_performance(self, min_comp_rate, max_cancel_rate=0.1):
        for uname, counts in self.user_task_counts.items():
            total = counts['total']
            completed = counts['completed']
            cancelled = counts['cancelled']
            if total >= 5:
                rate = completed / total
                if rate < min_comp_rate:
                    msg = f"GLOBAL: Low Completion Rate ({completed}/{total}, {rate:.1%})."
                    self.test_findings[18].append(f"User {uname}: {msg}")
                    self.user_issues[uname].append(msg)
            if completed > 0:
                c_rate = cancelled / completed
                if c_rate > max_cancel_rate:
                    msg = f"GLOBAL: High Cancellation Rate ({cancelled}/{completed}, {c_rate:.1%})."
                    self.test_findings[18].append(f"User {uname}: {msg}")
                    self.user_issues[uname].append(msg)

    def analyze_task_goals(self):
        for user in User.participants.all():
            formal = Task.objects.filter(user=user, content__belong_dataset__name="nq_hard_questions", active=False).count()
            tut = Task.objects.filter(user=user, content__belong_dataset__name="tutorial", active=False).count()
            if formal < 58 or tut < 4:
                msg = f"GOAL: Formal {formal}/58, Tutorial {tut}/4."
                self.test_findings[19].append(f"User {user.username}: {msg}")

    def report_final_summary(self):
        self.stdout.write(self.style.MIGRATE_HEADING("\n" + "="*40))
        self.stdout.write(self.style.MIGRATE_HEADING("       FINAL DATA ANOMALY REPORT"))
        self.stdout.write(self.style.MIGRATE_HEADING("="*40))

        # 1. OVERALL STATISTICS (Top of the report)
        total_tasks_scanned = Task.objects.filter(active=False).count()
        problematic_tasks = sorted(self.task_issues.keys())
        num_problematic_tasks = len(problematic_tasks)
        
        total_users = User.participants.count()
        problematic_users = [u for u, issues in self.user_issues.items() if issues]
        num_problematic_users = len(problematic_users)
        
        task_problem_rate = (num_problematic_tasks / total_tasks_scanned * 100) if total_tasks_scanned > 0 else 0
        user_problem_rate = (num_problematic_users / total_users * 100) if total_users > 0 else 0
        
        self.stdout.write(self.style.MIGRATE_HEADING("\n[1] Overall Statistics:"))
        self.stdout.write(f"  Tasks Scanned:       {total_tasks_scanned}")
        self.stdout.write(f"  Problematic Tasks:   {num_problematic_tasks} ({task_problem_rate:.1f}%)")
        self.stdout.write(f"  Clean Tasks:         {total_tasks_scanned - num_problematic_tasks}")
        self.stdout.write("")
        self.stdout.write(f"  Users Scanned:       {total_users}")
        self.stdout.write(f"  Problematic Users:   {num_problematic_users} ({user_problem_rate:.1f}%)")
        self.stdout.write(f"  Clean Users:         {total_users - num_problematic_users}")

        # 2. ANOMALY TYPE BREAKDOWN
        self.stdout.write(self.style.MIGRATE_HEADING("\n[2] Anomaly Type Breakdown:"))
        for i in sorted(self.test_names.keys()):
            findings = self.test_findings[i]
            count = len(findings)
            name = self.test_names[i].split(" (")[0] # Shorten name for table
            if count > 0:
                self.stdout.write(f"  - {name:<40}: {count} hits")

        # 3. USER-BASED SUMMARY
        self.stdout.write(self.style.MIGRATE_HEADING("\n[3] User-Based Summary:"))
        user_reports = []
        for username in self.user_task_counts.keys():
            issues = self.user_issues.get(username, [])
            counts = self.user_task_counts.get(username, {'total': 0, 'completed': 0})
            user_reports.append({
                'username': username,
                'issues': issues,
                'total': counts['total'],
                'completed': counts['completed']
            })
        
        user_reports.sort(key=lambda x: len(x['issues']), reverse=True)
        for r in user_reports:
            if not r['issues']: continue
            num_issues = len(r['issues'])
            self.stdout.write(self.style.MIGRATE_HEADING(f"  User: {r['username']} - {num_issues} anomalies ({r['completed']}/{r['total']} progress)"))
            # Sort issues to group by Task ID if possible
            sorted_issues = sorted(r['issues'])
            for issue in sorted_issues:
                self.stdout.write(f"    - {issue}")
            self.stdout.write("")

        # 4. DETAILED TASK-BASED LIST
        if num_problematic_tasks > 0:
            self.stdout.write(self.style.MIGRATE_HEADING("\n[4] Detailed Task-Based Anomaly List:"))
            for tid in problematic_tasks:
                issues = self.task_issues[tid]
                self.stdout.write(self.style.WARNING(f"  Task {tid}: ({len(issues)} anomalies)"))
                for issue in issues:
                    clean_issue = issue.split(": ", 1)[-1] if ":" in issue else issue
                    self.stdout.write(f"    - {clean_issue}")
        else:
            self.stdout.write(self.style.SUCCESS("\nAll tasks are clean!"))
        
        flush()

    def _get_rrweb_events(self, rrweb_record):
        if not rrweb_record: return []
        if isinstance(rrweb_record, list): return rrweb_record
        if isinstance(rrweb_record, dict) and rrweb_record.get("compressed"):
            return decompress_json_data(rrweb_record["data"]) or []
        if isinstance(rrweb_record, str):
            if rrweb_record in ("[]", "{}"): return []
            try:
                data = json.loads(rrweb_record)
                if isinstance(data, dict) and data.get("compressed"):
                    return decompress_json_data(data["data"]) or []
                return data if isinstance(data, list) else []
            except:
                return []
        return []

    def _is_interaction_event(self, event):
        return event.get('type') in [2, 3]

    def _is_similar(self, s1, s2, threshold=0.9):
        if not s1 or not s2: return s1 == s2
        return difflib.SequenceMatcher(None, s1, s2).ratio() > threshold

    def _cheap_count_rrweb(self, rrweb_record):
        """
        Estimate if rrweb_record has events without full decompression if possible.
        If it's empty, return 0. If it's compressed, return 1 (to indicate non-empty).
        We only decompress if we really need the exact count or for inactivity gaps.
        """
        if not rrweb_record: return 0
        if isinstance(rrweb_record, list): return len(rrweb_record)
        if isinstance(rrweb_record, dict):
            if rrweb_record.get("compressed"): return 1 # Non-empty indicator
            return len(rrweb_record)
        if isinstance(rrweb_record, str):
            if rrweb_record in ("[]", "{}"): return 0
            return 1 # Assume non-empty if string has content
        return 0

    def _count_items(self, val):
        if not val: return 0
        if isinstance(val, list): return len(val)
        if isinstance(val, dict):
            if val.get("compressed"):
                # If we really need the count of compressed items, we'd have to decompress.
                # For efficiency, we just return a large number if we don't want to decompress here,
                # but for accuracy in detect_data_anomalies, it's better to be correct.
                return len(self._get_rrweb_events(val))
            return len(val)
        if isinstance(val, str) and val.strip():
            if val in ("[]", "{}"): return 0
            try:
                data = json.loads(val)
                if isinstance(data, list): return len(data)
                if isinstance(data, dict):
                    if data.get("compressed"):
                        return len(self._get_rrweb_events(data))
                    return len(data)
            except: return 0
        return 0