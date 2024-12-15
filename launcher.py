import os
import sys
import subprocess
import platform

# Constants
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_DIR = os.path.join(PROJECT_DIR, "venv")
REQUIREMENTS_FILE = os.path.join(PROJECT_DIR, "requirements.txt")
MAIN_PROGRAM = os.path.join(PROJECT_DIR, "no_more_running.pyw")


def run_command(command, shell=True):
    """Runs a system command and exits on failure."""
    result = subprocess.run(command, shell=shell)
    if result.returncode != 0:
        print(f"Error: Command failed - {command}")
        sys.exit(1)


def create_venv():
    """Creates the virtual environment if it doesn't exist."""
    if not os.path.exists(VENV_DIR):
        print("Creating virtual environment...")
        if platform.system() == "Windows":
            run_command(f"python -m venv {VENV_DIR}")
        else:
            run_command(f"python3 -m venv {VENV_DIR}")
    else:
        print("Virtual environment already exists.")


def install_dependencies():
    """Installs required dependencies into the virtual environment."""
    pip_path = (
        os.path.join(VENV_DIR, "Scripts", "pip")  # Windows
        if platform.system() == "Windows"
        else os.path.join(VENV_DIR, "bin", "pip")  # Linux/Mac
    )

    print("Installing required dependencies...")
    run_command(f"{pip_path} install -r {REQUIREMENTS_FILE}")


def activate_and_launch():
    """Activates the virtual environment and launches the main program."""
    python_path = (
        os.path.join(VENV_DIR, "Scripts", "python")  # Windows
        if platform.system() == "Windows"
        else os.path.join(VENV_DIR, "bin", "python")  # Linux/Mac
    )

    print("Launching the main program...")
    run_command(f"{python_path} {MAIN_PROGRAM}")


def main():
    """Main launcher logic."""
    # Step 1: Ensure virtual environment exists
    create_venv()

    # Step 2: Install required dependencies
    install_dependencies()

    # Step 3: Activate the environment and run the program
    activate_and_launch()


if __name__ == "__main__":
    main()