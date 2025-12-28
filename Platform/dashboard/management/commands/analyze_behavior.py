from django.core.management.base import BaseCommand
from django.db.models import Avg, Sum
from task_manager.models import Task, Webpage, PostTaskAnnotation
from urllib.parse import urlparse, parse_qs
from collections import defaultdict
import statistics

class Command(BaseCommand):
    help = 'Analyzes human search behaviors and patterns in QA tasks.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting Behavioral Analysis...'))
        self.stdout.write('-----------------------------------')

        SEARCH_DOMAINS = {
            'www.google.com', 'google.com',
            'www.bing.com', 'cn.bing.com', 'bing.com',
            'www.baidu.com', 'baidu.com',
            'duckduckgo.com', 'search.yahoo.com'
        }

        def is_search_page(url):
            try:
                domain = urlparse(url).netloc
                return domain in SEARCH_DOMAINS
            except:
                return False

        tasks = Task.objects.filter(
            end_timestamp__isnull=False,
            webpage__isnull=False
        ).distinct().prefetch_related('webpage_set', 'posttaskannotation')

        total_tasks = 0
        search_time_ratios = []
        pogo_stick_counts = []
        unique_queries_counts = []
        page_counts = []
        
        difficulty_metrics = defaultdict(list) 

        for task in tasks:
            pages = list(task.webpage_set.all().order_by('id'))
            if not pages:
                continue
            
            total_tasks += 1
            time_search = 0
            time_content = 0
            transitions = [] 
            queries = set()

            for p in pages:
                dwell = p.dwell_time if p.dwell_time else 0
                if dwell > 600000: dwell = 600000
                
                is_search = is_search_page(p.url)
                
                if is_search:
                    time_search += dwell
                    transitions.append('S')
                    try:
                        parsed = urlparse(p.url)
                        params = parse_qs(parsed.query)
                        q_val = params.get('q') or params.get('wd') or params.get('p')
                        if q_val:
                            queries.add(q_val[0])
                    except:
                        pass
                else:
                    time_content += dwell
                    transitions.append('C')

            total_time = time_search + time_content
            search_ratio = (time_search / total_time) * 100 if total_time > 0 else 0
            search_time_ratios.append(search_ratio)
            unique_queries_counts.append(len(queries))
            page_counts.append(len(pages))

            pogo_count = 0
            for i in range(len(transitions) - 1):
                if transitions[i] == 'C' and transitions[i+1] == 'S':
                    pogo_count += 1
            pogo_stick_counts.append(pogo_count)

            try:
                diff = task.posttaskannotation.difficulty_actual
                if diff is not None:
                    difficulty_metrics[diff].append({
                        'pages': len(pages),
                        'queries': len(queries),
                        'search_ratio': search_ratio
                    })
            except PostTaskAnnotation.DoesNotExist:
                pass

        if total_tasks == 0:
            self.stdout.write("No sufficient data for analysis.")
            return

        self.stdout.write(f"Analyzed {total_tasks} completed tasks.")
        
        avg_search_ratio = statistics.mean(search_time_ratios)
        self.stdout.write(f"\n[Time Allocation]")
        self.stdout.write(f"Avg Time Spent on SERPs: {avg_search_ratio:.2f}%")
        self.stdout.write(f"Avg Time Spent Reading Content: {100 - avg_search_ratio:.2f}%")
        
        avg_queries = statistics.mean(unique_queries_counts)
        self.stdout.write(f"\n[Search Intensity]")
        self.stdout.write(f"Avg Unique Queries per Task: {avg_queries:.2f}")
        
        avg_pogo = statistics.mean(pogo_stick_counts)
        self.stdout.write(f"\n[Navigation Strategy]")
        self.stdout.write(f"Avg 'Return-to-Search' actions (Pogo-sticking) per Task: {avg_pogo:.2f}")
        
        self.stdout.write(f"\n[Behavior vs Perceived Difficulty]")
        sorted_diffs = sorted(difficulty_metrics.keys())
        
        header = f"{'Difficulty':<12} | {'Avg Pages':<10} | {'Avg Queries':<12} | {'Search Time %':<15}"
        self.stdout.write(header)
        self.stdout.write("-" * len(header))
        
        for diff in sorted_diffs:
            metrics = difficulty_metrics[diff]
            avg_p = statistics.mean(m['pages'] for m in metrics)
            avg_q = statistics.mean(m['queries'] for m in metrics)
            avg_t = statistics.mean(m['search_ratio'] for m in metrics)
            diff_label = f"{diff} (Hard)" if diff == 4 else f"{diff} (Easy)" if diff == 0 else str(diff)
            self.stdout.write(f"{diff_label:<12} | {avg_p:<10.2f} | {avg_q:<12.2f} | {avg_t:<15.2f}")

        self.stdout.write('-----------------------------------')
