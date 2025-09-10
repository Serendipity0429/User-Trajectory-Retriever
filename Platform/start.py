import os
work_dir = os.path.dirname(os.path.abspath(__file__))


DEBUG = True

if DEBUG:
    # Linux
    if os.name == 'posix':
        # Remove all existing migrations
        os.system(f"rm -rf {work_dir}/task_manager/migrations")
        os.system(f"rm -rf {work_dir}/user_system/migrations")
        os.system(f"rm -rf {work_dir}/db.sqlite3")
    elif os.name == 'nt':
        # Windows
        os.system(f"rmdir /s /q \"{work_dir}\\task_manager\\migrations\"")
        os.system(f"rmdir /s /q \"{work_dir}\\user_system\\migrations\"")
        os.system(f"del /f /q \"{work_dir}\\db.sqlite3\"")

os.system(f"python \"{work_dir}/manage.py\" makemigrations task_manager")
os.system(f"python \"{work_dir}/manage.py\" makemigrations user_system")
os.system(f"python \"{work_dir}/manage.py\" makemigrations")
os.system(f"python \"{work_dir}/manage.py\" migrate")

if DEBUG:
    os.system(f"python \"{work_dir}/manage.py\" load_nq_dataset ./task_manager/dataset/hard_questions_refined.jsonl nq_hard_questions")
    # os.system(f"python \"{work_dir}/manage.py\" load_nq_dataset ./task_manager/dataset/hard_questions.jsonl nq_hard_questions")
    # os.system(f"python \"{work_dir}/manage.py\" load_nq_dataset task_manager/dataset/NQ-open.train.jsonl nq_train")
    # Create a user for testing
    os.system(f"python \"{work_dir}/manage.py\" create_test_user test qwaszx")
    
# Start Server
os.system(f"python \"{work_dir}/manage.py\" runserver")