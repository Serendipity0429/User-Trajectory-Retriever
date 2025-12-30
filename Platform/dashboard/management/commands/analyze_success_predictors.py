from django.core.management.base import BaseCommand
from task_manager.models import Task, TaskTrial, Webpage
from urllib.parse import urlparse
import statistics
import networkx as nx

class Command(BaseCommand):
    help = 'Contrasts Successful vs Failed tasks to find behavioral predictors.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting Success Predictor Analysis...'))
        
        # Group 1: High Success (Tasks where all trials were correct)
        # Group 2: Failure (Tasks where at least one trial was incorrect)
        
        # Simplify: Just look at trials directly? 
        # Better: Look at Tasks. A task is "Success" if average trial correctness > 0.5?
        # Let's use strict success (all correct) vs strict failure (all wrong) for contrast.
        
        tasks = Task.objects.prefetch_related('tasktrial_set', 'webpage_set')
        total_all_tasks = tasks.count()
        self.stdout.write(f"Scanning {total_all_tasks} tasks...")
        
        success_group = []
        failure_group = []
        
        processed = 0
        for t in tasks:
            processed += 1
            if processed % 200 == 0:
                 self.stdout.write(f"Scanned {processed}/{total_all_tasks} tasks...")

            trials = list(t.tasktrial_set.all())
            if not trials: continue
            
            # Check correctness
            # We assume is_correct is boolean.
            corrects = [tr.is_correct for tr in trials if tr.is_correct is not None]
            if not corrects: continue
            
            # Strict definition for cleaner signal
            if all(corrects):
                success_group.append(t)
            elif not any(corrects):
                failure_group.append(t)
                
        self.stdout.write(f"Identified {len(success_group)} Successful Tasks and {len(failure_group)} Failed Tasks.")
        
        def get_metrics(task_list):
            metrics = {
                'page_counts': [],
                'dwell_times': [],
                'search_ratios': [],
                'star_dominance': []
            }
            
            for t in task_list:
                pages = list(t.webpage_set.all())
                if not pages: continue
                
                metrics['page_counts'].append(len(pages))
                
                dwells = [p.dwell_time for p in pages if p.dwell_time]
                if dwells:
                    metrics['dwell_times'].append(statistics.mean(dwells))
                
                search_hits = 0
                for p in pages:
                    if 'google' in p.url or 'bing' in p.url:
                        search_hits += 1
                metrics['search_ratios'].append(search_hits / len(pages))
                
                # Simple topology check
                # Star dominance = (neighbors of root) / (total nodes - 1)
                # We reuse the logic from analyze_topology briefly
                try:
                    urls = [p.url for p in pages]
                    if len(set(urls)) > 2:
                        root = urls[0]
                        neighbors = 0
                        # Count how many times we return to root or go from root
                        # Simplified: Unique pages directly after root
                        # This is expensive to graph fully, let's use a heuristic:
                        # "Backtrack rate": How often is page[i] == page[i-2]?
                        backtracks = 0
                        for i in range(2, len(urls)):
                            if urls[i] == urls[i-2]:
                                backtracks += 1
                        metrics['star_dominance'].append(backtracks / len(pages))
                except:
                    pass

            return metrics

        s_metrics = get_metrics(success_group)
        f_metrics = get_metrics(failure_group)
        
        headers = ["Metric", "Success Group", "Failure Group", "Diff"]
        row_fmt = "{:<20} | {:<15} | {:<15} | {:<10}"
        self.stdout.write(row_fmt.format(*headers))
        self.stdout.write("-" * 65)
        
        def compare(name, key, multiplier=1, unit=""):
            s_val = statistics.mean(s_metrics[key]) * multiplier if s_metrics[key] else 0
            f_val = statistics.mean(f_metrics[key]) * multiplier if f_metrics[key] else 0
            diff = ((s_val - f_val) / f_val * 100) if f_val != 0 else 0
            
            s_str = f"{s_val:.2f}{unit}"
            f_str = f"{f_val:.2f}{unit}"
            diff_str = f"{diff:+.1f}%"
            
            self.stdout.write(row_fmt.format(name, s_str, f_str, diff_str))

        compare("Avg Pages/Task", 'page_counts')
        compare("Avg Dwell Time", 'dwell_times', 0.001, "s")
        compare("Search Ratio", 'search_ratios', 100, "%")
        compare("Backtrack Rate", 'star_dominance', 100, "%")

        self.stdout.write('-----------------------------------')
