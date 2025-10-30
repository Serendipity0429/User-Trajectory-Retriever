import os
import shutil
import subprocess
import sys
from pathlib import Path

# --- Configuration ---
# Set to True to clean the project and load development data
DEBUG = True
# Set to True to run the server on 0.0.0.0:2904 for remote access
REMOTE = False
# --- End Configuration ---

# Get the directory of the current script
WORK_DIR = Path(__file__).parent.resolve()
MANAGE_PY = WORK_DIR / "manage.py"

def run_command(command, check=True):
    """Runs a shell command and checks for errors."""
    print(f"Running command: {' '.join(map(str, command))}")
    try:
        # Using sys.executable ensures we use the same python interpreter
        subprocess.run(command, check=check, cwd=WORK_DIR, text=True)
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {e}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print(f"Error: '{command[0]}' not found. Make sure it's in your PATH.", file=sys.stderr)
        sys.exit(1)

def run_manage_py_command(subcommand, *args):
    """Runs a manage.py command."""
    command = [sys.executable, str(MANAGE_PY), subcommand] + list(args)
    run_command(command)

def clean_project():
    """Removes migrations, database, and media files for a clean start."""
    print("--- Cleaning project for a fresh start ---")
    
    # Directories to remove
    dirs_to_remove = [
        WORK_DIR / "task_manager" / "migrations",
        WORK_DIR / "user_system" / "migrations",
        WORK_DIR / "media",
    ]
    
    # Files to remove
    files_to_remove = [
        WORK_DIR / "db.sqlite3",
    ]

    for d in dirs_to_remove:
        if d.exists() and d.is_dir():
            print(f"Removing directory: {d}")
            shutil.rmtree(d)

    for f in files_to_remove:
        if f.exists() and f.is_file():
            print(f"Removing file: {f}")
            f.unlink()
    print("--- Cleaning complete ---")


def setup_development_data():
    """Loads initial data and creates test users for development."""
    print("--- Setting up development data ---")
    run_manage_py_command("load_nq_dataset", "./task_manager/dataset/hard_questions_refined.jsonl", "nq_hard_questions")
    # The following lines are commented out as in the original script.
    # run_manage_py_command("load_nq_dataset", "./task_manager/dataset/hard_questions.jsonl", "nq_hard_questions")
    # run_manage_py_command("load_nq_dataset", "task_manager/dataset/NQ-open.train.jsonl", "nq_train")
    
    # Create test users
    print("Creating test users...")
    run_manage_py_command("create_test_user", "test", "thuirthuir")
    run_manage_py_command("create_test_user", "test1", "thuirthuir")
    run_manage_py_command("create_test_user", "test2", "thuirthuir")
    
    # Create a superuser
    print("Creating test superuser...")
    run_manage_py_command("create_test_superuser", "admin", "thuirthuir", "--primary")
    print("--- Development data setup complete ---")

def main():
    """Main script execution."""
    if DEBUG:
        clean_project()

    # Run migrations
    print("--- Running database migrations ---")
    run_manage_py_command("makemigrations", "task_manager")
    run_manage_py_command("makemigrations", "user_system")
    run_manage_py_command("makemigrations")
    run_manage_py_command("migrate")
    print("--- Migrations complete ---")

    if DEBUG:
        setup_development_data()

    # Start the server
    if REMOTE:
        print("--- Starting server for remote access on 0.0.0.0:2904 ---")
        run_manage_py_command("runserver", "0.0.0.0:2904")
    else:
        print("--- Starting development server ---")
        run_manage_py_command("runserver")

if __name__ == "__main__":
    main()
