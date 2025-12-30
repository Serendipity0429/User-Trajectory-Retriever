from django.core.management.base import BaseCommand
from django.db import models
from django.db.models import Prefetch
from task_manager.models import Task, Webpage
from urllib.parse import urlparse
import statistics
import networkx as nx

class Command(BaseCommand):
    help = 'Analyzes the topological structure of user navigation (Star vs Chain).'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting Topological Analysis...'))
        
        tasks = Task.objects.annotate(page_count=models.Count('webpage')).filter(page_count__gt=2)
        tasks = tasks.prefetch_related(
            Prefetch('webpage_set', queryset=Webpage.objects.order_by('id'))
        ).order_by('-id')
        
        depths = []
        branching_factors = []
        star_dominance = [] 
        
        processed_count = 0
        for task in tasks:
            processed_count += 1
            if processed_count % 100 == 0:
                self.stdout.write(f"Processed {processed_count} tasks...")
            
            pages = list(task.webpage_set.all())
            if not pages:
                continue
                
            G = nx.DiGraph()
            
            def clean_url(u):
                try:
                    p = urlparse(u)
                    return p.netloc + p.path
                except:
                    return u

            id_to_url = {p.id: clean_url(p.url) for p in pages}
            root_url = id_to_url[pages[0].id]
            G.add_node(root_url)
            
            for p in pages:
                curr = clean_url(p.url)
                ref = clean_url(p.referrer) if p.referrer else None
                
                G.add_node(curr)
                if ref and ref != curr:
                    if ref in id_to_url.values():
                        G.add_edge(ref, curr)

            try:
                lengths = nx.shortest_path_length(G, source=root_url)
                max_d = max(lengths.values())
                depths.append(max_d)
                
                root_neighbors = len(list(G.successors(root_url)))
                total_nodes = G.number_of_nodes()
                if total_nodes > 1:
                    star_dominance.append(root_neighbors / (total_nodes - 1))
                
                out_degrees = [d for n, d in G.out_degree() if d > 0]
                if out_degrees:
                    avg_b = statistics.mean(out_degrees)
                    branching_factors.append(avg_b)
            except:
                pass

        self.stdout.write(f"\nAnalyzed {len(depths)} navigation graphs.")
        
        if not depths:
             return

        avg_depth = statistics.mean(depths)
        avg_branch = statistics.mean(branching_factors) if branching_factors else 0
        avg_star = statistics.mean(star_dominance) if star_dominance else 0
        
        self.stdout.write(f"\n[Topology Metrics]")
        self.stdout.write(f"Avg Max Depth: {avg_depth:.2f} hops")
        self.stdout.write(f"Avg Branching Factor: {avg_branch:.2f} clicks per node")
        self.stdout.write(f"Avg Star Dominance: {avg_star*100:.1f}%")
        
        self.stdout.write('-----------------------------------')
