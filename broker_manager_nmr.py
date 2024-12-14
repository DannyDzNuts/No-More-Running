import configparser
import hashlib
import os
import platform
import secrets
import socket
import subprocess
import threading
import time

from colorama import Fore, Back, Style, init
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding

PROG_VER = '0.1_a'
RESOURCES_DIR = os.path.join('.', 'resources')
LOG_FILE = os.path.join(RESOURCES_DIR, 'log.txt')
CONFIG_FILE = os.path.join(RESOURCES_DIR, 'settings.ini')
MULTICAST_GROUP = '224.0.0.1'
MULTICAST_PORT = 50000

local_state = {}
init()

def print_status(type, level, message, new_line = False, custom_fg_color = None):
    _reset = Style.RESET_ALL

    if not level <= 0:
        _indentation = '    ' * level
    else:
        _indentation = ''
    
    if new_line == True:
        _line_break = '\n'
    else:
        _line_break = ''

    if type == 'success':
        _symbol_fg_color = Fore.GREEN
        _symbol_bg_color = Back.BLACK
        _symbol = '[√]'
        _msg_fg = Fore.LIGHTBLACK_EX
    
    if type == 'failure':
        _symbol_fg_color = Fore.RED
        _symbol_bg_color = Back.BLACK
        _symbol = '[x]'
        _msg_fg = Fore.LIGHTBLACK_EX

    if type == 'information':
        _symbol_fg_color = Fore.BLUE
        _symbol_bg_color = Back.BLACK
        _symbol = '[!]'
        _msg_fg = Fore.LIGHTBLACK_EX
    
    if type == 'warn':
        _symbol_fg_color = Fore.YELLOW
        _symbol_bg_color = Back.BLACK
        _symbol = '[!!]'
        _msg_fg = Fore.WHITE

    if type == 'crit': 
        _symbol_fg_color = Fore.BLACK
        _symbol_bg_color = Back.RED
        _symbol = '[!!!]'
        _msg_fg = Fore.WHITE
    
    if not custom_fg_color is None:
        print(f'{_indentation}{_symbol_fg_color}{_symbol_bg_color}{_symbol}{_reset} {custom_fg_color}{message}{_reset}{_line_break}')
    else:
        print(f'{_indentation}{_symbol_fg_color}{_symbol_bg_color}{_symbol}{_reset} {_msg_fg}{message}{_reset}{_line_break}')

def get_error_message(_e, _catagory = 'general'):
    _error_messages = {
        'configuration': {FileNotFoundError: lambda e: f'No config file was detected and one could not be created.\nExpected File Location: {e}',
                        PermissionError: lambda e: f'No config file was detected and NMR does not have permission to write a new one to disk.\n Error: {e}',
                        IOError: lambda e: f'No config file was detected and disk is too busy to write a new one.\nError: {e}',
                        OSError: lambda e: f'No config file was detected and an OS error occured when attempting to create one.\nError: {e}'
                        },

        'mqtt': {TypeError: lambda e: f'Programming error. Attempted to split received message before decoding.\nError: {e}',
                UnicodeDecodeError: lambda e: f'Received message with non-UTF-8 characters.\nError: {e}',
                AttributeError: lambda e: f'Received blank or unexpected message type.\nError: {e}',
                ValueError: lambda e: f'Received message with missing or incorrect delimiter.\nError: {e}'
                },
        
        'psk_encrypt_decrypt': {ValueError: lambda e: f'This error may have occured for several reasons. Please verify the supplied PSKs are of the correct, 32 character hexidecimal format.\nError: {3}',
                                TypeError: lambda e: f'Invalid key type. Supplied key is not in bytes format.\nError: {e}'}
    }
    
    _error_catagory = _error_messages.get(_catagory)
    if _error_catagory: 
        _message_function = _error_messages.get(type(_e))
        if _message_function: return _message_function(_e)
    
    return None

def generate_default_config(parser):
    _default_config = {
    'GUI': {
        'debug': 'False'
    },

    'NETWORK': {
        'broker_qos': '1',
        'broker_port': '1883',
    },
}

    for section, values in _default_config.items():
        parser[section] = values

    return parser

def write_config_to_file(parser = None):
    ''' Writes current program_state '''
    if parser is None:
        parser.read_dict(local_state['config'])

    try:
        with open(CONFIG_FILE, 'w') as file:
            parser.write(file)

    except Exception as e:
        err_message = get_error_message(e, 'config')

        if err_message:
            print_status('crit', 2, err_message)

def get_config():
    ''' Retrieves stored configuration or creates a new config file / loads defaults
        if no config file is found / accessible '''
    global parser
    global process_start_event

    parser = configparser.ConfigParser()
    config = {}

    if not os.path.exists(CONFIG_FILE):
        print_status('information', 3, 'No Configuration File Detected. Generating Default Config File...')
        parser = generate_default_config(parser)
        write_config_to_file(parser)
            
    else:
        try:
            parser = configparser.ConfigParser()
            parser.read(CONFIG_FILE)
        except Exception as e:
            err_message = get_error_message(e, 'config')

            if err_message:
                print_status('crit', 3, f'Unable to read configuration file: {e}')
    
    config = {'debug': parser.get('GUI','debug', fallback = False),
            'broker_port': parser.get('NETWORKING', 'broker_port', fallback = '1883'),
            'broker_qos': parser.get('NETWORKING', 'broker_qos', fallback = '1')
            }
    
    if config: 
        process_start_event.set()
        return config
    
def mDNS_announcements():
    global BROADCAST_IP
    global process_start_event

    def _get_local_ip():
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("192.168.1.1", 1))
                return s.getsockname()[0]
            
        except OSError as e:
            print(f"No network interface detected: {e}")
            return None

    def _broadcast_services():
        global BROADCAST_IP

        BROKER_PORT = local_state['config']['broker_port']
        BROKER_QOS = local_state['config']['broker_qos']
        MESSAGE = F'BROKER_IP | {BROADCAST_IP} | {BROKER_PORT} | {BROKER_QOS}'

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)

        while True:
            sock.sendto(MESSAGE.encode(), (MULTICAST_GROUP, MULTICAST_PORT))
            time.sleep(10)

       
    BROADCAST_IP = _get_local_ip()

    if BROADCAST_IP != '':
        process_start_event.set()
        _broadcast_services()

def initialize_program():
    global local_state
    global process_start_event

    process_start_event = threading.Event()
    mDNS_thread = threading.Thread(target = mDNS_announcements, daemon = False)

    local_state = {'config': ''}

    print_status('information', 0, 'Starting Broker Management Services...', new_line = True, custom_fg_color = Fore.WHITE)

    # Load Program Configuration File / Create If None Exists & Report Status To User
    print_status('information', 1, 'Loading Configuration')
    local_state['config'] = get_config()
    if process_start_event.wait(timeout = 30):
        process_start_event.clear()
        print_status('success', 2, 'Success!', True)
    else:
        print_status('failure', 2, 'Failed!', True)
        exit(0)
    
    # Retrieve Local IP & Start Multicasting It So Clients Can Find Broker
    print_status('information', 1, 'Starting Broker mDNS Service')
    mDNS_thread.start()
    if process_start_event.wait(timeout = 30):
        process_start_event.clear()
        print_status('success', 2, 'Success!', True)
    else:
        print_status('failure', 2, 'Failed!', True)
    
    # Detect Mosquitto Broker & Start It If Not Running
    def _is_mosquitto_alive():
        system = platform.system()

        if system == 'Windows':
            try:
                result = subprocess.run(['sc', 'query', 'mosquitto'], stdout = subprocess.PIPE, text = True)
                output = result.stdout.lower()
                if 'running' in output:
                    return True
            except Exception as e:
                print_status('failure', 2, 'Failed!', True)
                return False
        
        if system == 'Linux':
            try:
                result = subprocess.run(['systemctl', 'is-active', '--quiet', 'mosquitto'],
                                        stdout = subprocess.PIPE, stderr = subprocess.PIPE)
                
                if result.returncode == 0:
                    process_start_event.set()
                    return True
                
                result = subprocess.run(['pgrep', '-x', 'mosquitto'], stdout = subprocess.PIPE)
                if result.returncode == 0:
                    process_start_event.set()
                    return True
                
                else:
                    return False
            
            except Exception as e:
                print_status('failure', 3, f'Failed To Detect Broekr Service: {e}', custom_fg_color = Fore.WHITE)
    
    def _start_mosquitto_lin():
        pass

    def _start_mosquitto_win():
        try:
            result = subprocess.run(["sc", "start", "mosquitto"],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if "START_PENDING" in result.stdout.decode():
                print_status('success', 2, 'Broker Service Is Starting')
                return True
            
            elif "ALREADY_RUNNING" in result.stdout.decode():
                print_status('information', 2, 'Broker Service Is Already Running. Skipping Step.')
                return True
            
            else:
                print_status('failure', 2, 'Failed To Start Broker Service.')
                return False
        
        except Exception as e:
            print_status('failure', 2, f'Failed To Start Broker Service: {e}')
            return False


    def _start_mosquitto():
        system = platform.system()
        
        if system == 'Linux':
            if _start_mosquitto_lin():
                process_start_event.set()

        if system == 'Windows':
            if _start_mosquitto_win():
                process_start_event.set()

    print_status('information', 1, 'Detecting Broker Service Status')

    if _is_mosquitto_alive():
        process_start_event.set()
        print_status('success', 2, 'Success!', True)
    else:
        print_status('failure', 2, 'Failed!', True)

        print_status('information', 1, 'Starting Mosquitto Service')

        if process_start_event.wait(timeout = 30):
            print_status('success', 2, 'Success!', True)
        else:
            print_status('failure', 2, 'Failed!', True)
            exit(0)

if __name__ == "__main__":
    initialize_program()
    