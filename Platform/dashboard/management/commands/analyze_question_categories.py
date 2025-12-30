from django.core.management.base import BaseCommand
from django.db.models import Avg, Count
from task_manager.models import Task, TaskDatasetEntry
import statistics

class Command(BaseCommand):
    help = 'Analyzes question difficulty across semantic categories (Factoid, Reasoning, Comparison, etc.).'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting Question Difficulty Analysis...'))

        # Defined Categories
        # Time: When, Date
        # Person: Who
        # Quantity: How many, number, angle, stats
        # Entity: What, Which, Where (Names, Places, Things)
        # Description: How did, Meaning, Explanation

        QUESTION_MAP = {
            # Time
            "when did the sims 4 toddlers come out?": "Time",
            "when did mcgee became a regular on ncis?": "Time",
            "when were official birth certificates first issued in the united states?": "Time",
            "when did last podcast on the left start": "Time",
            "when does boomer find out she a cylon?": "Time",
            "when does season 18 of law and order: svu start": "Time",
            "when does the last episode of izombie air as of june 12, 2025?": "Time",
            "when did the dallas cowboys win their last playoff game as of june 12, 2025?": "Time",
            "when was the letter j introduced to the alphabet?": "Time",
            "when does jo come in grey's anatomy": "Time",
            "when was i look at the world poem written?": "Time",
            "when does scully come back in season 2?": "Time",
            "when do dwight and angela start dating again?": "Time",
            "when did the flash season 4 episode 14 come out?": "Time",
            "when did it become law to stand for the national anthem in the united states?": "Time",
            "when does elena turn into a vampire in the tv series?": "Time",
            "what was the date of the signing of the declaration of independence": "Time",
            "when do the walking dead comics come out?": "Time",

            # Person
            "who developed the central processing unit (cpu)?": "Person",
            "who sang rip it up and start again?": "Person",
            "who became the king of ayodhya after rama?": "Person",
            "who has the most yards per carry in nfl history until june 12, 2025?": "Person",
            "who was the girl in the video brenda got a baby?": "Person",
            "who plays reggie the robot in justin's house": "Person",
            "who sings gone gone gone she been gone so long?": "Person",
            "who plays rachel on jessie punch dumped love?": "Person",
            "who dies in the lost city of z?": "Person",
            "who votes to elect a rajya sabha memmber": "Person",
            "who played lionel in as time goes by?": "Person",
            "who sang smoke gets in your eyes first?": "Person",
            "who was the first british team to win the european cup?": "Person", # Team acts as Person/Agent
            "who plays kevin's shrink on kevin probably saves the world?": "Person",
            "who commissioned the first christmas card in 1843?": "Person",
            "who was the leader of the zulu in south africa who led the fight against the british?": "Person",
            "who played truman capote in in cold blood?": "Person",
            "who played michael jackson in jackson 5 movie?": "Person",
            "who did the dominican republic gain its independence from?": "Person", # Agent/Entity
            "who plays rose in the fall season 2?": "Person",
            "who won the nobel prize in physics in 2024?": "Person",

            # Quantity
            "what is the angle of the tower of pisa?": "Quantity",
            "how many pages are in the book inside out and back again?": "Quantity",
            "how many books are there in the one piece series as of june 12, 2025?": "Quantity",
            "how many consecutive games with at least 20 points is the longest streak in nba history?": "Quantity",
            "what were the highest runs in india south africa test series 2018?": "Quantity",
            "how many walker texas ranger seasons are there": "Quantity",
            "how many professors are there in thuir laboratory?": "Quantity",
            "what are the term limits for house of representatives in united states?": "Quantity", # Term limit is a number/rule

            # Entity (What/Which/Where)
            "in what episode does goku give up against cell?": "Entity",
            "what is the name of the last episode of spongebob before june 12, 2025?": "Entity",
            "what is the name of the boundary line between india and bangladesh?": "Entity",
            "what does g stand for in ncis los angeles?": "Entity",
            "which battle ended britain's support for the south?": "Entity",
            "which type of hematoma is a result of torn bridging meningeal veins?": "Entity",
            "what is the cross on a letter t called?": "Entity",
            "where was it happened at the world fair filmed": "Entity",
            "what is the latest version of chrome for linux as of june 12, 2025?": "Entity",
            "which country host cop30?": "Entity",
            "which high school did kaiming he graduate from?": "Entity",
            "where does junior want to go to find hope": "Entity",

            # Description / Meaning
            "how did leo dalton die in silent witness?": "Description",
            "what is the meaning of the name comanche?": "Description",
        }

        # Data structure to hold stats per category
        categories = ['Time', 'Person', 'Quantity', 'Entity', 'Description', 'Other']
        stats = {cat: {
            'count': 0, 
            'pre_diff': [], 
            'post_diff': [], 
            'accuracy': [],
            'time': []
        } for cat in categories}

        tasks = Task.objects.select_related('content', 'pretaskannotation', 'posttaskannotation')\
                            .prefetch_related('tasktrial_set', 'webpage_set')
        
        total_tasks = tasks.count()
        self.stdout.write(f"Analyzing {total_tasks} tasks...")
        
        processed = 0
        for task in tasks:
            processed += 1
            if processed % 500 == 0:
                self.stdout.write(f"Processed {processed}/{total_tasks} tasks...")

            if not task.content: continue
            
            q_text = task.content.question.lower().strip()
            
            # Direct Mapping
            assigned_cat = QUESTION_MAP.get(q_text)
            
            # Fallback for slight variations or missing ones
            if not assigned_cat:
                if 'when' in q_text or 'date' in q_text or 'year' in q_text:
                    assigned_cat = 'Time'
                elif 'who' in q_text:
                    assigned_cat = 'Person'
                elif 'how many' in q_text or 'count' in q_text:
                    assigned_cat = 'Quantity'
                elif 'what' in q_text or 'which' in q_text or 'where' in q_text:
                    assigned_cat = 'Entity'
                elif 'how' in q_text: # General how
                    assigned_cat = 'Description'
                else:
                    assigned_cat = 'Other'
            
            # 2. Gather Metrics
            s = stats[assigned_cat]
            s['count'] += 1
            
            # Difficulty (Pre/Post)
            try:
                if hasattr(task, 'pretaskannotation') and task.pretaskannotation.difficulty is not None:
                    s['pre_diff'].append(task.pretaskannotation.difficulty)
            except: pass
            
            try:
                if hasattr(task, 'posttaskannotation') and task.posttaskannotation.difficulty_actual is not None:
                    s['post_diff'].append(task.posttaskannotation.difficulty_actual)
            except: pass
            
            # Accuracy (Actual Difficulty)
            trials = list(task.tasktrial_set.all())
            if trials:
                is_correct = any(t.is_correct for t in trials)
                s['accuracy'].append(1 if is_correct else 0)
                
            # Time (Effort)
            # Use sum of dwell times
            dwells = [p.dwell_time for p in task.webpage_set.all() if p.dwell_time]
            total_time = sum(dwells) / 1000.0 if dwells else 0
            if total_time > 0:
                s['time'].append(total_time)

        # 3. Output Table
        header = f"{'Type':<12} | {'Count':<6} | {'Pre-Diff':<10} | {'Post-Diff':<10} | {'Gap':<6} | {'Accuracy':<10} | {'Avg Time (s)'}"
        self.stdout.write("\n" + header)
        self.stdout.write("-" * len(header))

        for cat in categories:
            data = stats[cat]
            if data['count'] == 0: continue
            
            avg_pre = statistics.mean(data['pre_diff']) if data['pre_diff'] else 0
            avg_post = statistics.mean(data['post_diff']) if data['post_diff'] else 0
            gap = avg_post - avg_pre
            acc = (statistics.mean(data['accuracy']) * 100) if data['accuracy'] else 0
            avg_time = statistics.mean(data['time']) if data['time'] else 0
            
            self.stdout.write(f"{cat:<12} | {data['count']:<6} | {avg_pre:<10.2f} | {avg_post:<10.2f} | {gap:<+6.2f} | {acc:<10.1f}% | {avg_time:.1f}")

        self.stdout.write('\n-----------------------------------')
        self.stdout.write("Metrics Key:")
        self.stdout.write("- Pre-Diff: Expected difficulty (0-4)")
        self.stdout.write("- Post-Diff: Actual perceived difficulty (0-4)")
        self.stdout.write("- Gap: Positive = Harder than expected, Negative = Easier than expected")