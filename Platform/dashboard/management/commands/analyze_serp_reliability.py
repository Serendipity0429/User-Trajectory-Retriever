from django.core.management.base import BaseCommand
from task_manager.models import Justification
from urllib.parse import urlparse

class Command(BaseCommand):
    help = 'Analyzes reliability of SERP-based justifications (Text-based Heuristic).'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting SERP Reliability Analysis (Text Heuristic)...'))
        
        serp_domains = ['bing.com', 'google.com']
        
        ai_count = 0
        ai_correct = 0
        snippet_count = 0
        snippet_correct = 0
        
        for j in Justification.objects.select_related('belong_task_trial'):
            domain = urlparse(j.url).netloc
            if not any(sd in domain for sd in serp_domains):
                continue
                
            text = j.text or ""
            is_correct = 1 if j.belong_task_trial.is_correct else 0
            
            has_ellipsis = '...' in text
            is_long_fluent = len(text) > 150 and not has_ellipsis
            
            if is_long_fluent:
                ai_count += 1
                ai_correct += is_correct
            else:
                snippet_count += 1
                snippet_correct += is_correct

        if ai_count > 0:
            self.stdout.write(f"\n[Fluent/Long Summaries (Likely AI/Featured)]")
            self.stdout.write(f"  Count: {ai_count}")
            self.stdout.write(f"  Accuracy: {ai_correct/ai_count*100:.2f}%")
            
        if snippet_count > 0:
            self.stdout.write(f"\n[Fragmented Snippets (Organic)]")
            self.stdout.write(f"  Count: {snippet_count}")
            self.stdout.write(f"  Accuracy: {snippet_correct/snippet_count*100:.2f}%")
