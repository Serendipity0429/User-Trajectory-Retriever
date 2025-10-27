import os
work_dir = os.path.dirname(os.path.abspath(__file__))


DEBUG = True
REMOTE = False

if DEBUG:
    # Linux
    if os.name == 'posix':
        # Remove all existing migrations
        os.system(f"rm -rf {work_dir}/task_manager/migrations")
        os.system(f"rm -rf {work_dir}/user_system/migrations")
        os.system(f"rm -rf {work_dir}/db.sqlite3")
        os.system(f"rm -rf {work_dir}/media")
    elif os.name == 'nt':
        # Windows
        os.system(f"rmdir /s /q \"{work_dir}\\task_manager\\migrations\"")
        os.system(f"rmdir /s /q \"{work_dir}\\user_system\\migrations\"")
        os.system(f"del /f /q \"{work_dir}\\db.sqlite3\"")
        os.system(f"rmdir /s /q \"{work_dir}\\media\"")

os.system(f"python \"{work_dir}/manage.py\" makemigrations task_manager")
os.system(f"python \"{work_dir}/manage.py\" makemigrations user_system")
os.system(f"python \"{work_dir}/manage.py\" makemigrations")
os.system(f"python \"{work_dir}/manage.py\" migrate")

if DEBUG:
    os.system(f"python \"{work_dir}/manage.py\" load_nq_dataset ./task_manager/dataset/hard_questions_refined.jsonl nq_hard_questions")
    # os.system(f"python \"{work_dir}/manage.py\" load_nq_dataset ./task_manager/dataset/hard_questions.jsonl nq_hard_questions")
    # os.system(f"python \"{work_dir}/manage.py\" load_nq_dataset task_manager/dataset/NQ-open.train.jsonl nq_train")
    # Create a user for testing
    os.system(f"python \"{work_dir}/manage.py\" create_test_user test thuirthuir")
    os.system(f"python \"{work_dir}/manage.py\" create_test_user test1 thuirthuir")
    os.system(f"python \"{work_dir}/manage.py\" create_test_user test2 thuirthuir")
    # Create a superuser for testing
    os.system(f"python \"{work_dir}/manage.py\" create_test_superuser admin thuirthuir --primary")
    
if REMOTE:
    os.system(f"python \"{work_dir}/manage.py\" runserver 0.0.0.0:2904")
else:
    # Start Server
    os.system(f"python \"{work_dir}/manage.py\" runserver")