import os
import sys
import subprocess
import platform
import urllib.request
import shutil

# Constants
REPO_URL = "https://github.com/DannyDzNuts/No-More-Running.git"
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_DIR = os.path.join(PROJECT_DIR, "venv")
REQUIREMENTS_FILE = os.path.join(PROJECT_DIR, "requirements.txt")
MAIN_PROGRAM = os.path.join(PROJECT_DIR, "no_more_running.pyw")

# Helper Functions
def run_command(command, shell=True, silent=False):
    """Runs a system command and exits on failure."""
    if silent:
        result = subprocess.run(command, shell=shell, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    else:
        result = subprocess.run(command, shell=shell)

    if result.returncode != 0:
        print(f"Error: Command failed - {command}")
        if silent:
            print(result.stderr.decode())
        sys.exit(1)

def download_file(url, destination):
    """Downloads a file from a URL to a destination."""
    print(f"Downloading {url}...")
    with urllib.request.urlopen(url) as response, open(destination, 'wb') as out_file:
        shutil.copyfileobj(response, out_file)

def ensure_git():
    """Ensures Git is installed."""
    git_check = subprocess.run("git --version", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if git_check.returncode != 0:
        print("    Git is not installed. Installing Git...")
        if platform.system() == "Windows":
            git_installer_url = "https://github.com/git-for-windows/git/releases/download/v2.42.0.windows.1/Git-2.42.0-64-bit.exe"
            git_installer_path = os.path.join(PROJECT_DIR, "git_installer.exe")
            download_file(git_installer_url, git_installer_path)
            run_command(f"{git_installer_path} /VERYSILENT /NORESTART")
            os.remove(git_installer_path)
            print("        Git installed successfully.")
        else:
            run_command("sudo apt update && sudo apt install -y git")
    else:
        print("    Git is already installed.")

def clone_or_update_repo():
    """Clones or updates the repository."""
    if os.path.exists(PROJECT_DIR):
        print("    Project directory already exists. Installing updates...")
        os.chdir(PROJECT_DIR)
        run_command("git pull", silent=True)
    else:
        print("    Cloning the repository...")
        run_command(f"git clone {REPO_URL} {PROJECT_DIR}", silent=True)

def create_venv():
    """Creates the virtual environment if it doesn't exist."""
    if not os.path.exists(VENV_DIR):
        print("    Creating virtual environment...")
        if platform.system() == "Windows":
            run_command(f"python -m venv {VENV_DIR}", silent=True)
        else:
            run_command(f"python3 -m venv {VENV_DIR}", silent=True)
    else:
        print("    Virtual environment already exists.")

def install_dependencies():
    """Installs required dependencies into the virtual environment."""
    print('    Gathering already installed dependencies...')
    pip_path = (
        os.path.join(VENV_DIR, "Scripts", "pip")  # Windows
        if platform.system() == "Windows"
        else os.path.join(VENV_DIR, "bin", "pip")  # Linux/Mac
    )

    print("     Installing required dependencies...")
    run_command(f"{pip_path} install -r {REQUIREMENTS_FILE}", silent=True)

def ignore_venv():
    """Ensures the venv directory is excluded from Git tracking."""
    gitignore_path = os.path.join(PROJECT_DIR, ".gitignore")
    venv_entry = "venv/\n"

    if os.path.exists(gitignore_path):
        with open(gitignore_path, "r+") as gitignore:
            content = gitignore.readlines()
            if venv_entry not in content:
                gitignore.write(venv_entry)
                print("    Adding /venv entry to .gitignore")
            else:
                print("    Git already ignores /venv")
    else:
        with open(gitignore_path, "w") as gitignore:
            gitignore.write(venv_entry)
        print("    Added /venv entry to .gitignore")

    # Attempt to untrack the venv directory
    result = subprocess.run("git ls-files --error-unmatch venv", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode == 0:
        run_command("git rm -r --cached venv", shell=True, silent=True)

def activate_and_launch():
    """Activates the virtual environment and launches the main program."""
    python_path = (
        os.path.join(VENV_DIR, "Scripts", "python")  # Windows
        if platform.system() == "Windows"
        else os.path.join(VENV_DIR, "bin", "python")  # Linux/Mac
    )

    run_command(f"{python_path} {MAIN_PROGRAM}")

def main():
    """Main launcher logic."""
    # Ensure Git is installed
    print("Checking for Git installation...")
    ensure_git()

    # Clone or update the repository
    print("Checking repository status...")
    clone_or_update_repo()

    # Ensure virtual environment exists
    print("Ensuring virtual environment exists...")
    create_venv()

    # Install required dependencies
    print("Installing dependencies...")
    install_dependencies()

    # Ensure venv is ignored by Git
    print("Configuring Git to ignore the virtual environment...")
    ignore_venv()

    # Activate the environment and run the program
    print("Starting the program...")
    activate_and_launch()

if __name__ == "__main__":
    main()