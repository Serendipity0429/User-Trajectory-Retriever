import json
from django.core.management.base import BaseCommand
from task_manager.models import Task, TaskTrial, Webpage

class Command(BaseCommand):
    help = 'Statistics the data size of tasks, trials and webpages, separating rrweb_record, event_list and mouse_moves'

    def handle(self, *args, **options):
        self.stdout.write("Calculating data sizes... This may take a while.")

        # Initialize counters
        total_rrweb_size = 0
        total_event_list_size = 0
        total_mouse_moves_size = 0
        
        webpage_count = 0
        task_sizes = {} # map task_id -> size
        trial_sizes = {} # map trial_id -> size

        # helper to estimate size
        def get_size(data):
            if data is None:
                return 0
            # Rough estimation: length of JSON string
            try:
                return len(json.dumps(data))
            except:
                return 0

        # Use iterator to avoid loading all objects into memory
        webpages = Webpage.objects.all().iterator()
        
        for wp in webpages:
            webpage_count += 1
            
            rrweb = get_size(wp.rrweb_record)
            events = get_size(wp.event_list)
            moves = get_size(wp.mouse_moves)
            
            total_rrweb_size += rrweb
            total_event_list_size += events
            total_mouse_moves_size += moves
            
            wp_total = rrweb + events + moves
            
            # Aggregate to Task
            if wp.belong_task_id:
                task_sizes[wp.belong_task_id] = task_sizes.get(wp.belong_task_id, 0) + wp_total
                
            # Aggregate to Trial
            if wp.belong_task_trial_id:
                trial_sizes[wp.belong_task_trial_id] = trial_sizes.get(wp.belong_task_trial_id, 0) + wp_total

            if webpage_count % 100 == 0:
                 self.stdout.write(f"Processed {webpage_count} webpages...", ending='\r')
                 self.stdout.flush()

        self.stdout.write(f"\nProcessed {webpage_count} webpages.")

        total_size = total_rrweb_size + total_event_list_size + total_mouse_moves_size

        def format_bytes(size):
            # 2**10 = 1024
            power = 1024
            n = 0
            power_labels = {0 : 'B', 1: 'KB', 2: 'MB', 3: 'GB', 4: 'TB'}
            while size > power:
                size /= power
                n += 1
            return f"{size:.2f} {power_labels[n]}"

        self.stdout.write("\n--- Total Data Size by Field ---")
        self.stdout.write(f"rrweb_record: {format_bytes(total_rrweb_size)}")
        self.stdout.write(f"event_list:   {format_bytes(total_event_list_size)}")
        self.stdout.write(f"mouse_moves:  {format_bytes(total_mouse_moves_size)}")
        self.stdout.write(f"Total:        {format_bytes(total_size)}")

        self.stdout.write("\n--- Statistics ---")
        
        # Tasks
        num_tasks = len(task_sizes)
        if num_tasks > 0:
            avg_task = sum(task_sizes.values()) / num_tasks
            max_task = max(task_sizes.values())
            self.stdout.write(f"Tasks ({num_tasks}):")
            self.stdout.write(f"  Avg Size: {format_bytes(avg_task)}")
            self.stdout.write(f"  Max Size: {format_bytes(max_task)}")
        else:
            self.stdout.write("Tasks: No data")

        # Trials
        num_trials = len(trial_sizes)
        if num_trials > 0:
            avg_trial = sum(trial_sizes.values()) / num_trials
            max_trial = max(trial_sizes.values())
            self.stdout.write(f"Trials ({num_trials}):")
            self.stdout.write(f"  Avg Size: {format_bytes(avg_trial)}")
            self.stdout.write(f"  Max Size: {format_bytes(max_trial)}")
        else:
             self.stdout.write("Trials: No data")

        # Webpages
        if webpage_count > 0:
            avg_wp = total_size / webpage_count
            self.stdout.write(f"Webpages ({webpage_count}):")
            self.stdout.write(f"  Avg Size: {format_bytes(avg_wp)}")
        else:
            self.stdout.write("Webpages: No data")
