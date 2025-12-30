from django.core.management.base import BaseCommand
from task_manager.models import ReflectionAnnotation
from collections import Counter
import json

class Command(BaseCommand):
    help = 'Analyzes user reflections on failure and future plans.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting Reflection Analysis...'))
        
        # Optimize by fetching only needed fields
        data = ReflectionAnnotation.objects.values_list('failure_category', 'future_plan_actions')
        total_refs = data.count()
        self.stdout.write(f"Analyzing {total_refs} reflections...")
        
        fail_cats = []
        future_actions = []
        
        processed = 0
        for cats_raw, actions_raw in data:
            processed += 1
            if processed % 500 == 0:
                self.stdout.write(f"Processed {processed}/{total_refs} reflections...")

            if cats_raw:
                cats = cats_raw
                if isinstance(cats, str): 
                    try: cats = json.loads(cats)
                    except: cats = [cats]
                if isinstance(cats, list):
                    fail_cats.extend(cats)
            
            if actions_raw:
                actions = actions_raw
                if isinstance(actions, str):
                    try: actions = json.loads(actions)
                    except: actions = [actions]
                if isinstance(actions, list):
                    future_actions.extend(actions)

        self.stdout.write(f"\n[Why Users Think They Failed]")
        for cat, count in Counter(fail_cats).most_common(10):
            self.stdout.write(f"  {cat:<30}: {count}")

        self.stdout.write(f"\n[What Users Would Do Differently (Future Plans)]")
        for act, count in Counter(future_actions).most_common(10):
            self.stdout.write(f"  {act:<30}: {count}")

        self.stdout.write('-----------------------------------')
