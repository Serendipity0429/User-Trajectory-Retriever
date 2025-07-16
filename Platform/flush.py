import os
import shutil
work_dir = os.path.dirname(os.path.abspath(__file__))

os.system(f"python \"{work_dir}/manage.py\" flush --no-input")

# Delete all migrations in task_manager and user_system
if os.path.exists(f"{work_dir}/task_manager/migrations"):
    shutil.rmtree(f"{work_dir}/task_manager/migrations")
if os.path.exists(f"{work_dir}/user_system/migrations"):
    shutil.rmtree(f"{work_dir}/user_system/migrations")

# Delete the SQLite database file
if os.path.exists(f"{work_dir}/db.sqlite3"):
    os.remove(f"{work_dir}/db.sqlite3")
    
os.system(f"python \"{work_dir}/manage.py\" makemigrations task_manager")
os.system(f"python \"{work_dir}/manage.py\" makemigrations user_system")
os.system(f"python \"{work_dir}/manage.py\" makemigrations")
os.system(f"python \"{work_dir}/manage.py\" migrate")
os.system(f"python \"{work_dir}/manage.py\" load_nq_dataset ./task_manager/dataset/hard_questions_refined.jsonl nq_hard_questions")