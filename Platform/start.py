#!/usr/bin/env python3
"""
This script automates the setup and execution of a Django development server.

It provides functionalities for:
- Cleaning the project by removing migration files, the database, and media assets.
- Running database migrations.
- Setting up development data, including loading datasets and creating test users.
- Starting the Django development server with optional remote access.

Features:
- A `--debug` mode that performs a complete project cleanup and sets up fresh 
  development data.
- User confirmation prompt when running in debug mode to prevent accidental 
  data loss.
- Clear, color-coded console output for better readability of script operations.

Usage:
- To start the server normally: `python start.py`
- To start in debug mode for a clean environment: `python start.py --debug`
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Union

# --- Configuration ---
# Set to True to run the server on 0.0.0.0:2904 for remote access.
REMOTE: bool = False
# --- End Configuration ---

# --- Constants ---
WORK_DIR: Path = Path(__file__).parent.resolve()
MANAGE_PY: Path = WORK_DIR / "manage.py"

# --- ANSI Color Codes for Console Output ---
class Colors:
    """ANSI color codes for styling terminal output."""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_header(message: str) -> None:
    """Prints a formatted header message to the console."""
    print(f"\n{Colors.HEADER}{Colors.BOLD}--- {message} ---" + Colors.ENDC)

def print_success(message: str) -> None:
    """Prints a success message."""
    print(f"{Colors.OKGREEN}{message}{Colors.ENDC}")

def print_warning(message: str, end="\n") -> None:
    """Prints a warning message."""
    print(f"{Colors.WARNING}{message}{Colors.ENDC}", end=end)

def print_info(message: str) -> None:
    """Prints an informational message."""
    print(f"{Colors.OKCYAN}{message}{Colors.ENDC}")

def run_command(command: List[Union[str, Path]], check: bool = True) -> None:
    """
    Executes a shell command and handles potential errors.

    Args:
        command: A list representing the command and its arguments.
        check: If True, raises CalledProcessError for non-zero exit codes.
    """
    print_info(f"Running command: {' '.join(map(str, command))}")
    try:
        subprocess.run(command, check=check, cwd=WORK_DIR, text=True, 
                       stdout=sys.stdout, stderr=sys.stderr)
    except subprocess.CalledProcessError as e:
        print(f"{Colors.FAIL}Error running command: {e}{Colors.ENDC}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print(f"{Colors.FAIL}Error: '{command[0]}' not found. Is it in your PATH?{Colors.ENDC}", file=sys.stderr)
        sys.exit(1)

def run_manage_py_command(subcommand: str, *args: str) -> None:
    """
    Constructs and runs a Django manage.py command.

    Args:
        subcommand: The manage.py command to run (e.g., 'migrate').
        *args: Additional arguments for the command.
    """
    command: List[Union[str, Path]] = [sys.executable, MANAGE_PY, subcommand] + list(args)
    run_command(command)

def clean_project() -> None:
    """
    Removes migration files, the database, and media assets for a clean start.
    """
    print_header("Cleaning project for a fresh start")
    
    # Define paths for directories and files to be removed.
    paths_to_remove: List[Path] = [
        WORK_DIR / "task_manager" / "migrations",
        WORK_DIR / "user_system" / "migrations",
        WORK_DIR / "discussion" / "migrations",
        WORK_DIR / "db.sqlite3",
        WORK_DIR / "media" / "attachments",
    ]

    for path in paths_to_remove:
        try:
            if path.is_dir():
                print_info(f"Removing directory: {path}")
                shutil.rmtree(path)
            elif path.is_file():
                print_info(f"Removing file: {path}")
                path.unlink()
        except FileNotFoundError:
            print_warning(f"Path not found, skipping: {path}")

    print_success("--- Cleaning complete ---")

def setup_development_data() -> None:
    """
    Loads initial data and creates test users for a development environment.
    """
    print_header("Setting up development data")
    
    # Load dataset.
    run_manage_py_command(
        "load_nq_dataset", 
        "./task_manager/dataset/hard_questions_refined.jsonl", 
        "nq_hard_questions"
    )
    
    # Create test users.
    print_info("Creating test users...")
    users = {"test": "thuirtest", "test1": "thuirtest1", "test2": "thuirtest2"}
    for username, password in users.items():
        run_manage_py_command("create_test_user", username, password)
    
    # Create a primary superuser.
    print_info("Creating test superuser...")
    run_manage_py_command("create_test_superuser", "admin", "thuirthuir", "--primary")
    
    print_success("--- Development data setup complete ---")

def main() -> None:
    """
    Main script execution flow.
    """
    parser = argparse.ArgumentParser(description="Start the Django development server.")
    parser.add_argument(
        "--debug", 
        action="store_true", 
        default=False,
        help="Run in debug mode (clean project, load development data)."
    )
    args = parser.parse_args()
    
    if args.debug:
        print_warning("Are you sure you want to run in debug mode?")
        print_warning("This will delete the database and media files. (y/n): ", end="")
        if input().strip().lower() != 'y':
            print_info("Aborting debug mode.")
            sys.exit(0)
        
        clean_project()

    # Apply database migrations.
    print_header("Running database migrations")
    for app in ["task_manager", "user_system", "discussion"]:
        run_manage_py_command("makemigrations", app)
    run_manage_py_command("makemigrations")
    run_manage_py_command("migrate")
    print_success("--- Migrations complete ---")

    if args.debug:
        setup_development_data()

    # Start the Django server.
    if REMOTE:
        print_header("Starting server for remote access on 0.0.0.0:2904")
        run_manage_py_command("runserver", "0.0.0.0:2904")
    else:
        print_header("Starting development server")
        run_manage_py_command("runserver")

if __name__ == "__main__":
    main()