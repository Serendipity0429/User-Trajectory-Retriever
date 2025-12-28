from django.core.management.base import BaseCommand
from django.db.models import Avg, Count, Sum
from user_system.models import User
from task_manager.models import Task, Webpage
import statistics

class Command(BaseCommand):
    help = 'Classifies users into behavioral personas.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting Persona Analysis...'))
        
        users = User.objects.all()
        user_metrics = []
        
        for u in users:
            tasks = Task.objects.filter(user=u, end_timestamp__isnull=False)
            task_count = tasks.count()
            if task_count < 5:
                continue
            
            avg_pages_list = []
            for t in tasks:
                p_count = t.webpage_set.count()
                avg_pages_list.append(p_count)
            avg_pages_per_task = statistics.mean(avg_pages_list)
            
            u_pages = Webpage.objects.filter(user=u)
            page_visits_count = u_pages.count()
            if page_visits_count == 0:
                continue

            dwells = [p.dwell_time for p in u_pages if p.dwell_time]
            avg_dwell = statistics.mean(dwells) if dwells else 0
            
            search_count = u_pages.filter(url__icontains='google').count() + \
                           u_pages.filter(url__icontains='bing').count() + \
                           u_pages.filter(url__icontains='baidu').count()
            search_ratio = search_count / page_visits_count
            
            user_metrics.append({
                'username': u.username,
                'avg_pages': avg_pages_per_task,
                'avg_dwell': avg_dwell / 1000.0,
                'search_ratio': search_ratio
            })

        self.stdout.write(f"\nAnalyzed {len(user_metrics)} active users.")
        
        if not user_metrics:
            return

        pop_pages = statistics.mean([m['avg_pages'] for m in user_metrics])
        pop_dwell = statistics.mean([m['avg_dwell'] for m in user_metrics])
        pop_search = statistics.mean([m['search_ratio'] for m in user_metrics])
        
        self.stdout.write(f"Population Averages: {pop_pages:.1f} pages/task, {pop_dwell:.1f}s dwell, {pop_search*100:.1f}% search")
        
        personas = {'Sniper': [], 'Forager': [], 'Reader': [], 'Struggler': []}
        
        for m in user_metrics:
            if m['avg_pages'] < pop_pages and m['search_ratio'] > pop_search:
                personas['Sniper'].append(m['username'])
            elif m['avg_pages'] > pop_pages and m['search_ratio'] > pop_search:
                personas['Forager'].append(m['username'])
            elif m['search_ratio'] < pop_search and m['avg_dwell'] > pop_dwell:
                personas['Reader'].append(m['username'])
            else:
                personas['Struggler'].append(m['username'])

        self.stdout.write(f"\n[User Persona Distribution]")
        for p, users in personas.items():
            self.stdout.write(f"  {p}: {len(users)} users ({len(users)/len(user_metrics)*100:.1f}%)")

        self.stdout.write('-----------------------------------')
