import os
work_dir = os.path.dirname(os.path.abspath(__file__))


DEBUG = False

os.system(f"python \"{work_dir}/manage.py\" makemigrations task_manager")
os.system(f"python \"{work_dir}/manage.py\" makemigrations user_system")
os.system(f"python \"{work_dir}/manage.py\" makemigrations")
os.system(f"python \"{work_dir}/manage.py\" migrate")

if DEBUG:
    os.system(f"python \"{work_dir}/manage.py\" load_nq_dataset ./task_manager/dataset/hard_questions_refined.jsonl nq_hard_questions")
    # os.system(f"python \"{work_dir}/manage.py\" load_nq_dataset ./task_manager/dataset/hard_questions.jsonl nq_hard_questions")
    # os.system(f"python \"{work_dir}/manage.py\" load_nq_dataset task_manager/dataset/NQ-open.train.jsonl nq_train")

# Start Server
os.system(f"python \"{work_dir}/manage.py\" runserver")