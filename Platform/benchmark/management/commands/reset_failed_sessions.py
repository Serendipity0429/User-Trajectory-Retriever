"""
Reset failed sessions for re-running. Context exceeded errors are auto-skipped by the pipeline.

Usage:
    python manage.py reset_failed_sessions           # Reset all retryable errors
    python manage.py reset_failed_sessions --dry-run # Preview only
"""
from django.core.management.base import BaseCommand
from benchmark.models import MultiTurnTrial, MultiTurnSession


class Command(BaseCommand):
    help = 'Reset failed sessions for re-running'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Preview without changes')

    def handle(self, *args, **options):
        # Find sessions with error trials (but not already completed)
        error_sessions = MultiTurnSession.objects.filter(
            is_completed=False,
            trials__status='error'
        ).distinct().prefetch_related('trials')

        # Separate context exceeded (permanent) from retryable errors
        retryable = []
        permanent = []

        for session in error_sessions:
            has_context_error = False
            for trial in session.trials.filter(status='error'):
                error_msg = str(trial.log.get('error', '')) if trial.log else ''
                if 'context length' in error_msg.lower() or 'maximum context' in error_msg.lower():
                    has_context_error = True
                    break

            if has_context_error:
                permanent.append(session)
            else:
                retryable.append(session)

        self.stdout.write(f'Retryable errors: {len(retryable)}')
        self.stdout.write(f'Permanent errors (context exceeded): {len(permanent)}')

        if options['dry_run']:
            self.stdout.write('\n--dry-run: No changes made')
            return

        # Reset retryable sessions
        for session in retryable:
            if session.pipeline_type == 'browser_agent':
                # Browser agent: clear ALL trials, start fresh (context accumulates)
                session.trials.all().delete()
            else:
                # Other pipelines: clear error trials, keep completed ones
                session.trials.filter(status='error').delete()
            session.status = 'pending'
            session.save()

        # Mark permanent errors as completed (pipeline will skip them anyway)
        for session in permanent:
            session.is_completed = True
            session.status = 'error'
            session.save()

        self.stdout.write(self.style.SUCCESS(f'\nReset {len(retryable)} sessions for retry'))
        self.stdout.write(f'Marked {len(permanent)} sessions as permanently failed')
