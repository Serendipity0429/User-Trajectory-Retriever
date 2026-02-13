"""
Management command to export task_manager data to HuggingFace-compatible JSONL format.

Usage:
    python manage.py export_task_data --mode anonymized --output ./export/
    python manage.py export_task_data --mode full --output ./export/
    python manage.py export_task_data --mode anonymized --output ./export/ --test
"""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from dashboard.utils.export import TaskManagerExporter
from dashboard.utils.huggingface import save_huggingface_files, generate_dataset_info


class Command(BaseCommand):
    help = 'Export task_manager data to HuggingFace-compatible JSONL format'

    def add_arguments(self, parser):
        parser.add_argument(
            '--mode',
            type=str,
            choices=['anonymized', 'full'],
            default='anonymized',
            help='Export mode: "anonymized" (default) or "full"'
        )
        parser.add_argument(
            '--output',
            type=str,
            required=True,
            help='Output directory path'
        )
        parser.add_argument(
            '--test',
            action='store_true',
            help='Test mode: export only 2 users'
        )
        parser.add_argument(
            '--users',
            type=str,
            help='Comma-separated list of user IDs to export'
        )

    def handle(self, *args, **options):
        from task_manager.models import TaskDataset

        mode = options['mode']
        output_dir = options['output']
        test_mode = options['test']
        user_ids_str = options.get('users')

        anonymize = (mode == 'anonymized')

        # Parse user IDs if provided
        user_ids = None
        if user_ids_str:
            try:
                user_ids = [int(uid.strip()) for uid in user_ids_str.split(',')]
            except ValueError:
                raise CommandError('Invalid user IDs format. Use comma-separated integers.')

        # Determine limit for test mode
        limit = 2 if test_mode else None

        if test_mode:
            self.stdout.write(self.style.WARNING('[TEST MODE] Exporting only 2 users...'))

        # Always exclude tutorial dataset
        exclude_dataset_ids = list(
            TaskDataset.objects.filter(name="tutorial").values_list('id', flat=True)
        )
        if exclude_dataset_ids:
            self.stdout.write(f"Excluding tutorial dataset (ID: {exclude_dataset_ids})")

        # Create exporter
        exporter = TaskManagerExporter(anonymize=anonymize)

        # Get preview first
        preview = exporter.get_export_preview(
            user_ids=user_ids, limit=limit, exclude_dataset_ids=exclude_dataset_ids
        )
        self.stdout.write(f"Preparing to export:")
        self.stdout.write(f"  - Participants: {preview['participant_count']}")
        self.stdout.write(f"  - Tasks: {preview['task_count']}")
        self.stdout.write(f"  - Trials: {preview['trial_count']}")
        self.stdout.write(f"  - Webpages: {preview['webpage_count']}")
        self.stdout.write(f"  - Mode: {'Anonymized' if anonymize else 'Full'}")

        # Export
        self.stdout.write('Exporting...')
        stats = exporter.export_to_file(
            output_dir, user_ids=user_ids, limit=limit,
            exclude_dataset_ids=exclude_dataset_ids
        )

        # Save HuggingFace files
        save_huggingface_files(output_dir, stats, anonymized=anonymize)

        # Convert JSONL → Parquet with explicit schema (streaming, memory-safe)
        output_path = Path(output_dir)
        jsonl_path = output_path / "data.jsonl"
        data_dir = output_path / "data"
        data_dir.mkdir(exist_ok=True)
        parquet_path = data_dir / "train-00000-of-00001.parquet"

        self.stdout.write('Converting to Parquet...')
        features_dict = generate_dataset_info(stats, anonymized=anonymize)["features"]
        TaskManagerExporter.jsonl_to_parquet(jsonl_path, parquet_path, features_dict)

        # Remove intermediate JSONL (Parquet is the primary format)
        jsonl_path.unlink()

        self.stdout.write(self.style.SUCCESS(f'Export completed!'))
        self.stdout.write(f"  - Output directory: {output_dir}")
        self.stdout.write(f"  - Tasks exported: {stats['task_count']}")
        self.stdout.write(f"  - Participants: {stats['participant_count']}")
        self.stdout.write(f"  - Trials: {stats['trial_count']}")
        self.stdout.write(f"  - Webpages: {stats['webpage_count']}")
        self.stdout.write(f"Files created:")
        self.stdout.write(f"  - {parquet_path}")
        self.stdout.write(f"  - {output_dir}/dataset_info.json")
        self.stdout.write(f"  - {output_dir}/README.md")
