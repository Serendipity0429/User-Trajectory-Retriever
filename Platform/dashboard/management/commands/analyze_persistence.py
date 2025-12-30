from django.core.management.base import BaseCommand
from task_manager.models import Task, User
from django.db.models import Count, Q, Prefetch
import statistics

class Command(BaseCommand):
    help = 'Analyzes user persistence and fatigue across tasks.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting Persistence Analysis...'))
        
        users = User.objects.annotate(
            total_tasks=Count('task'),
            cancelled_tasks=Count('task', filter=Q(task__cancelled=True)),
            success_tasks=Count('task', filter=Q(task__tasktrial__is_correct=True), distinct=True)
        ).filter(total_tasks__gt=5).prefetch_related(
            Prefetch('task_set', queryset=Task.objects.order_by('start_timestamp').prefetch_related('webpage_set'))
        )
        
        total_users = users.count()
        self.stdout.write(f"Analyzing {total_users} users...")
        
        user_stats = []
        processed = 0
        for u in users:
            processed += 1
            if processed % 10 == 0:
                self.stdout.write(f"Processed {processed}/{total_users} users...")

            tasks = list(u.task_set.all())
            # Calculate "Early Task Speed" vs "Late Task Speed"
            if len(tasks) < 4: continue
            
            def get_avg_p(task_list):
                counts = [t.webpage_set.count() for t in task_list]
                return statistics.mean(counts) if counts else 0

            early_p = get_avg_p(tasks[:3])
            late_p = get_avg_p(tasks[-3:])
            
            user_stats.append({
                'username': u.username,
                'persistence': (1 - (u.cancelled_tasks / u.total_tasks)) * 100,
                'success_rate': (u.success_tasks / u.total_tasks) * 100,
                'fatigue_index': (late_p - early_p) # Positive means they take MORE pages as time goes on
            })

        self.stdout.write(f"\n{'User':<15} | {'Persistence':<12} | {'Success':<10} | {'Fatigue Index'}")
        self.stdout.write("-" * 60)
        
        for s in sorted(user_stats, key=lambda x: x['success_rate'], reverse=True)[:10]:
            self.stdout.write(f"{s['username'][:15]:<15} | {s['persistence']:<12.1f}% | {s['success_rate']:<10.1f}% | {s['fatigue_index']:.1f}")

        # Correlation
        fatigues = [s['fatigue_index'] for s in user_stats]
        successes = [s['success_rate'] for s in user_stats]
        
        if len(fatigues) > 1:
            # Simple trend
            avg_fatigue = statistics.mean(fatigues)
            self.stdout.write(f"\nAvg Fatigue Index: {avg_fatigue:.2f} pages (increase in task length over time)")
            
        self.stdout.write('-----------------------------------')
