from django.core.management.base import BaseCommand
from django.db.models import Avg, Count, F
from user_system.models import User
from task_manager.models import (
    Task, TaskTrial, Webpage, PreTaskAnnotation, PostTaskAnnotation
)
from urllib.parse import urlparse
from collections import Counter

class Command(BaseCommand):
    help = 'Analyzes recorded trajectories and annotations.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting Data Analysis...'))
        self.stdout.write('-----------------------------------')

        # 1. General Counts
        user_count = User.objects.count()
        task_count = Task.objects.count()
        trial_count = TaskTrial.objects.count()
        webpage_count = Webpage.objects.count()

        self.stdout.write(f'Total Users: {user_count}')
        self.stdout.write(f'Total Tasks: {task_count}')
        self.stdout.write(f'Total Trials: {trial_count}')
        self.stdout.write(f'Total Webpages Recorded: {webpage_count}')
        self.stdout.write('-----------------------------------')

        # 2. Task Status Analysis
        completed_tasks = Task.objects.filter(end_timestamp__isnull=False).count()
        cancelled_tasks = Task.objects.filter(cancelled=True).count()
        active_tasks = Task.objects.filter(active=True).count()
        
        self.stdout.write(f'Completed Tasks: {completed_tasks}')
        self.stdout.write(f'Cancelled Tasks: {cancelled_tasks}')
        self.stdout.write(f'Active Tasks: {active_tasks}')
        
        if task_count > 0:
            completion_rate = (completed_tasks / task_count) * 100
            self.stdout.write(f'Completion Rate: {completion_rate:.2f}%')
        self.stdout.write('-----------------------------------')

        # 3. Trajectory Analysis (Webpages per Task)
        tasks_with_pages = Task.objects.annotate(page_count=Count('webpage')).filter(page_count__gt=0)
        avg_pages = tasks_with_pages.aggregate(Avg('page_count'))['page_count__avg']
        
        if avg_pages:
             self.stdout.write(f'Avg Webpages per Task (for tasks with activity): {avg_pages:.2f}')
        else:
             self.stdout.write('Avg Webpages per Task: N/A')
             
        avg_dwell = Webpage.objects.aggregate(Avg('dwell_time'))['dwell_time__avg']
        if avg_dwell:
             self.stdout.write(f'Avg Dwell Time per Page: {avg_dwell:.2f} (units depend on implementation)')
        self.stdout.write('-----------------------------------')

        # 4. Annotation Analysis (Difficulty)
        avg_pre_diff = PreTaskAnnotation.objects.aggregate(Avg('difficulty'))['difficulty__avg']
        avg_post_diff = PostTaskAnnotation.objects.aggregate(Avg('difficulty_actual'))['difficulty_actual__avg']

        if avg_pre_diff is not None:
            self.stdout.write(f'Avg Expected Difficulty (Pre-Task): {avg_pre_diff:.2f} / 4')
        if avg_post_diff is not None:
            self.stdout.write(f'Avg Actual Difficulty (Post-Task): {avg_post_diff:.2f} / 4')
            
        if avg_pre_diff is not None and avg_post_diff is not None:
            diff = avg_post_diff - avg_pre_diff
            self.stdout.write(f'Difficulty Gap (Actual - Expected): {diff:.2f}')
        
        self.stdout.write('-----------------------------------')

        # 5. Top Domains
        recent_pages = Webpage.objects.all().order_by('-id')[:2000]
        domains = []
        for p in recent_pages:
            try:
                domain = urlparse(p.url).netloc
                domains.append(domain)
            except:
                continue
        
        domain_counts = Counter(domains).most_common(10)
        self.stdout.write('Top 10 Visited Domains (from last 2000 pages):')
        for domain, count in domain_counts:
            self.stdout.write(f'  {domain}: {count}')
            
        self.stdout.write('-----------------------------------')
        self.stdout.write(self.style.SUCCESS('Analysis Complete.'))
