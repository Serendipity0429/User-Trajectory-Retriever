from django.core.management.base import BaseCommand
from task_manager.models import TaskTrial
from django.db.models import Avg, Count
import statistics

class Command(BaseCommand):
    help = 'Analyzes the correlation between user confidence and actual accuracy.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting Confidence Analysis...'))
        
        trials = TaskTrial.objects.exclude(confidence=-1).exclude(is_correct__isnull=True)
        total = trials.count()
        
        stats = {} 
        for t in trials:
            c = t.confidence
            if c not in stats:
                stats[c] = {'correct': 0, 'total': 0}
            stats[c]['total'] += 1
            if t.is_correct:
                stats[c]['correct'] += 1
        
        self.stdout.write(f"\n[Accuracy by Confidence Level]")
        self.stdout.write(f"{'Conf':<5} | {'Trials':<8} | {'Accuracy':<10}")
        self.stdout.write("-" * 30)
        
        for c in sorted(stats.keys()):
            data = stats[c]
            acc = (data['correct'] / data['total']) * 100
            self.stdout.write(f"{c:<5} | {data['total']:<8} | {acc:<10.1f}%")
            
        self.stdout.write('-----------------------------------')
