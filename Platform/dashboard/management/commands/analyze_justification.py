from django.core.management.base import BaseCommand
from django.db.models import Avg, Count
from task_manager.models import Justification
from urllib.parse import urlparse
import json
import statistics

class Command(BaseCommand):
    help = 'Analyzes the nature of user justifications/evidence.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting Justification Analysis...'))
        
        justifications = Justification.objects.all()
        total_j = justifications.count()
        self.stdout.write(f"Total Justifications Recorded: {total_j}")
        
        if total_j == 0:
            return

        types = justifications.values('evidence_type').annotate(count=Count('id')).order_by('-count')
        self.stdout.write(f"\n[Evidence Formats]")
        for t in types:
            self.stdout.write(f"  {t['evidence_type']}: {t['count']} ({t['count']/total_j*100:.1f}%)")

        domains = []
        for j in justifications:
            try:
                d = urlparse(j.url).netloc
                domains.append(d)
            except:
                pass
        
        from collections import Counter
        top_domains = Counter(domains).most_common(5)
        self.stdout.write(f"\n[Trusted Sources (Gold Evidence)]")
        for d, c in top_domains:
            self.stdout.write(f"  {d}: {c}")

        text_lengths = []
        for j in justifications:
            if j.text:
                text_lengths.append(len(j.text))
        
        if text_lengths:
            avg_len = statistics.mean(text_lengths)
            self.stdout.write(f"\n[Evidence Granularity]")
            self.stdout.write(f"Avg Character Length of Justification: {avg_len:.0f}")

        self.stdout.write('-----------------------------------')
