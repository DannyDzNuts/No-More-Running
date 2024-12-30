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
RESOURCES_DIR = os.path.join('.', 'resources')
REQUIREMENTS_FILE = os.path.join(RESOURCES_DIR, "requirements.txt")
MAIN_PROGRAM = os.path.join(PROJECT_DIR, "no_more_running.pyw")

os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'

# Helper Functions
def run_command(command, shell=True, silent=False):
    """Runs a system command and exits on failure."""
    if silent:
        result = subprocess.run(command, shell=shell, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    else:
        result = subprocess.run(command, shell=shell)

    if result.returncode != 0:
        print(f"    !! Error: Command failed - {command}")
        if silent:
            print(result.stderr.decode())
        sys.exit(1)

def download_file(url, destination):
    """Downloads a file from a URL to a destination."""
    print(f"    + Downloading {url}...")
    with urllib.request.urlopen(url) as response, open(destination, 'wb') as out_file:
        shutil.copyfileobj(response, out_file)

def ensure_git():
    """Ensures Git is installed."""
    git_check = subprocess.run("git --version", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if git_check.returncode != 0:
        print("    + Installing Git...")
        if platform.system() == "Windows":
            git_installer_url = "https://github.com/git-for-windows/git/releases/download/v2.42.0.windows.1/Git-2.42.0-64-bit.exe"
            git_installer_path = os.path.join(PROJECT_DIR, "git_installer.exe")
            download_file(git_installer_url, git_installer_path)
            run_command(f"{git_installer_path} /VERYSILENT /NORESTART")
            os.remove(git_installer_path)
            print("        + Installation Successful")
        else:
            run_command("sudo apt update && sudo apt install -y git")

def clone_or_update_repo():
    """Clones or updates the repository."""
    if os.path.exists(PROJECT_DIR):
        os.chdir(PROJECT_DIR)
        run_command("git pull origin nightly", silent=True)
    else:
        print("    • Downloading NMR")
        run_command(f"git clone {REPO_URL} {PROJECT_DIR}", silent=True)

def create_venv():
    """Creates the virtual environment if it doesn't exist."""
    if not os.path.exists(VENV_DIR):
        print("    • Creating Virtual Environment")
        if platform.system() == "Windows":
            run_command(f"python -m venv {VENV_DIR}", silent=True)
        else:
            run_command(f"python3 -m venv {VENV_DIR}", silent=True)

def install_dependencies():
    """Installs required dependencies into the virtual environment."""
    print('    • Detecting Installed Dependancies')
    pip_path = (
        os.path.join(VENV_DIR, "Scripts", "pip")  # Windows
        if platform.system() == "Windows"
        else os.path.join(VENV_DIR, "bin", "pip")  # Linux/Mac
    )

    print("    • Installing Missing Dependancies")
    run_command(f"{pip_path} install -r {REQUIREMENTS_FILE}", silent=True)

def ignore_venv():
    """Ensures the venv directory is excluded from Git tracking."""
    gitignore_path = os.path.join(PROJECT_DIR, ".gitignore")
    venv_entry = "venv/\n"
    no_update_entry = 'resources/no_update.txt'

    if os.path.exists(gitignore_path):
        with open(gitignore_path, "r+") as gitignore:
            content = gitignore.readlines()
            if venv_entry not in content:
                gitignore.write(venv_entry)
                print("    • Now ignoring /venv")
            
            if gitignore not in content:
                gitignore.write(no_update_entry)
                print('    • Now ignoring no_update.txt')
    else:
        with open(gitignore_path, "w") as gitignore:
            gitignore.write(venv_entry)
            gitignore.write(no_update_entry)
        print("    √ Created .gitignore\n    √ Now ignoring /venv\n    √ Now ignoring no_update.txt")

    # Attempt to untrack the venv directory
    result = subprocess.run("git ls-files --error-unmatch venv", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode == 0:
        run_command("git rm -r --cached venv", shell=True, silent=True)

def detect_ssh():
    """Detects if the script is being run over SSH."""
    return "SSH_CONNECTION" in os.environ or "SSH_CLIENT" in os.environ

def ensure_display():
    """Ensures DISPLAY is set when running in SSH."""
    if detect_ssh():
        if "DISPLAY" not in os.environ:
            print("Activating Remote Display")
            os.environ["DISPLAY"] = ":0"

def activate_and_launch():
    """Activates the virtual environment and launches the main program."""
    ensure_display()  # Ensure DISPLAY is set for SSH sessions

    python_path = (
        os.path.join(VENV_DIR, "Scripts", "python")  # Windows
        if platform.system() == "Windows"
        else os.path.join(VENV_DIR, "bin", "python")  # Linux/Mac
    )

    run_command(f"{python_path} {MAIN_PROGRAM}")

def main():
    """Main launcher logic."""
    # Ensure Git is installed
    print("Verifying Git Installation...")
    ensure_git()

    # Clone or update the repository
    if not os.path.exists(os.path.join(RESOURCES_DIR, './disable_updates.txt')):
        print("Verifying NMR Is Updated...")
        clone_or_update_repo()

    # Ensure virtual environment exists
    print("Verifying Virtual Environment...")
    create_venv()

    # Install required dependencies
    print("Verifying Dependencies...")
    install_dependencies()

    # Ensure venv is ignored by Git
    print("Verifying Git Ignore List...")
    ignore_venv()

    # Activate the environment and run the program
    print("Starting NMR...")
    activate_and_launch()

if __name__ == "__main__":
    main()