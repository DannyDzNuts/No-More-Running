import os
import sys
import subprocess
import platform
import urllib.request
import shutil

# Constants
REPO_URL = "https://github.com/DannyDzNuts/No-More-Running.git"
PROJECT_DIR = "No-More-Running"

# Helper Functions
def run_command(command, shell=True):
    """Runs a system command and exits on failure."""
    result = subprocess.run(command, shell=shell)
    if result.returncode != 0:
        print(f"Error: Command failed - {command}")
        sys.exit(1)

def download_file(url, destination):
    """Downloads a file from a URL to a destination."""
    print(f"Downloading {url}...")
    with urllib.request.urlopen(url) as response, open(destination, 'wb') as out_file:
        shutil.copyfileobj(response, out_file)

def setup_linux():
    """Sets up the project on Linux."""
    print("Detected Linux OS. Starting installation...")

    # Update and install dependencies
    print("Updating package manager and installing dependencies...")
    run_command("sudo apt update && sudo apt upgrade -y")
    run_command("sudo apt install -y git python3 python3-pip python3-venv")

    # Clone or update repository
    if os.path.exists(PROJECT_DIR):
        print("Project directory already exists. Pulling latest changes...")
        os.chdir(PROJECT_DIR)
        run_command("git pull")
    else:
        print("Cloning the repository...")
        run_command(f"git clone {REPO_URL}")
        os.chdir(PROJECT_DIR)

    # Set up virtual environment
    print("Setting up virtual environment...")
    run_command("python3 -m venv venv")
    run_command("source venv/bin/activate && pip install -r requirements.txt", shell=True)

    print("\nInstallation complete! To run the project, use:")
    print(f"source {os.path.join(PROJECT_DIR, 'venv/bin/activate')} && python3 no_more_running.pyw")

def setup_windows():
    """Sets up the project on Windows."""
    print("Detected Windows OS. Starting installation...")

    # Check if Git is installed; if not, install it silently
    git_check = subprocess.run("git --version", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if git_check.returncode != 0:
        print("Git is not installed. Downloading and installing silently...")
        git_installer_url = "https://github.com/git-for-windows/git/releases/download/v2.42.0.windows.1/Git-2.42.0-64-bit.exe"
        git_installer_path = os.path.join(os.getcwd(), "git_installer.exe")
        download_file(git_installer_url, git_installer_path)
        run_command(f"{git_installer_path} /VERYSILENT /NORESTART")
        os.remove(git_installer_path)
        print("Git installed successfully.")

    # Clone or update repository
    if os.path.exists(PROJECT_DIR):
        print("Project directory already exists. Pulling latest changes...")
        os.chdir(PROJECT_DIR)
        run_command("git pull")
    else:
        print("Cloning the repository...")
        run_command(f"git clone {REPO_URL}")
        os.chdir(PROJECT_DIR)

    # Set up virtual environment
    print("Setting up virtual environment...")
    run_command("python -m venv venv")
    run_command("venv\\Scripts\\activate && pip install -r requirements.txt", shell=True)

    print("\nInstallation complete! To run the project, use:")
    print(f"call {os.path.join(PROJECT_DIR, 'venv\\Scripts\\activate')} && python no_more_running.pyw")

# Main Execution
if __name__ == "__main__":
    detected_os = platform.system()
    if detected_os == "Linux":
        setup_linux()
    elif detected_os == "Windows":
        setup_windows()
    else:
        print(f"Unsupported operating system: {detected_os}")
        sys.exit(1)