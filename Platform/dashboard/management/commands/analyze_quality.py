from django.core.management.base import BaseCommand
from task_manager.models import PostTaskAnnotation, ReflectionAnnotation, Task, Webpage
from collections import Counter
import json
import statistics

class Command(BaseCommand):
    help = 'Analyzes user-reported quality signals (unhelpful paths, failures, aha moments).'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting Quality Analysis...'))

        annotations = PostTaskAnnotation.objects.exclude(unhelpful_paths__isnull=True)
        unhelpful_urls = []
        for ann in annotations:
            paths = ann.unhelpful_paths
            if isinstance(paths, str):
                try: paths = json.loads(paths)
                except: continue
            if isinstance(paths, list):
                unhelpful_urls.extend(paths)

        self.stdout.write(f"\n[Ineffective Paths]")
        self.stdout.write(f"Total User-Flagged Unhelpful Paths: {len(unhelpful_urls)}")
        
        unhelpful_pages = Webpage.objects.filter(url__in=unhelpful_urls[:500])
        bad_dwells = [p.dwell_time for p in unhelpful_pages if p.dwell_time]
        avg_dwell_bad = statistics.mean(bad_dwells) if bad_dwells else 0
        
        all_pages = Webpage.objects.all().order_by('-id')[:1000]
        dwells = [p.dwell_time for p in all_pages if p.dwell_time]
        avg_dwell_all = statistics.mean(dwells) if dwells else 0
        
        self.stdout.write(f"Avg Dwell Time on 'Unhelpful' Pages: {avg_dwell_bad/1000:.2f}s")
        self.stdout.write(f"Avg Dwell Time on All Pages: {avg_dwell_all/1000:.2f}s")
        
        failures = ReflectionAnnotation.objects.exclude(failure_category__isnull=True)
        fail_cats = []
        for f in failures:
            cats = f.failure_category
            if isinstance(cats, str):
                try: cats = json.loads(cats)
                except: continue
            if isinstance(cats, list):
                fail_cats.extend(cats)
        
        self.stdout.write(f"\n[Root Causes of Failure]")
        for cat, count in Counter(fail_cats).most_common(5):
            self.stdout.write(f"  {cat}: {count}")

        ahas = PostTaskAnnotation.objects.exclude(aha_moment_type__isnull=True)
        aha_types = [a.aha_moment_type for a in ahas if a.aha_moment_type]
        self.stdout.write(f"\n[Success Triggers (Aha Moments)]")
        for aha, count in Counter(aha_types).most_common(5):
            self.stdout.write(f"  {aha}: {count}")

        shifts = PostTaskAnnotation.objects.exclude(strategy_shift__isnull=True)
        shift_types = []
        for s in shifts:
            st = s.strategy_shift
            if isinstance(st, str):
                 try: st = json.loads(st)
                 except: continue
            if isinstance(st, list):
                shift_types.extend(st)
        self.stdout.write(f"\n[Adaptive Behavior (Strategy Shifts)]")
        for shift, count in Counter(shift_types).most_common(5):
            self.stdout.write(f"  {shift}: {count}")

        self.stdout.write('-----------------------------------')
