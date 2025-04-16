from django.apps import AppConfig
import json

from pygame.examples.video import answer


class TaskManagerConfig(AppConfig):
    name = 'task_manager'
    default_auto_field = 'django.db.models.BigAutoField'

    # Load dataset
    def load_dataset(self):
        from task_manager.models import TaskDataset, TaskDatasetEntry
        def load_nq_dataset(dir):
            # Check if the dataset already exists
            if TaskDataset.objects.filter(name="NQ-open").exists():
                print("Dataset already exists, skipping loading.")
                return
            dataset = TaskDataset.objects.create(
                name="NQ-open",
                path=dir
            )
            with open(dir, 'r', encoding='utf-8') as f:
                for line in f:
                    data = json.loads(line)
                    question = data['question']
                    answer = data['answer']
                    entry = TaskDatasetEntry(
                        belong_dataset=dataset,
                        question=question,
                        answer=json.dumps(answer, ensure_ascii=False)  # Convert answer to JSON string
                    )
                    entry.save()

        nq_dir = r"dataset\natural-questions\nq_open\NQ-open.train.jsonl"
        load_nq_dataset(nq_dir)


    def ready(self):
        from task_manager.models import Task
        import task_manager.signals
        # Judge if Task Table already exists
        if not hasattr(Task, 'objects'):
            return
        Task.objects.filter(active=True).update(active=False)

        self.load_dataset()
