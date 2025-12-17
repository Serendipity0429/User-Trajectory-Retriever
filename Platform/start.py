import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Union
from dotenv import load_dotenv
import os

load_dotenv()


# --- Configuration ---
# Read settings from environment variables.
IS_DEBUG: bool = os.getenv("DJANGO_DEBUG", "True").lower() in ("true", "1", "t")
IS_REMOTE: bool = os.getenv("REMOTE", "False").lower() in ("true", "1", "t")

# Determine bind address based on environment variables.
if IS_REMOTE:
    BIND_ADDRESS: str = os.getenv("BIND_ADDRESS_REMOTE", "0.0.0.0:8000")
else:
    BIND_ADDRESS: str = os.getenv("BIND_ADDRESS_LOCAL", "127.0.0.1:8000")
# --- End Configuration ---


# --- Constants ---
WORK_DIR: Path = Path(__file__).parent.resolve()
MANAGE_PY: Path = WORK_DIR / "manage.py"


# --- ANSI Color Codes for Console Output ---
class Colors:
    """ANSI color codes for styling terminal output."""

    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


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
        subprocess.run(
            command,
            check=check,
            cwd=WORK_DIR,
            text=True,
            stdout=sys.stdout,
            stderr=sys.stderr,
        )
    except subprocess.CalledProcessError as e:
        print(f"{Colors.FAIL}Error running command: {e}{Colors.ENDC}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print(
            f"{Colors.FAIL}Error: '{command[0]}' not found. Is it in your PATH?{Colors.ENDC}",
            file=sys.stderr,
        )
        sys.exit(1)


def run_manage_py_command(subcommand: str, *args: str) -> None:
    """
    Constructs and runs a Django manage.py command.

    Args:
        subcommand: The manage.py command to run (e.g., 'migrate').
        *args: Additional arguments for the command.
    """
    command: List[Union[str, Path]] = [sys.executable, MANAGE_PY, subcommand] + list(
        args
    )
    run_command(command)


def clean_project() -> None:
    """
    Removes migration files, flushes the database, and clears media assets for a clean start.
    """
    print_header("Cleaning project for a fresh start")

    # Define paths for directories and files to be removed.
    paths_to_remove: List[Path] = [
        WORK_DIR / "task_manager" / "migrations",
        WORK_DIR / "user_system" / "migrations",
        WORK_DIR / "discussion" / "migrations",
        WORK_DIR / "benchmark" / "migrations",
        WORK_DIR / "dashboard" / "migrations",
        WORK_DIR / "msg_system" / "migrations",
        WORK_DIR / "media" / "attachments",
        WORK_DIR / "media" / "evidence_images",
        WORK_DIR / "media" / "benchmark_datasets",
        WORK_DIR / "staticfiles",
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

    print_info("Flushing the database...")
    run_manage_py_command("flush", "--no-input")

    print_success("--- Cleaning complete ---")


def setup_development_data() -> None:
    """
    Loads initial data and creates test users for a development environment.
    """
    print_header("Setting up development data")

    # Load dataset.
    run_manage_py_command(
        "load_nq_dataset",
        "./data/hard_questions_refined.jsonl",
        "nq_hard_questions",
    )

    run_manage_py_command(
        "load_nq_dataset", "./data/tutorial_questions.jsonl", "tutorial"
    )

    # Create test users.
    print_info("Creating test users...")
    users = {"test": "thuirtest"}
    test_user_num = 2
    for i in range(test_user_num):
        users[f"user{i}"] = f"thuiruser{i}"
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
    parser = argparse.ArgumentParser(description="Start the Django server.")
    parser.add_argument(
        "--clean",
        action="store_true",
        default=False,
        help="Clean project, then set up development data. Only works in debug mode.",
    )
    args = parser.parse_args()

    if args.clean:
        RETYPE_CNT = 1 if IS_DEBUG else 3
        while RETYPE_CNT > 0:
            RETYPE_CNT -= 1
            print_warning("Are you sure you want to clean the project?")
            print_warning(
                "This will delete the database and media files. (y/n): ", end=""
            )
            if input().strip().lower() != "y":
                print_info("Aborting clean.")
                sys.exit(0)
        clean_project()

    # Apply database migrations.
    print_header("Running database migrations")
    for app in ["task_manager", "user_system", "discussion", "msg_system", "benchmark"]:
        run_manage_py_command("makemigrations", app)
    run_manage_py_command("makemigrations")
    run_manage_py_command("migrate")
    print_success("--- Migrations complete ---")

    if args.clean and IS_DEBUG:
        setup_development_data()

    # Start the appropriate server.
    if IS_DEBUG:
        print_header(f"Starting Django development server on {BIND_ADDRESS}")
        run_manage_py_command("runserver", BIND_ADDRESS)
    else:
        print_header(f"Starting Gunicorn production server on {BIND_ADDRESS}")
        print_info("Collecting static files...")
        run_manage_py_command("collectstatic", "--noinput")
        print_success("--- Static files collected ---")

        # Construct and run the Gunicorn command.
        gunicorn_command = [
            "gunicorn",
            "--bind",
            BIND_ADDRESS,
            "annotation_platform.wsgi:application",
        ]
        run_command(gunicorn_command)


if __name__ == "__main__":
    main()
