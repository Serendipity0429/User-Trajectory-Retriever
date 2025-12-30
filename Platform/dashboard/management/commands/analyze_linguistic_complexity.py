from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from task_manager.models import Task
import statistics

class Command(BaseCommand):
    help = 'Analyzes trajectories based on question complexity (Optimized).'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting Linguistic Complexity Analysis...'))
        
        # We use annotation to avoid loading all objects
        tasks = Task.objects.filter(content__isnull=False).annotate(
            p_count=Count('webpage'),
            s_count=Count('webpage', filter=Q(webpage__url__icontains='google') | Q(webpage__url__icontains='bing') | Q(webpage__url__icontains='baidu')),
            correct_trials=Count('tasktrial', filter=Q(tasktrial__is_correct=True))
        ).select_related('content')

        groups = {
            'short_factoid': {'pages': [], 'search_ratio': [], 'acc': []},
            'long_complex': {'pages': [], 'search_ratio': [], 'acc': []},
            'reasoning_words': {'pages': [], 'search_ratio': [], 'acc': []}
        }
        
        reasoning_keywords = ['why', 'how', 'difference', 'compare', 'contrast', 'explain', 'reason']

        total_tasks = tasks.count()
        self.stdout.write(f"Analyzing {total_tasks} tasks...")
        
        processed = 0
        for task in tasks:
            processed += 1
            if processed % 500 == 0:
                self.stdout.write(f"Processed {processed}/{total_tasks} tasks...")

            q = task.content.question.lower()
            p_count = task.p_count
            if p_count == 0: continue
            
            is_correct = task.correct_trials > 0
            search_ratio = (task.s_count / p_count * 100)

            target_groups = []
            words = q.split()
            if len(words) < 10: target_groups.append('short_factoid')
            if len(words) >= 12: target_groups.append('long_complex')
            if any(w in q for w in reasoning_keywords): target_groups.append('reasoning_words')
            
            for g in target_groups:
                groups[g]['pages'].append(p_count)
                groups[g]['acc'].append(1 if is_correct else 0)
                groups[g]['search_ratio'].append(search_ratio)

        self.stdout.write(f"\n{'Group':<20} | {'Avg Pages':<10} | {'Search %':<10} | {'Accuracy':<10}")
        self.stdout.write("-" * 55)
        
        for g, data in groups.items():
            if not data['pages']: continue
            avg_p = statistics.mean(data['pages'])
            avg_s = statistics.mean(data['search_ratio'])
            acc = (sum(data['acc']) / len(data['acc']) * 100)
            
            self.stdout.write(f"{g:<20} | {avg_p:<10.1f} | {avg_s:<10.1f}% | {acc:<10.1f}%")

        self.stdout.write('-----------------------------------')