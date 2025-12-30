from django.core.management.base import BaseCommand
from task_manager.models import TaskTrial
from django.db.models import Avg, Count, Case, When, IntegerField, Sum

class Command(BaseCommand):
    help = 'Analyzes the correlation between user confidence and actual accuracy.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting Confidence Analysis...'))
        
        # Use aggregation to group by confidence and calculate metrics
        stats = TaskTrial.objects.exclude(confidence=-1).exclude(is_correct__isnull=True).values('confidence').annotate(
            total=Count('id'),
            correct_count=Sum(
                Case(When(is_correct=True, then=1), default=0, output_field=IntegerField())
            )
        ).order_by('confidence')

        total_trials = sum(s['total'] for s in stats)
        self.stdout.write(f"Analyzed {total_trials} trials.")

        self.stdout.write(f"\n[Accuracy by Confidence Level]")
        self.stdout.write(f"{'Conf':<5} | {'Trials':<8} | {'Accuracy':<10}")
        self.stdout.write("-" * 30)
        
        for s in stats:
            c = s['confidence']
            total = s['total']
            correct = s['correct_count']
            acc = (correct / total) * 100 if total > 0 else 0
            self.stdout.write(f"{c:<5} | {total:<8} | {acc:<10.1f}%")
            
        self.stdout.write('-----------------------------------')
