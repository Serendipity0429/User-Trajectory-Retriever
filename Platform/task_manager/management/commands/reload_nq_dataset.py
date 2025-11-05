import json
from django.core.management.base import BaseCommand
from task_manager.models import TaskDataset, TaskDatasetEntry
from django.core.exceptions import ObjectDoesNotExist
from thefuzz import fuzz

class Command(BaseCommand):
    help = 'Reload questions and answers for the NQ-open dataset from a file line by line.'

    def add_arguments(self, parser):
        parser.add_argument('dataset_path', type=str, help='The path to the dataset file.')
        parser.add_argument('dataset_name', type=str, help='The name of the dataset to reload.')

    def handle(self, *args, **kwargs):
        dataset_path = kwargs['dataset_path']
        dataset_name = kwargs['dataset_name']

        try:
            dataset = TaskDataset.objects.get(name=dataset_name)
            self.stdout.write(f"Found dataset '{dataset_name}'.")
        except ObjectDoesNotExist:
            self.stdout.write(self.style.ERROR(f"Dataset '{dataset_name}' does not exist. Please load it first."))
            return

        entries = TaskDatasetEntry.objects.filter(belong_dataset=dataset).order_by('id')
        
        with open(dataset_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        if len(lines) != entries.count():
            self.stdout.write(self.style.WARNING(
                f"Warning: The number of lines in the file ({len(lines)}) does not match the number of entries "
                f"in the dataset ({entries.count()}). Proceeding with the smaller of the two."
            ))

        for i, line in enumerate(lines):
            if i >= len(entries):
                self.stdout.write(self.style.WARNING(f"Stopping because file has more lines than dataset entries."))
                break
                
            try:
                data = json.loads(line)
                
                if fuzz.ratio(data['question'], entries[i].question) < 80:
                    self.stdout.write(self.style.WARNING(
                        f"Warning: The question on line {i+1} does not closely match the existing entry question. "
                        f"Skipping update for this entry."
                    ))
                    continue
                
                question = data['question']
                answer = data['answer']
                
                entry = entries[i]
                entry.question = question
                entry.answer = json.dumps(answer, ensure_ascii=False)
                entry.save()

            except json.JSONDecodeError:
                self.stdout.write(self.style.ERROR(f"Error decoding JSON on line {i+1}. Skipping."))
                continue
            except KeyError:
                self.stdout.write(self.style.ERROR(f"Missing 'question' or 'answer' on line {i+1}. Skipping."))
                continue

        self.stdout.write(self.style.SUCCESS(f"Dataset '{dataset_name}' reloaded successfully from '{dataset_path}'."))
