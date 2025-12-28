from django.core.management.base import BaseCommand
from task_manager.models import Webpage, Task
import json
import math
import statistics

class Command(BaseCommand):
    help = 'Analyzes micro-level user interactions (mouse moves, events).'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting Micro-Interaction Analysis...'))
        
        pages = Webpage.objects.exclude(mouse_moves=[]).exclude(mouse_moves__exact='[]').order_by('-id')[:200]
        
        if not pages:
            self.stdout.write("No data found.")
            return

        total_distance = []
        avg_speeds = [] 
        stillness_ratios = [] 
        
        hover_counts = []
        hover_tags = []
        
        y_ranges = []

        for page in pages:
            try:
                moves = page.mouse_moves
                if isinstance(moves, str):
                    moves = json.loads(moves)
                
                if not moves or len(moves) < 2:
                    continue

                dist = 0
                idle_time = 0
                active_time = 0
                min_y = float('inf')
                max_y = float('-inf')

                start_time = moves[0]['time']
                end_time = moves[-1]['time']
                duration_sec = (end_time - start_time) / 1000.0
                
                if duration_sec <= 0:
                    continue

                for i in range(1, len(moves)):
                    p1 = moves[i-1]
                    p2 = moves[i]
                    min_y = min(min_y, p1.get('y', 0))
                    max_y = max(max_y, p1.get('y', 0))
                    d = math.sqrt((p2['x'] - p1['x'])**2 + (p2['y'] - p1['y'])**2)
                    dist += d
                    dt = (p2['time'] - p1['time'])
                    if dt > 500 and d < 5:
                        idle_time += dt
                    else:
                        active_time += dt

                total_distance.append(dist)
                avg_speeds.append(dist / duration_sec)
                stillness_ratios.append((idle_time / (idle_time + active_time)) * 100 if (idle_time + active_time) > 0 else 0)
                y_ranges.append(max_y - min_y if max_y > min_y else 0)

            except Exception:
                pass

            try:
                events = page.event_list
                if isinstance(events, str):
                    events = json.loads(events)
                h_count = 0
                for e in events:
                    if e.get('type') == 'hover':
                        h_count += 1
                        tag = e.get('tag')
                        if tag: hover_tags.append(tag.upper())
                hover_counts.append(h_count)
            except Exception:
                pass

        self.stdout.write(f"\nAnalyzed {len(pages)} sample webpages.")

        if avg_speeds:
            mean_speed = statistics.mean(avg_speeds)
            mean_dist = statistics.mean(total_distance)
            mean_still = statistics.mean(stillness_ratios)
            self.stdout.write(f"\n[Mouse Dynamics]")
            self.stdout.write(f"Avg Mouse Speed: {mean_speed:.2f} pixels/sec")
            self.stdout.write(f"Avg Total Distance Travelled: {mean_dist:.2f} pixels")
            self.stdout.write(f"Avg Stillness (Idle Time): {mean_still:.2f}%")

        if y_ranges:
            mean_y_range = statistics.mean(y_ranges)
            self.stdout.write(f"\n[Viewport/Scroll Activity]")
            self.stdout.write(f"Avg Vertical Area Covered: {mean_y_range:.2f} pixels")

        if hover_counts:
            mean_hovers = statistics.mean(hover_counts)
            self.stdout.write(f"\n[Interaction Density]")
            self.stdout.write(f"Avg Hovers per Page: {mean_hovers:.2f}")
            
            from collections import Counter
            tag_counts = Counter(hover_tags).most_common(5)
            self.stdout.write("Most Hovered Elements:")
            for tag, count in tag_counts:
                self.stdout.write(f"  {tag}: {count}")

        self.stdout.write('-----------------------------------')
