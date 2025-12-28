from django.core.management.base import BaseCommand
from task_manager.models import Task
from urllib.parse import urlparse, parse_qs
import difflib

class Command(BaseCommand):
    help = 'Analyzes the semantic evolution of search queries.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting Query Evolution Analysis...'))
        
        tasks = Task.objects.filter(webpage__isnull=False).distinct()
        
        evolution_stats = {'specification': 0, 'generalization': 0, 'reformulation': 0, 'repetition': 0}
        total_transitions = 0
        
        for task in tasks:
            pages = task.webpage_set.all().order_by('id')
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
