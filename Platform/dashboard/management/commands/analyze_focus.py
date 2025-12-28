from django.core.management.base import BaseCommand
from task_manager.models import Webpage
import json
import statistics

class Command(BaseCommand):
    help = 'Analyzes focus, multitasking, and reading focus.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting Focus Analysis...'))
        
        pages = Webpage.objects.exclude(event_list=[]).exclude(event_list__exact='[]').order_by('-id')[:500]
        
        focus_switches = [] 
        hover_text_lengths = [] 
        
        for page in pages:
            try:
                events = page.event_list
                if isinstance(events, str):
                    events = json.loads(events)
                if not events:
                    continue

                blurs = len([e for e in events if e.get('type') == 'blur'])
                focus_switches.append(blurs)

                for e in events:
                    if e.get('type') == 'hover':
                        content = e.get('content', '')
                        if content:
                            hover_text_lengths.append(len(content))
            except:
                pass

        self.stdout.write(f"Analyzed {len(pages)} pages.")

        avg_blurs = statistics.mean(focus_switches) if focus_switches else 0
        self.stdout.write(f"\n[Attention Span]")
        self.stdout.write(f"Avg Tab Switches/Blurs per Page: {avg_blurs:.2f}")
        
        if hover_text_lengths:
            avg_len = statistics.mean(hover_text_lengths)
            self.stdout.write(f"\n[Reading Focus]")
            self.stdout.write(f"Avg Length of Hovered Text: {avg_len:.0f} chars")
            
            short = len([l for l in hover_text_lengths if l < 50])
            long_text = len([l for l in hover_text_lengths if l > 200])
            total = len(hover_text_lengths)
            
            self.stdout.write(f"  Short Items (<50 chars): {short/total*100:.1f}%")
            self.stdout.write(f"  Long Blocks (>200 chars): {long_text/total*100:.1f}%")
            
        self.stdout.write('-----------------------------------')
