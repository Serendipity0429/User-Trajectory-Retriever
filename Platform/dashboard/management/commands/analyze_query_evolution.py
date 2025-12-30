from django.core.management.base import BaseCommand
from django.db.models import Prefetch
from django.core.paginator import Paginator
from task_manager.models import Task, Webpage
from urllib.parse import urlparse, parse_qs
import difflib

class Command(BaseCommand):
    help = 'Analyzes the semantic evolution of search queries.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting Query Evolution Analysis...'))
        
        # Get all task IDs first to avoid long-running transaction issues
        task_ids = list(Task.objects.filter(webpage__isnull=False).values_list('id', flat=True).distinct())
        total_tasks = len(task_ids)
        self.stdout.write(f"Found {total_tasks} tasks to process.")
        
        evolution_stats = {'specification': 0, 'generalization': 0, 'reformulation': 0, 'repetition': 0}
        total_transitions = 0
        
        batch_size = 100
        for i in range(0, total_tasks, batch_size):
            batch_ids = task_ids[i:i + batch_size]
            tasks = Task.objects.filter(id__in=batch_ids).prefetch_related(
                Prefetch('webpage_set', queryset=Webpage.objects.order_by('id'))
            )
            
            self.stdout.write(f"Processing batch {i // batch_size + 1}/{(total_tasks + batch_size - 1) // batch_size}...")

            for task in tasks:
                pages = list(task.webpage_set.all())
                queries = []
                
                for p in pages:
                    try:
                        parsed = urlparse(p.url)
                        q = None
                        params = parse_qs(parsed.query)
                        if 'google' in p.url or 'bing' in p.url:
                            q = params.get('q', [None])[0]
                        elif 'baidu' in p.url:
                            q = params.get('wd', [None])[0]
                        
                        if q:
                            q = q.lower().strip()
                            if not queries or queries[-1] != q:
                                queries.append(q)
                    except:
                        pass
            
                if len(queries) < 2:
                    continue
                    
                for i in range(len(queries) - 1):
                    q1 = queries[i]
                    q2 = queries[i+1]
                    total_transitions += 1
                    w1 = q1.split()
                    w2 = q2.split()
                    
                    if set(w1).issubset(set(w2)) and len(w2) > len(w1):
                        evolution_stats['specification'] += 1
                    elif set(w2).issubset(set(w1)) and len(w1) > len(w2):
                        evolution_stats['generalization'] += 1
                    elif q1 == q2:
                        evolution_stats['repetition'] += 1
                    else:
                        evolution_stats['reformulation'] += 1

        self.stdout.write(f"\nAnalyzed {total_transitions} query transitions.")
        
        self.stdout.write("\n[Query Semantic Drift]")
        for k, v in evolution_stats.items():
            self.stdout.write(f"  {k.capitalize()}: {v} ({v/total_transitions*100:.1f}%)")

        self.stdout.write('-----------------------------------')
