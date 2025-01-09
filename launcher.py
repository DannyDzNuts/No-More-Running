import os
import sys
import subprocess
import platform
import urllib.request
import shutil
import ctypes

# Constants
REPO_URL = "https://github.com/DannyDzNuts/No-More-Running.git"
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_DIR = os.path.join(PROJECT_DIR, "venv")
RESOURCES_DIR = os.path.join('.', 'resources')
REQUIREMENTS_FILE = os.path.join(RESOURCES_DIR, "requirements.txt")
MAIN_PROGRAM = os.path.join(PROJECT_DIR, "no_more_running.pyw")

os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'

# Helper Functions
def is_admin():
    """
    Checks if the script is running with administrative privileges.
    Returns True if it is, False otherwise.
    """
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False
        
def relaunch_as_admin():
    """Relaunches the script with administrative privileges."""
    try:
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, " ".join([os.path.abspath(__file__)] + sys.argv[1:]), None, 1
        )
        sys.exit(0)  # Exit the current script after relaunching
    except Exception as e:
        print(f"Failed to relaunch as admin: {e}")
        sys.exit(1)
        
def run_command(command, shell = True, silent = False):
    """Runs a system command and exits on failure."""
    if silent:
        result = subprocess.run(command, shell = shell, stdout = subprocess.PIPE, stderr = subprocess.PIPE)
    else:
        result = subprocess.run(command, shell = shell)

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
    git_check = subprocess.run("git --version", shell = True, stdout = subprocess.PIPE, stderr = subprocess.PIPE)
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
        run_command("git pull origin nightly", silent = True)
    else:
        print("    • Downloading NMR")
        run_command(f"git clone {REPO_URL} {PROJECT_DIR}", silent = True)

def create_venv():
    """Creates the virtual environment if it doesn't exist."""
    if not os.path.exists(VENV_DIR):
        print("    • Creating Virtual Environment")
        if platform.system() == "Windows":
            run_command(f"python -m venv {VENV_DIR}", silent = True)
        else:
            run_command(f"python3 -m venv {VENV_DIR}", silent = True)

def install_dependencies():
    """Installs required dependencies into the virtual environment."""
    def is_mosquitto_in_path():
        """Checks if Mosquitto is in the system's PATH."""
        return shutil.which("mosquitto") is not None

    def add_to_path_windows(directory):
        """Adds a directory to the system PATH on Windows."""
        try:
            current_path = os.environ.get("PATH", "")
            if not directory in current_path:
                import winreg as reg
                key = reg.OpenKey(reg.HKEY_CURRENT_USER, r"Environment", 0, reg.KEY_READ | reg.KEY_WRITE)
                
                try:
                    user_path, _ = reg.QueryValueEx(key, "Path")
                except FileNotFoundError:
                    user_path = ""  # No existing PATH variable for the user
                
                if directory not in user_path:
                    new_path = user_path + ";" + directory if user_path else directory
                    reg.SetValueEx(key, "Path", 0, reg.REG_EXPAND_SZ, new_path)
                else:
                    reg.CloseKey(key)
                    subprocess.run(["setx", "Path", new_path])
            
            relaunch_as_admin()
        except Exception as e:
            print(f"Failed to add {directory} to PATH: {e}")

    def add_to_path_linux(directory):
        """Adds a directory to the system PATH on Linux."""
        path_file = os.path.expanduser("~/.bashrc")
        try:
            with open(path_file, "a") as f:
                f.write(f"\n# Added by script\nexport PATH = {directory}:$PATH\n")
        except Exception as e:
            print(f"Failed to update PATH: {e}")
        
    def _is_broker_installed():
        try:
            result = subprocess.run(
                ["mosquitto", "-h"],
                stdout = subprocess.PIPE,
                stderr = subprocess.PIPE,
                text = True
            )
            return True

        except FileNotFoundError:
            return False
        
    def _download_file(url, save_path):
        try:
            with urllib.request.urlopen(url) as response, open(save_path, "wb") as out_file:
                out_file.write(response.read())
        except Exception as e:
            print(f"    !! Failed To Install Mosquitto: {e}")
        
    def _install_broker():
        service = 'mosquitto'
        sub_service = 'mosquitto-clients'
        plat = platform.system()
        
        if _is_broker_installed():
            if not is_mosquitto_in_path():
                if plat == 'Linux': add_to_path_linux()
                if plat == 'Windows': add_to_path_windows()
            return
        
        if plat == 'Linux':
            try:
                mosquitto_dir = "/usr/sbin"
                subprocess.run(['sudo', 'apt-get', 'update'],
                            check = True,
                            text = True,
                            capture_output = True)
                
                subprocess.run(
                    ['sudo', 'apt-get', '-y', 'install', service, sub_service],
                    check = True,
                    text = True,
                    capture_output = True
                )
                
            except subprocess.CalledProcessError as e:
                print('    !! Mosquitto is missing from your system and failed to install automatically.')

            if not is_mosquitto_in_path():
                add_to_path_linux()
                
        elif plat == 'Windows':
            try:
                mosquitto_dir = r"C:\Program Files\mosquitto"
                installer_url = "https://mosquitto.org/files/binary/win64/mosquitto-2.0.15-install-windows-x64.exe"
                save_path = os.path.join(os.getcwd(), "mosquitto-installer.exe")
                
                _download_file(installer_url, save_path)

                subprocess.run([save_path, "/S"], check = True)  # Silent install
                os.remove(save_path)
                
            except subprocess.CalledProcessError as e:
                print('    !! Mosquitto is missing from your system and failed to install automatically.')
            
            if not is_mosquitto_in_path():
                add_to_path_windows(mosquitto_dir)

    def _install_tkinter():
        """Detects and installs tkinter if missing."""
        try:
            import tkinter
        except ImportError:
            plat = platform.system()
            if plat == "Linux":
                try:
                    subprocess.run(
                        ["sudo", "apt-get", "install", "-y", "python3-tk"],
                        check=True,
                        text=True
                    )
                except subprocess.CalledProcessError as e:
                    print(f"    !! Failed to install tkinter: {e}")
            elif plat == "Windows":
                try:
                    subprocess.run(
                        ["pip", "install", "tkinter"], check = True, text = True)
                except subprocess.CalledProcessError as e:
                    print(f'    !! Error installing tkinter: {e}')

    pip_path = (
        os.path.join(VENV_DIR, "Scripts", "pip")  # Windows
        if platform.system() == "Windows"
        else os.path.join(VENV_DIR, "bin", "pip")  # Linux/Mac
    )

    print("    • Installing Missing Dependancies")
    if not is_mosquitto_in_path():_install_broker()
    run_command(f"{pip_path} install -r {REQUIREMENTS_FILE}", silent = True)
    _install_tkinter()
    
def ignore_files():
    """Ensures the venv directory is excluded from Git tracking."""
    gitignore_path = os.path.join(PROJECT_DIR, ".gitignore")
    ignored = ['venv/', 'resources/no_update.txt', 'resources/log.txt']
    
    if os.path.exists(gitignore_path):
        with open(gitignore_path, "r+") as gitignore:
            content = [line.strip() for line in gitignore.readlines()]
            for item in ignored:
                if item not in content:
                    gitignore.write(f'\n{item}')
                    print(f'    • Now ignoring {item}')
            
    else:
        with open(gitignore_path, "w") as gitignore:
            for item in ignored:
                gitignore.write(f'\n{item}')
                print(f'    • Now ignoring {item}')

        print("    √ Created .gitignore\n    √ Now ignoring /venv\n    √ Now ignoring no_update.txt")

    # Attempt to untrack the venv directory
    result = subprocess.run("git ls-files --error-unmatch venv", shell = True, stdout = subprocess.PIPE, stderr = subprocess.PIPE)
    if result.returncode == 0:
        run_command("git rm -r --cached venv", shell = True, silent = True)

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
    
    # Ensure Launcher Is Running As Admin on Windows
    if os.name == 'nt':
        if not is_admin(): relaunch_as_admin()
    
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
    ignore_files()

    # Activate the environment and run the program
    print("Starting NMR...")
    activate_and_launch()

if __name__ == "__main__":
    main()
