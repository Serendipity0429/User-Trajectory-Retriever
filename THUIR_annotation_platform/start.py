import os
work_dir = os.path.dirname(os.path.abspath(__file__))
os.system("python \"" + work_dir + "/manage.py\" makemigrations task_manager")
os.system("python \"" + work_dir + "/manage.py\" makemigrations user_system")
os.system("python \"" + work_dir + "/manage.py\" makemigrations")
os.system("python \"" + work_dir + "/manage.py\" migrate")