from django.core.management.base import BaseCommand
from django.db.models import Avg, Count
from django.db.models.functions import Length
from task_manager.models import Justification
from urllib.parse import urlparse
from collections import Counter
import statistics

class Command(BaseCommand):
    help = 'Analyzes the nature of user justifications/evidence.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting Justification Analysis...'))
        
        total_j = Justification.objects.count()
        self.stdout.write(f"Total Justifications Recorded: {total_j}")
        
        if total_j == 0:
            return

        types = Justification.objects.values('evidence_type').annotate(count=Count('id')).order_by('-count')
        self.stdout.write(f"\n[Evidence Formats]")
        for t in types:
            self.stdout.write(f"  {t['evidence_type']}: {t['count']} ({t['count']/total_j*100:.1f}%)")

        # Efficiently extract domains
        urls = Justification.objects.values_list('url', flat=True)
        domains = []
        for u in urls:
            try:
                d = urlparse(u).netloc
                domains.append(d)
            except:
                pass
        
        top_domains = Counter(domains).most_common(5)
        self.stdout.write(f"\n[Trusted Sources (Gold Evidence)]")
        for d, c in top_domains:
            self.stdout.write(f"  {d}: {c}")

        # Efficiently calculate average length using DB function
        avg_len = Justification.objects.exclude(text__isnull=True).exclude(text='').annotate(text_len=Length('text')).aggregate(avg=Avg('text_len'))['avg']
        
        if avg_len:
            self.stdout.write(f"\n[Evidence Granularity]")
            self.stdout.write(f"Avg Character Length of Justification: {avg_len:.0f}")

        self.stdout.write('-----------------------------------')
