from django.core.management.base import BaseCommand
from task_manager.models import TaskTrial, Justification
import difflib

class Command(BaseCommand):
    help = 'Analyzes Answer Formulation (Extraction vs Synthesis).'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting Formulation Analysis...'))
        
        trials = TaskTrial.objects.prefetch_related('justifications').exclude(answer='undefined')
        total_trials = trials.count()
        self.stdout.write(f"Total trials to analyze: {total_trials}")
        
        strategies = {
            'verbatim': {'correct': 0, 'total': 0}, 
            'paraphrase': {'correct': 0, 'total': 0}, 
            'synthesis': {'correct': 0, 'total': 0}
        }
        
        count = 0
        processed = 0
        
        for t in trials.iterator(chunk_size=100):
            processed += 1
            if processed % 500 == 0:
                self.stdout.write(f"Processed {processed}/{total_trials} trials...")

            ans = t.answer.lower().strip()
            if not ans: continue
            
            evidence_texts = [j.text.lower().strip() for j in t.justifications.all() if j.text]
            full_evidence = " ".join(evidence_texts)
            if not full_evidence: continue
            
            count += 1
            
            ans_words = ans.split()
            found_words = 0
            for w in ans_words:
                if w in full_evidence: found_words += 1
            
            overlap_ratio = found_words / len(ans_words) if ans_words else 0
            
            category = 'synthesis'
            if overlap_ratio > 0.8: category = 'verbatim'
            elif overlap_ratio > 0.4: category = 'paraphrase'
            
            strategies[category]['total'] += 1
            if t.is_correct: strategies[category]['correct'] += 1

        self.stdout.write(f"\nAnalyzed {count} formulation pairs.")
        
        self.stdout.write(f"\n[Strategy Performance]")
        for cat, stats in strategies.items():
            tot = stats['total']
            acc = (stats['correct'] / tot * 100) if tot > 0 else 0
            share = (tot / count * 100) if count > 0 else 0
            self.stdout.write(f"  {cat.capitalize()}: {share:.1f}% usage | Accuracy: {acc:.1f}%")
