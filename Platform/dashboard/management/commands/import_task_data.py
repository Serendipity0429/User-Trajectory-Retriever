"""
Management command to import task_manager data from HuggingFace-compatible JSONL format.

Usage:
    python manage.py import_task_data --input ./export/data.jsonl --test
    python manage.py import_task_data --input ./export/data.jsonl
"""

import getpass

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import authenticate

from dashboard.utils.importer import TaskManagerImporter, ImportValidationError


class Command(BaseCommand):
    help = 'Import task_manager data from HuggingFace-compatible JSONL format'

    def add_arguments(self, parser):
        parser.add_argument(
            '--input',
            type=str,
            required=True,
            help='Input JSONL file path'
        )
        parser.add_argument(
            '--test',
            action='store_true',
            help='Test mode: validate and preview without making changes (dry run)'
        )

    def handle(self, *args, **options):
        input_file = options['input']
        test_mode = options['test']

        importer = TaskManagerImporter()

        if test_mode:
            self._handle_test_mode(importer, input_file)
        else:
            self._handle_import(importer, input_file)

    def _handle_test_mode(self, importer, input_file):
        """Handle dry-run/test mode."""
        self.stdout.write(self.style.WARNING('[DRY RUN] Validating import...'))

        preview = importer.validate_and_preview(input_file)

        if preview['is_valid']:
            self.stdout.write(self.style.SUCCESS('Valid JSONL format'))
        else:
            self.stdout.write(self.style.ERROR('Validation errors:'))
            for error in preview['errors'][:10]:  # Show first 10 errors
                self.stdout.write(f"  - {error}")
            if len(preview['errors']) > 10:
                self.stdout.write(f"  ... and {len(preview['errors']) - 10} more errors")
            return

        self.stdout.write('')
        self.stdout.write('Would delete:')
        self.stdout.write(f"  - {preview['would_delete']['users']} existing users (excluding admins)")
        self.stdout.write(f"  - {preview['would_delete']['tasks']} existing tasks")
        self.stdout.write(f"  - {preview['would_delete']['trials']} existing trials")
        self.stdout.write(f"  - {preview['would_delete']['webpages']} existing webpages")

        self.stdout.write('')
        self.stdout.write('Would import:')
        self.stdout.write(f"  - {preview['would_import']['participants']} participants")
        self.stdout.write(f"  - {preview['would_import']['tasks']} tasks")
        self.stdout.write(f"  - {preview['would_import']['trials']} trials")
        self.stdout.write(f"  - {preview['would_import']['webpages']} webpages")

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('No changes made to database.'))

    def _handle_import(self, importer, input_file):
        """Handle real import with admin verification."""
        # First validate
        preview = importer.validate_and_preview(input_file)

        if not preview['is_valid']:
            self.stdout.write(self.style.ERROR('Validation failed:'))
            for error in preview['errors'][:10]:
                self.stdout.write(f"  - {error}")
            raise CommandError('Cannot import: validation errors found')

        # Check if there's existing data
        if preview['existing_stats']['has_data']:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING('Existing data detected:'))
            self.stdout.write(f"  - {preview['existing_stats']['task_count']} tasks")
            self.stdout.write(f"  - {preview['existing_stats']['user_count']} users (excluding {preview['existing_stats']['admin_count']} admins)")
            self.stdout.write(f"  - {preview['existing_stats']['webpage_count']} webpages")
            self.stdout.write('')
            self.stdout.write(self.style.ERROR(
                'This will DELETE all existing data (except admin accounts) '
                'and import from the JSONL file.'
            ))
            self.stdout.write('')

            # Require admin authentication
            username = input('Enter admin username: ')
            password = getpass.getpass('Enter admin password: ')

            user = authenticate(username=username, password=password)
            if not user or not user.is_superuser:
                raise CommandError('Authentication failed or user is not an admin.')

            self.stdout.write(self.style.SUCCESS(f'Authenticated as {username}'))

        # Confirm
        self.stdout.write('')
        self.stdout.write('About to import:')
        self.stdout.write(f"  - {preview['would_import']['participants']} participants")
        self.stdout.write(f"  - {preview['would_import']['tasks']} tasks")
        self.stdout.write(f"  - {preview['would_import']['trials']} trials")
        self.stdout.write(f"  - {preview['would_import']['webpages']} webpages")
        self.stdout.write('')

        confirm = input('Proceed with import? (yes/no): ')
        if confirm.lower() != 'yes':
            self.stdout.write(self.style.WARNING('Import cancelled.'))
            return

        # Perform import
        self.stdout.write('Importing...')
        try:
            stats = importer.import_from_file(input_file)
        except ImportValidationError as e:
            raise CommandError(f'Import failed: {e}')

        self.stdout.write(self.style.SUCCESS('Import completed!'))
        self.stdout.write(f"  - Participants imported: {stats['participants_imported']}")
        self.stdout.write(f"  - Tasks imported: {stats['tasks_imported']}")
        self.stdout.write(f"  - Trials imported: {stats['trials_imported']}")
        self.stdout.write(f"  - Webpages imported: {stats['webpages_imported']}")
