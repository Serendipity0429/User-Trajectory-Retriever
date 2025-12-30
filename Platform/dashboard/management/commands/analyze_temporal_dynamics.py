from django.core.management.base import BaseCommand
from django.db.models import Prefetch
from task_manager.models import Task, Webpage
from urllib.parse import urlparse
import statistics

class Command(BaseCommand):
    help = 'Analyzes how user behavior changes across the lifespan of a task (Early vs Middle vs Late).'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting Temporal Dynamics Analysis...'))
        
        # Optimize query with Prefetch
        tasks = Task.objects.filter(webpage__isnull=False).distinct().prefetch_related(
            Prefetch('webpage_set', queryset=Webpage.objects.order_by('start_timestamp', 'id'))
        )
        total_tasks = tasks.count()
        self.stdout.write(f"Analyzing {total_tasks} tasks...")
        
        # Buckets for phases
        phases = {
            'early': {'dwells': [], 'search_hits': 0, 'total_hits': 0},
            'middle': {'dwells': [], 'search_hits': 0, 'total_hits': 0},
            'late': {'dwells': [], 'search_hits': 0, 'total_hits': 0}
        }
        
        valid_tasks = 0
        processed = 0
        
        SEARCH_DOMAINS = ['google.com', 'bing.com', 'baidu.com', 'duckduckgo.com', 'yahoo.com']

        for task in tasks:
            processed += 1
            if processed % 200 == 0:
                self.stdout.write(f"Processed {processed}/{total_tasks} tasks...")

            pages = list(task.webpage_set.all())
            n = len(pages)
            if n < 3: continue 
            
            valid_tasks += 1
            
            # Divide into thirds
            p1 = int(n / 3)
            p2 = int(2 * n / 3)
            
            segments = [
                ('early', pages[:p1]),
                ('middle', pages[p1:p2]),
                ('late', pages[p2:])
            ]
            
            for phase_name, segment_pages in segments:
                for p in segment_pages:
                    dwell = p.dwell_time if p.dwell_time else 0
                    if dwell > 300000: dwell = 300000 # Cap outliers
                    
                    phases[phase_name]['dwells'].append(dwell)
                    phases[phase_name]['total_hits'] += 1
                    
                    try:
                        domain = urlparse(p.url).netloc
                        if any(s in domain for s in SEARCH_DOMAINS):
                            phases[phase_name]['search_hits'] += 1
                    except:
                        pass

        self.stdout.write(f"\nAnalyzed {valid_tasks} multi-step tasks.")
        
        header = f"{'Phase':<10} | {'Avg Dwell (s)':<15} | {'Search Usage %':<15}"
        self.stdout.write(header)
        self.stdout.write("-" * len(header))
        
        for phase in ['early', 'middle', 'late']:
            data = phases[phase]
            avg_dwell = statistics.mean(data['dwells']) / 1000.0 if data['dwells'] else 0
            search_ratio = (data['search_hits'] / data['total_hits'] * 100) if data['total_hits'] else 0
            
            self.stdout.write(f"{phase.capitalize():<10} | {avg_dwell:<15.2f} | {search_ratio:<15.1f}")

        self.stdout.write('-----------------------------------')
        self.stdout.write("Interpretation:\n" 
                          "- High 'Late' search % suggests 'Panic Searching' or verification.\n" 
                          "- Low 'Late' dwell time might indicate rushing.")
