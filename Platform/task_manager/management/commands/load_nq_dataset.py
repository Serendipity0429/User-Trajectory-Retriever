import json
from django.core.management.base import BaseCommand
from task_manager.models import TaskDataset, TaskDatasetEntry

class Command(BaseCommand):
    help = 'Load the NQ-open dataset into the database'

    def add_arguments(self, parser):
        parser.add_argument('dataset_path', type=str)
        parser.add_argument('dataset_name', type=str, default="train")

    def handle(self, *args, **kwargs):
        dataset_path = kwargs['dataset_path']
        dataset_name = kwargs['dataset_name']

        existing_datasets = TaskDataset.objects.filter(name=dataset_name)
        if existing_datasets.exists():
            # Delete the existing dataset if you want to reload it
            self.stdout.write(f"NQ-open {dataset_name} dataset already exists, deleting it.")
            existing_datasets.delete()
            # self.stdout.write(f"NQ-open {dataset_name} dataset already exists, skipping.")
            # return

        dataset = TaskDataset.objects.create(
            name=dataset_name,
            path=dataset_path
        )

        with open(dataset_path, 'r', encoding='utf-8') as f:
            for line in f:
                data = json.loads(line)
                question = data['question']
                answer = data['answer']
                TaskDatasetEntry.objects.create(
                    belong_dataset=dataset,
                    question=question,
                    answer=json.dumps(answer, ensure_ascii=False)
                )

        self.stdout.write(self.style.SUCCESS(f"Dataset NQ-open {dataset_name} loaded successfully."))
