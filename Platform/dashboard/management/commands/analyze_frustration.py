from django.core.management.base import BaseCommand
from task_manager.models import Task, Webpage, CancelAnnotation
import json
import statistics

class Command(BaseCommand):
    help = 'Analyzes signals of user frustration and cancellation.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting Frustration Analysis...'))
        
        cancelled_tasks = Task.objects.filter(cancelled=True).exclude(webpage__isnull=True)
        thrashing_count = 0
        
        for task in cancelled_tasks:
            recent_pages = task.webpage_set.all().order_by('-start_timestamp')[:3]
            short_dwells = [p for p in recent_pages if p.dwell_time and p.dwell_time < 3000] 
            if len(short_dwells) >= 2:
                thrashing_count += 1
                
        if cancelled_tasks.count() > 0:
            self.stdout.write(f"\n[The 'Give Up' Moment]")
            self.stdout.write(f"Analyzed {cancelled_tasks.count()} cancelled tasks.")
            self.stdout.write(f"Thrashing Detected: {thrashing_count} tasks ({thrashing_count/cancelled_tasks.count()*100:.1f}%)")
        
        sample_pages = Webpage.objects.exclude(event_list=[]).exclude(event_list__exact='[]').order_by('-id')[:200]
        
        rage_click_pages = 0
        
        for p in sample_pages:
            try:
                events = p.event_list
                if isinstance(events, str): events = json.loads(events)
                
                clicks = [e for e in events if e.get('type') in ['click', 'mousedown']]
                if len(clicks) < 3: continue
                
                clicks.sort(key=lambda x: x.get('timestamp', 0))
                
                for i in range(len(clicks) - 2):
                    t1 = clicks[i].get('timestamp', 0)
                    t3 = clicks[i+2].get('timestamp', 0)
                    if (t3 - t1) < 1000:
                        rage_click_pages += 1
                        break 
            except:
                pass
                
        self.stdout.write(f"\n[Rage Click Analysis]")
        self.stdout.write(f"Pages with Rage Clicks: {rage_click_pages} (Sample 200)")

        self.stdout.write('-----------------------------------')
