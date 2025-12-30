from django.core.management.base import BaseCommand
from task_manager.models import Webpage, TaskTrial
from urllib.parse import urlparse
from collections import defaultdict
import statistics

class Command(BaseCommand):
    help = 'Analyzes performance and behavior across different web domains.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting Domain Impact Analysis...'))
        
        # 1. Map domains to accuracy
        # We look at justifications to see which domains provided 'correct' answers
        domain_stats = defaultdict(lambda: {'correct': 0, 'total': 0, 'dwells': []})
        
        trials = TaskTrial.objects.prefetch_related('justifications').exclude(is_correct__isnull=True)
        total_trials = trials.count()
        self.stdout.write(f"Analyzing {total_trials} trials...")
        
        processed = 0
        for trial in trials.iterator(chunk_size=1000):
            processed += 1
            if processed % 1000 == 0:
                self.stdout.write(f"Processed {processed}/{total_trials} trials...")

            is_correct = trial.is_correct
            # Find the domains used in this trial
            seen_domains = set()
            for j in trial.justifications.all():
                try:
                    d = urlparse(j.url).netloc
                    if d: seen_domains.add(d)
                except: continue
            
            for d in seen_domains:
                domain_stats[d]['total'] += 1
                if is_correct:
                    domain_stats[d]['correct'] += 1

        # 2. Map domains to dwell time
        pages = Webpage.objects.exclude(dwell_time__isnull=True).only('url', 'dwell_time')
        total_pages = pages.count()
        self.stdout.write(f"Analyzing {total_pages} pages for dwell time...")
        
        processed = 0
        for p in pages.iterator(chunk_size=2000):
            processed += 1
            if processed % 5000 == 0:
                self.stdout.write(f"Processed {processed}/{total_pages} pages...")
                
            try:
                d = urlparse(p.url).netloc
                if d and d in domain_stats:
                    domain_stats[d]['dwells'].append(p.dwell_time)
            except: continue

        self.stdout.write(f"\n{'Domain':<25} | {'Trials':<8} | {'Accuracy':<10} | {'Avg Dwell':<10}")
        self.stdout.write("-" * 60)
        
        # Filter for domains with enough data
        significant_domains = [d for d in domain_stats if domain_stats[d]['total'] >= 10]
        # Sort by accuracy
        sorted_domains = sorted(significant_domains, key=lambda x: domain_stats[x]['correct']/domain_stats[x]['total'], reverse=True)

        for d in sorted_domains:
            data = domain_stats[d]
            acc = (data['correct'] / data['total']) * 100
            avg_dwell = statistics.mean(data['dwells']) / 1000.0 if data['dwells'] else 0
            self.stdout.write(f"{d[:25]:<25} | {data['total']:<8} | {acc:<10.1f}% | {avg_dwell:<10.1f}s")

        self.stdout.write('-----------------------------------')
