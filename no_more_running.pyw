# venv: "C:\Users\DannyDzNuts\Desktop\Development\No More Running v0.1\venv\Scripts\activate.bat"

"""
No More Running
A tkinter-based program for inter-station communication. Designed for use in restaurants, adapted to the world.

Created by Daniel Blake, 2024

Dependencies:
    Standard Libraries:
        - configparser: For reading and managing configuration files.
        - os: To handle file and directory operations.
        - time: For time-related functions.
        - threading: To enable concurrent execution of tasks.
        - hmac, hashlib: For cryptographic operations.
        - secrets: To generate secure tokens and passwords.
        - random: For random number generation.
        - tkinter: To create the graphical user interface (GUI).
        - uuid: For generating unique identifiers.
        - datetime: For working with dates and times.
        - queue: For thread-safe message passing.
        - copy: For deep and shallow copy operations.

    Third-Party Libraries:
        - paho.mqtt.client (v1.6.1): For MQTT messaging.
        - pygame (v2.6.1): For multimedia functionality, including audio playback.
        - Pillow (PIL, v11.0.0): For image processing and manipulation.
        - dateutil.relativedelta (v2.9.0.post0): For advanced date manipulations.
        - cryptography (v44.0.0): For secure encryption and decryption operations.

Usage:
    - Run the program with Python 3.11.x or higher.
    - Ensure the required dependencies are installed (preferably in a virtual environment).
    - Example: `python3 no_more_running.pyw`

Features:
    - Fast, Lightweight Communication
    - Customizability
    - Lightweight Security - Designed to prevent misuse from laypeople (not designed for sensitive data)

License:
    This project is licensed under the GNU General Public License (GPL). You are free to use, modify, and distribute this software, provided that any derivatives are also licensed under the GPL.

    For more details, see the GNU GPL documentation.
"""
import os
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1' 
# Hides the pygame support message (makes console cleaner when debuging).
# I've credited pygame in the README so they're more visible since this program doesn't show a console.

import configparser
import platform
import time
import threading
import hmac
import hashlib
import secrets
import random
import tkinter as tk

from math import radians, sin, cos
from tkinter import Button, Label, Toplevel, PhotoImage, messagebox
from uuid import uuid4
from datetime import datetime
from queue import Queue, Empty

import paho.mqtt.client as mqtt # v1.6.1
import pygame # v2.6.1
from PIL import Image, ImageTk, ImageDraw # v11.0.0
from dateutil.relativedelta import relativedelta # v2.9.0.post0
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes # v44.0.0
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding

PROG_VER = '4.45_nightly'
RESOURCES_DIR = os.path.join('.', 'resources')
IMG_DIR = os.path.join(RESOURCES_DIR, 'images')
LOG_FILE = os.path.join(RESOURCES_DIR, 'log.txt')
CONFIG_FILE = os.path.join(RESOURCES_DIR, 'settings.ini')
ICO_PATH = os.path.join(IMG_DIR, 'logo.ico')

local_state = {} # Client configurtion, temporary global vars, client auth state

lock = threading.Lock()
config_initialized = threading.Event() # Prevents race condition with logic / mqtt threads at start of program

pygame.mixer.init()

class ContentPanel(tk.Frame):
    def __init__(self, parent, mode = 'main', *args, **kwargs):
        super().__init__(parent, *args, **kwargs)

        self.configure(bg = local_state['mc_bg_color'])

        self.num_columns = 4
        self.num_rows = 3
        self.objs_per_page = 12
        self.grid_tracker = [[None for _ in range(self.num_columns)] for _ in range(self.num_rows)]
        self.current_main_page = 1
        self.current_sec_page = 1
        self.mode = mode

        self.main_objs = list(local_state['main_obj_refs']) if mode == 'main' and local_state['main_obj_refs'] else []
        self.sec_objs = list(local_state['sec_obj_refs']) if mode == 'sec' and local_state['sec_obj_refs'] else []
        
        if mode == 'main':
            self.total_main_pages = max((len(self.main_objs) + self.objs_per_page - 1) // self.objs_per_page, 1)
        elif mode == 'sec':
            self.total_sec_pages = max((len(self.sec_objs) + self.objs_per_page - 1) // self.objs_per_page, 1)

        if self.main_objs and self.mode == 'main':
            self.populate_grid(self.current_main_page, self.mode)
        elif self.sec_objs and self.mode == 'sec':
            self.populate_grid(self.current_sec_page, self.mode)

        self.grid_columnconfigure(0, weight = 1)
        self.grid_columnconfigure(1, weight = 1)
        self.grid_columnconfigure(2, weight = 1)
        self.grid_columnconfigure(3, weight = 1)

        self.grid_rowconfigure(0, weight = 1)
        self.grid_rowconfigure(1, weight = 1)
        self.grid_rowconfigure(2, weight = 1)
        self.grid_rowconfigure(3, weight = 1)


        self.nav_bar = tk.Canvas(self, 
                                      width = 300, 
                                      height = 75, 
                                      bg = local_state['side_bg_color'],
                                      highlightthickness = 0)
        
        _prefix = (f"{local_state['icons']}_")

        try:
            _img_left_arrow_path = os.path.join(IMG_DIR, f'{_prefix}arrow_left.png')
            _img_right_arrow_path = os.path.join(IMG_DIR, f'{_prefix}arrow_right.png')
            _img_first_page_path = os.path.join(IMG_DIR, f'{_prefix}first_page.png')
            _img_last_page_path = os.path.join(IMG_DIR, f'{_prefix}last_page.png')
            _img_left_arrow = Image.open(_img_left_arrow_path).resize((56, 56))
            _img_right_arrow = Image.open(_img_right_arrow_path).resize((56, 56))
            _img_first_page = Image.open(_img_first_page_path).resize((38, 38))
            _img_last_page = Image.open(_img_last_page_path).resize((38, 38))

        except Exception as e:
            # Creates an image placeholder if image above cannot be loaded.
            _placeholder = Image.new('RGBA', (38, 28), (200, 200, 200, 255))
            _draw = ImageDraw.Draw(_placeholder)
            _draw.line((0, 0, 38, 38), fill = 'red', width = 2)
            _draw.line((0, 38, 38, 0), fill = 'red', width = 2)
            _img_left_arrow = _placeholder
            _img_right_arrow = _placeholder
            _img_first_page = _placeholder
            _img_last_page = _placeholder

        self.img_left_arrow = ImageTk.PhotoImage(_img_left_arrow)
        self.img_right_arrow = ImageTk.PhotoImage(_img_right_arrow)
        self.img_first_page = ImageTk.PhotoImage(_img_first_page)
        self.img_last_page = ImageTk.PhotoImage(_img_last_page)

        self.cont_img_left_arrow = Label(self.nav_bar, 
                                         image = self.img_left_arrow, 
                                         bg = local_state['side_bg_color'], 
                                         )
        
        self.cont_img_right_arrow = Label(self.nav_bar, 
                                          image = self.img_right_arrow, 
                                          bg = local_state['side_bg_color'], 
                                          )
        
        self.cont_img_first_page = Label(self.nav_bar, 
                                         image = self.img_first_page, 
                                         bg = local_state['side_bg_color'], 
                                         )
        
        self.cont_img_last_page = Label(self.nav_bar, 
                                        image = self.img_last_page, 
                                        bg = local_state['side_bg_color'], 
                                        )

        self.cont_img_left_arrow.bind("<Button-1>", lambda e: self.go_to_previous_page(self.mode))
        self.cont_img_right_arrow.bind("<Button-1>", lambda e: self.go_to_next_page(self.mode))
        self.cont_img_first_page.bind("<Button-1>", lambda e: self.go_to_first_page(self.mode))
        self.cont_img_last_page.bind("<Button-1>", lambda e: self.go_to_last_page(self.mode))

        self.nav_bar.place(relx = 0.84, rely = 0.93)
        self.cont_img_first_page.place(relx = 0.05, rely = 0.2)
        self.cont_img_left_arrow.place(relx = 0.28, rely = 0.1)
        self.cont_img_right_arrow.place(relx = 0.52, rely = 0.1)
        self.cont_img_last_page.place(relx = 0.8, rely = 0.21)

    def add_object(self, obj, mode):
        if mode == 'main':
            self.main_objs.append(obj)
            self.total_main_pages = max((len(self.main_objs) + self.objs_per_page - 1) // self.objs_per_page, 1)
        else:
            self.sec_objs.append(obj)
            self.total_sec_pages = max((len(self.sec_objs) + self.objs_per_page - 1) // self.objs_per_page, 1)

        self.populate_grid(self.current_main_page, mode)

    def get_page(self, page_number, mode):
        items = self.main_objs if mode == 'main' else self.sec_objs

        start_index = (page_number - 1) * self.objs_per_page
        end_index = start_index + self.objs_per_page
        return items[start_index:end_index]


    def clear_grid(self):
        """Remove objects from the grid without destroying them."""
        for row in range(self.num_rows):
            for col in range(self.num_columns):
                if self.grid_tracker[row][col] is not None:
                    self.grid_tracker[row][col].grid_forget()  # Hide the widget
                    self.grid_tracker[row][col] = None


    def populate_grid(self, page_number, mode):
        self.clear_grid()  # Clear the current grid

        items = self.get_page(page_number, mode)

        if not items:  # If no items exist, just return without doing anything
            return

        for obj in items:
            row, column = self._find_next_cell(self.grid_tracker)
            if row is not None and column is not None:
                obj.grid(row=row, column=column)
                self.grid_tracker[row][column] = obj

    @property
    def total_pages(self):
        objs = self.main_objs if self.mode == 'main' else self.sec_objs
        total = max((len(objs) + self.objs_per_page - 1) // self.objs_per_page, 1)
        return total


    def go_to_next_page(self, event=None):
        if self.mode == 'main' and self.current_main_page < self.total_pages:
            self.current_main_page += 1
            self.populate_grid(self.current_main_page, self.mode)
        elif self.mode == 'sec' and self.current_sec_page < self.total_pages:
            self.current_sec_page += 1
            self.populate_grid(self.current_sec_page, self.mode)


    def go_to_previous_page(self, event = None):
        if self.mode == 'main' and self.current_main_page > 1:
            self.current_main_page -= 1
            self.populate_grid(self.current_main_page, self.mode)
        elif self.mode == 'sec' and self.current_sec_page > 1:
            self.current_sec_page -= 1
            self.populate_grid(self.current_sec_page, self.mode)

    def go_to_first_page(self, event = None):
        if self.mode == 'main' and self.current_main_page != 1:
            self.current_main_page = 1
            self.populate_grid(self.current_main_page, self.mode)
        elif self.mode == 'sec' and self.current_sec_page != 1:
            self.current_sec_page = 1
            self.populate_grid(self.current_sec_page, self.mode)

    def go_to_last_page(self, event = None):
        if self.mode == 'main' and self.current_main_page != self.total_pages:
            self.current_main_page = self.total_pages
            self.populate_grid(self.current_main_page, self.mode)
        elif self.mode == 'sec' and self.current_sec_page != self.total_pages:
            self.current_sec_page = self.total_pages
            self.populate_grid(self.current_sec_page, self.mode)

    def _page_active(self, event = None):
        if local_state.get('active_obj_id') not in (None, ''):
            _active_obj_id = str(local_state.get('active_obj_id'))
            
            if _active_obj_id in local_state['main_obj_refs']:
                _active_obj = local_state['main_obj_refs'][_active_obj_id]
            else:
                _active_obj = local_state['sec_obj_refs'][_active_obj_id]
            
            _active_obj.page()
    def _trigger_gen_mainobj(self):
        temp_thread = threading.Thread(target = self._debug_gen_mainobjs(), daemon = True)
        temp_thread.start()
        temp_thread.join()

    def _debug_gen_mainobjs(self, number_to_generate=1):
        """Generate and add sample objects to the panel for debugging purposes."""

        def _generate_phone_number():
            while True:
                area_code = random.randint(200, 999)
                if area_code % 100 != 11:
                    break

            central_office_code = random.randint(200, 999)
            station_number = random.randint(1000, 9999)

            return f"+1-{area_code}-{central_office_code}-{station_number}"

        for _ in range(number_to_generate):
            _title = f"#{random.randint(1000, 9999)}"
            _subtitle_val = _generate_phone_number()
            _flag_a = random.choice([True, False])
            _flag_b = random.choice([True, False])

            # Create a new MainObject instance
            main_obj = ContentObject(
                self,
                mode='main',
                title_val=_title,
                width=int(self.winfo_width() / 5),
                height=int(self.winfo_height() / 4),
                enable_timer=True,
                subtitle_val=_subtitle_val,
                flag_a_val=_flag_a,
                flag_b_val=_flag_b,
            )

            self.main_objs.append(main_obj)

            # Find the next available cell
            cell = self._find_next_cell(self.grid_tracker)
            if cell is not None:
                row, column = cell
                self.after(10, main_obj.grid(row=row, column=column))
                self.grid_tracker[row][column] = main_obj

    def _find_next_cell(self, grid_tracker):
        for row in range(len(grid_tracker)):
            for column in range(len(grid_tracker[row])):
                if grid_tracker[row][column] is None:
                    return row, column
        return None
    
    def instantiate_main_obj(self):
        number_to_generate = 5
        for _ in range(number_to_generate):
            _title = f"#{random.randint(1000, 9999)}"
            _flag_a = random.choice([True, False])
            _flag_b = random.choice([True, False])

        # Create a new MainObject instance
        sec_obj = ContentObject(
            self,
            mode = 'sec',
            title_val = _title,
            flag_a_val = _flag_a,
            flag_b_val = _flag_b,
        )

        sec_obj.pack(fill='x', padx=0, pady=1)

    def _debug_gen_secobjs(self):
        """Generate and add sample objects to the panel for debugging purposes."""
        object_creation_thread = threading.Thread(target = self.instatiate_main_obj, daemon = True)
        object_creation_thread.start()
        object_creation_thread.join()

class ContentObject(tk.Canvas):
    def __init__(self, parent, mode, title_val, width, height, enable_timer = False, subtitle_val = None, flag_a_val = False, flag_b_val = False):
        super().__init__(parent, bd = 0, relief = 'flat')
        if not mode in ('main', 'sec'): return
        global local_state

        # Colors (bd = Border)
        self.inactive_bg = self._brighten_color(local_state['mc_bg_color'], brighten_by = 10)
        self.active_bg = local_state['accent_bg_color']
        self.fg_color = local_state['mc_fg_color']
        self.inactive_bd = self._brighten_color(self.inactive_bg, brighten_by = 10)
        self.active_bd = self._brighten_color(self.inactive_bd, 30)

        self.is_selected = False
        self.unique_id = uuid4()
        self.corner_radius = 23
        self.width = width
        self.height = height

        if local_state['accent_bg_color'] != '':
            self.accent_bg_color = local_state['accent_bg_color']
        else:
            self.accent_bg_color = '#F0F0F0'

        if local_state['accent_fg_color'] != '':
            self.accent_fg_color = local_state['accent_fg_color']
        else:
            self.accent_fg_color = '#0F0F0F'
            
        self.configure(height = self.height, 
                        width = self.width,
                        bd = 0, 
                        highlightthickness = 3,
                        highlightbackground = self.inactive_bd,
                        bg = self.inactive_bg
        )

        self.bind("<Button-1>", self._set_selected)

        if mode == 'main':
            self.ref_dict = 'main_obj_refs'
            self.enable_masking = local_state['config']['main_enable_masking']
            self.enable_timer = local_state['config']['main_enable_timer']
        else:
            self.ref_dict = 'sec_obj_refs'
            self.enable_masking = local_state['config']['sec_enable_masking']
            self.enable_timer = local_state['config']['sec_enable_timer']
        
        if not subtitle_val is None:
            self.subtitle_enabled = True
            self.unmasked_subtitle_val = subtitle_val
            self.masked_subtitle_val = ''
            self.is_masked = False
        else:
            self.subtitle_enabled = False

        if isinstance(self.enable_masking, str): # Python interprets bools weird, let's make sure we get the right value...
            self.enable_masking = self.enable_masking.lower() in ('true', '1', 'yes', 'y')
        
        self.enable_masking = bool(self.enable_masking)

        if self.enable_masking:
            self.is_masked = True
            self.masked_subtitle_val = '*' * (len(self.unmasked_subtitle_val) - 4) + self.unmasked_subtitle_val[-4:]
            _init_subtitle_val = self.masked_subtitle_val
        else:
            _init_subtitle_val = self.unmasked_subtitle_val

        _prefix = local_state['icons']

        self.img_flag_a = local_state['images'][f'{_prefix}_main_flag_a']
        self.img_flag_b = local_state['images'][f'{_prefix}_main_flag_b']

        self.lbl_title = tk.Label(self,
                                    text = title_val,
                                    bg = self.inactive_bg,
                                    fg = self.fg_color,
                                    font = ('Arial', 34, 'bold'),
                                    anchor = 'w')

        self.lbl_title.place(relx = 0.5, rely = 0.15, anchor = 'center')
        self.lbl_title.bind("<Button-1>", self._set_selected)
        
        if self.subtitle_enabled:
            self.lbl_subtitle = tk.Label(self,
                                            text = _init_subtitle_val,
                                            bg = self.inactive_bg,
                                            fg = self.fg_color,
                                            font = ('Arial', 14),
                                            anchor = 'w')

            self.lbl_subtitle.place(relx = 0.5, rely = 0.3, anchor = 'center')
            self.lbl_subtitle.bind("<Button-1>", self._set_selected)

        if isinstance(self.enable_timer, str):
            self.enable_timer = self.enable_timer.lower() in ('true', '1', 'yes', 'y')
        
        if self.enable_timer:
            self.creation_time = time.time()
            self.lbl_timer = tk.Label(self,
                                        text = '00:00:00',
                                        font = ('Ariel', 20, 'bold'),
                                        bg = self.inactive_bg,
                                        fg = self.fg_color)

            self.lbl_timer.place(relx = 0.5, rely = 0.5, anchor = 'center')
            self.lbl_timer.bind("<Button-1>", self._set_selected)
        

        if mode == 'main' and local_state['config']['main_flags_enabled']:
            _flag_a_name = local_state['config']['main_obj_flag_a_name']
            _flag_b_name = local_state['config']['main_obj_flag_b_name']


        elif mode == 'sec' and local_state['config']['sec_flags_enabled']:
            _flag_a_name = local_state['config']['sec_obj_flag_a_name']
            _flag_b_name = local_state['config']['sec_obj_flag_b_name']
            
        _mode_flags_map = {
            'main': local_state['config']['main_flags_enabled'],
            'sec': local_state['config']['sec_flags_enabled']
        }

        if _mode_flags_map[mode]:
            self.lbl_flag_a = tk.Label(self,
                                        text = _flag_a_name,
                                        font = ('Arial', 16),
                                        bg = self.inactive_bg,
                                        fg = self.fg_color)
            
            self.cont_flag_a = tk.Label(self,
                                        image = self.img_flag_a,
                                        bg = self.inactive_bg)
            
            self.lbl_flag_b = tk.Label(self,
                                        text = _flag_b_name,
                                        font = ('Arial', 16),
                                        bg = self.inactive_bg,
                                        fg = self.fg_color)
            
            self.cont_flag_b = tk.Label(self,
                                            image = self.img_flag_b,
                                            bg = self.inactive_bg)
            
            if flag_a_val:
                self.lbl_flag_a.place(relx = 0.3, rely = 0.7, anchor = 'center')
                self.cont_flag_a.place(relx = 0.3, rely = 0.85, anchor = 'center')
                self.lbl_flag_a.bind('<Button-1>', self._set_selected)
                self.cont_flag_a.bind('<Button-1>', self._set_selected)

            if flag_b_val:
                self.lbl_flag_b.place(relx = 0.7, rely = 0.7, anchor = 'center')
                self.cont_flag_b.place(relx = 0.7, rely = 0.85, anchor = 'center')
                self.lbl_flag_b.bind('<Button-1>', self._set_selected)
                self.cont_flag_b.bind('<Button-1>', self._set_selected)

        update_local_state(self.ref_dict, {f'{self.unique_id}': self})
        self.update_idletasks()
    
    def _brighten_color(self, hex_color, brighten_by=10):
        hex_color = hex_color.lstrip("#")

        if len(hex_color) != 6:
            raise ValueError("Invalid hex color code. Must be 6 characters long.")

        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)

        brightness = 0.299 * r + 0.587 * g + 0.114 * b
        max_brightness = 0.299 * 240 + 0.587 * 240 + 0.114 * 240

        if brightness >= max_brightness:
            return f"#{r:02X}{g:02X}{b:02X}"

        r = min(r + brighten_by, 255)
        g = min(g + brighten_by, 255)
        b = min(b + brighten_by, 255)

        brightened_color = f"#{r:02X}{g:02X}{b:02X}"
        return brightened_color

    def _set_selected(self, _is_selected):
        """Change the appearance of the widget to indicate selection."""

        _other_object_active = local_state['is_object_active']

        if not self.is_selected and _other_object_active == True:
            _active_obj_id = str(local_state.get('active_obj_id'))
            _active_obj = local_state[self.ref_dict][_active_obj_id]
            _active_obj.deselect()
        
        _other_object_active = local_state['is_object_active'] # Double checking to ensure something else wasn't selected before we reached this line

        if not self.is_selected and not _other_object_active:
            self.configure(highlightbackground = self.active_bd, bg = self.active_bg)

            if hasattr(self, 'lbl_flag_a'):
                self.cont_flag_a.configure(bg = self.accent_bg_color)
                self.lbl_flag_a.configure(bg = self.accent_bg_color, fg = self.accent_fg_color)

            if hasattr(self, 'lbl_flag_b'):
                self.cont_flag_b.configure(bg = self.accent_bg_color)
                self.lbl_flag_b.configure(bg = self.accent_bg_color, fg = self.accent_fg_color)
            
            self.lbl_title.configure(fg = self.accent_fg_color, bg = self.accent_bg_color)
            if hasattr(self, 'lbl_subtitle'): self.lbl_subtitle.configure(fg = self.accent_fg_color, bg = self.accent_bg_color)
            if hasattr(self, 'lbl_timer'): self.lbl_timer.configure(fg = self.accent_fg_color, bg = self.accent_bg_color)

            if self.enable_masking:
                self.lbl_subtitle.configure(text = self.unmasked_subtitle_val)

            self.is_selected = True
            update_local_state('is_object_active', True)
            update_local_state('active_obj_id', self.unique_id)

        elif self.is_selected:
            self.deselect()

    def deselect(self):
        self.configure(bg = self.inactive_bg, highlightbackground = self.inactive_bd)
        self.lbl_title.configure(bg = self.inactive_bg)

        if hasattr(self, 'cont_flag_a'):
            self.cont_flag_a.configure(bg = self.inactive_bg)
            self.lbl_flag_a.configure(bg = self.inactive_bg)
            self.lbl_flag_a.configure(fg = self.fg_color)

        if hasattr(self, 'cont_flag_b'):
            self.cont_flag_b.configure(bg = self.inactive_bg)
            self.lbl_flag_b.configure(bg = self.inactive_bg)
            self.lbl_flag_b.configure(fg = self.fg_color)
        
        self.lbl_title.configure(fg = self.fg_color)
        
        if hasattr(self, 'lbl_subtitle'): 
            self.lbl_subtitle.configure(fg = self.fg_color)
            self.lbl_subtitle.configure(bg = self.inactive_bg)
        
        if hasattr(self, 'lbl_timer'): 
            self.lbl_timer.configure(fg = self.fg_color)
            self.lbl_timer.configure(bg = self.inactive_bg)

        if self.enable_masking is True:
            self.lbl_subtitle.configure(text = self.masked_subtitle_val)

        self.is_selected = False

        update_local_state('is_object_active', False)
        update_local_state('active_obj_id', None)

class SettingsContent(tk.Frame):
    def __init__(self, parent, mode):
        super().__init__(parent, bd = 1, relief = 'raised')
        
        _sub_font = ('Arial', 18)
        _section_font = ('Arial', 24, 'bold')
        
        self.bg_color = local_state['mc_bg_color']
        self.fg_color = local_state['mc_fg_color']
        
        labels = [
            ('lbl_section_GUI', 'INTERFACE', _section_font),
            ('lbl_section_CLIENT', 'ADVANCED', _section_font),
            ('lbl_client_name', 'Client Name:', _sub_font),
            ('lbl_client_id', 'Client ID:', _sub_font),
            ('lbl_client_password', 'Client Password:', _sub_font),
            ('lbl_client_audience', 'Client Group:', _sub_font),
            ('lbl_client_position', 'Client Sub Group:', _sub_font),
            ('lbl_broker_ip', 'Broker IP:', _sub_font),
            ('lbl_broker_port', 'Broker Port:', _sub_font),
            ('lbl_primary_psk', 'Primary PSK:', _sub_font),
            ('lbl_primary_psk_exp', 'Primary PSK Exp:', _sub_font),
            ('lbl_primary_psk_exp_val', '', _sub_font),
            ('lbl_backup_psk', 'Backup PSK:', _sub_font),
        ]

        for var_name, text, font in labels:
            setattr(self, var_name, tk.Label(text=text, font=font))

        
        mapping = {
            'client_name': 'val_client_name',
            'client_id': 'val_client_id',
            'client_audience': 'val_client_audience',
            'client_position': 'val_client_position',
            'main_object_name': 'val_main_obj_name',
            'main_obj_subtitle': 'val_main_obj_subtitle',
            'main_flags_enabled': 'val_main_flags_enabled',
            'main_obj_flag_a_name': 'val_main_obj_flag_a_name',
            'main_obj_flag_b_name': 'val_main_obj_flag_b_name',
            'secondary_object_name': 'val_secondary_obj_name',
            'secondary_flag_a_name': 'val_sec_flag_a_name',
            'secondary_flag_b_name': 'val_sec_flag_b_name',
            'secondary_flags_enabled': 'val_sec_flags_enabled',
            'enable_masking': 'enable_masking',
            'enable_debug': 'enable_debug'
        }

        for key, attr in mapping.items():
            setattr(self, attr, local_state['config'][key])
        
        self.lbl_section_GUI.place(rex = 0.05, rely = 0.05)

class SideBarButtons(tk.Frame):
    def __init__(self, parent, text, bg_color, width, height = 1, command=None, *args, **kwargs):
        super().__init__(parent, text=text, width=width, height=height, command=command, bg=bg_color, *args, **kwargs)
        
class SideBar(tk.Frame):
    def __init__(self, parent, main_content_panel, min_width=50, max_width=200):
        super().__init__(parent, width=min_width, bg=local_state['side_bg_color'], relief='groove')
        self.pack_propagate(True)

        self.min_width = min_width
        self.max_width = max_width
        self.current_width = min_width
        self.is_minimized = True
        self.bg_color = local_state['side_bg_color']
        self.fg_color = local_state['side_fg_color']
        self.main_content_panel = main_content_panel

        main_obj_name = local_state['config']['main_object_name']
        sec_obj_name = local_state['config']['sec_object_name']

        # Load and resize an image using Pillow for the logo
        _prefix = f"{local_state['icons']}_"
        try:
            raw_img = Image.open(os.path.join(IMG_DIR, f'{_prefix}logo.png'))
            ready_img = raw_img.resize((int(min_width - 25), int(min_width - 30)))
            self.image = ImageTk.PhotoImage(ready_img)
        except FileNotFoundError:
            self.image = tk.PhotoImage(width=min_width, height=60)

        # Create a label to hold the logo and text
        self.image_container = tk.Label(
            self, 
            image = self.image, 
            bg = self.bg_color, 
            text = 'NMR', 
            compound = 'left', 
            font = ('Ariel', 34), 
            fg = self.fg_color
        )

        # Create a spacer frame
        self.spacer = tk.Frame(self, width = 50, height = 1, bg = self.bg_color)

        _prefix = f"{local_state['icons']}_"

        # Create buttons (with icons and labels for extended mode)
        self.buttons = {
            'minimize': self._create_sidebar_button('Minimize', f'{_prefix}menu.png', command=self._toggle),
            f'show_{main_obj_name.capitalize()}_list': self._create_sidebar_button(f'Active {main_obj_name}s', f'{_prefix}show_main_objs.png', command = self._show_main_panel),
            f'show_{sec_obj_name.capitalize()}_list': self._create_sidebar_button(f'{sec_obj_name} List', f'{_prefix}show_sec_objs.png', command=self._show_sec_panel),
            'create': self._create_sidebar_button('Create', f'{_prefix}create.png', command=self._create_object),
            'modify': self._create_sidebar_button('Modify', f'{_prefix}edit.png', command=self._edit_object),
            'page': self._create_sidebar_button('Page', f'{_prefix}page.png', command=self._debug_page_object),
            'remove': self._create_sidebar_button('Remove', f'{_prefix}delete.png', command=self._delete_object),
            'exit': self._create_sidebar_button('Exit', f'{_prefix}exit.png', command=self._exit_program),
            'settings': self._create_sidebar_button('Settings', f'{_prefix}settings.png', command=self._show_set_panel),
            'generate_objects': self._create_sidebar_button('Generate Objs', f'{_prefix}generate.png', command=self.main_content_panel._trigger_gen_mainobj),
        }

        # Pack the logo and spacer
        self.image_container.pack(pady=10)
        self.spacer.pack(pady=5)
        self._pack_sidebar_buttons()

        # Start minimized
        self._minimize()

    def _create_sidebar_button(self, text, icon_filename, command=None):
        """Factory function to create buttons with icons and labels."""
        try:
            icon_path = os.path.join(IMG_DIR, icon_filename)
            icon_image = Image.open(icon_path).resize((42, 42))
            icon = ImageTk.PhotoImage(icon_image)
        except FileNotFoundError:
            icon = tk.PhotoImage(width = 42, height = 42)

        if local_state['config']['theme'] == 'super_dark':
            _fg_color = local_state['mc_bg_color']
        else:
            _fg_color = local_state['side_fg_color']

        button = tk.Button(
            self,
            text = text,
            font = ("Arial", 16),
            image = icon,
            compound = 'left',
            padx = 5,
            pady = 5,
            width = int(self.winfo_width()- 5),
            command=command,
            bg = self.bg_color,
            fg = _fg_color,
            borderwidth = 0,
            relief = 'flat',
            activebackground = self.bg_color
        )

        button.icon = icon
        return button

    def _pack_sidebar_buttons(self):
        """Pack all buttons with their current state (minimized or maximized)."""
        _btn_show_mainobj_name = f'show_{local_state["config"]["main_object_name"].capitalize()}_list'
        spacer_items = [_btn_show_mainobj_name, 'create']

        for key, btn in self.buttons.items():
            if key in spacer_items:
                if local_state['screen_height'] <= 1000:
                    btn.pack(pady = (30, 8), anchor = 'center')
                else:
                    btn.pack(pady = (40, 8), anchor='center')

            elif key in ['settings', 'exit']:
                btn.pack(pady = (8, 8), side = 'bottom', anchor = 'center')

            elif key in ['generate_objects', 'page_active']:
                if local_state['config']['enable_debug']:
                    btn.pack(pady = (8, 8), side = 'bottom', anchor = 'center')
                else:
                    pass
            else:
                btn.pack(pady = (8, 8), anchor='center')

    def _minimize(self):
        self.configure(width = self.current_width)
        self.is_minimized = True

        self.image_container.config(text='')

        # Update Sidebar Buttons To Display Icons Only
        for btn in self.buttons.values():
            btn.config(compound = 'top', text = '')
            btn.pack_configure(anchor = 'center')

    def _maximize(self):
        """Maximize the sidebar (show icons with labels)."""
        self.configure(width = self.max_width)
        self.is_minimized = False

        self.image_container.config(text='NMR')
        # Update Sidebar Buttons To Show Icons + Text
        for key, btn in self.buttons.items():
            _label_text = key.replace('_', ' ').title()
            btn.config(compound = 'left', text = _label_text)
            btn.pack_configure(anchor='w')

    def _toggle(self):
        """Toggle between minimized and maximized states."""
        if self.is_minimized:
            self._maximize()
        else:
            self._minimize()

    def _generate_objects(self):
        """Call the generate_debug_objectss method of the MainContentPanel."""
        if self.main_content_panel:
            self.main_content_panel.generate_debug_objects()

    def _show_main_panel(self):
        """Switch to the main content panel."""
        _main_panel = local_state['mc_panel_ref']
        _active_panel = local_state['active_panel_ref']

        _active_panel.grid_remove()

        update_local_state('active_panel_ref', _main_panel)

        _main_panel.grid()
        _main_panel.lift()

    def _show_sec_panel(self):
        """Switch to the sec content panel."""
        _active_panel = local_state['active_panel_ref']
        _sec_panel = local_state['sec_panel_ref']

        _active_panel.grid_remove()

        update_local_state('active_panel_ref', _sec_panel)

        _sec_panel.grid()
        _sec_panel.lift()
    
    def _show_set_panel(self):
        _set_panel = local_state['set_panel_ref']
        _active_panel = local_state['active_panel_ref']

        _active_panel.grid_remove()

        update_local_state('active_panel_ref', _set_panel)

        _set_panel.grid()
        _set_panel.lift()

    def _create_object(self):
        pass

    def _edit_object(self):
        pass

    def _debug_page_object(self):
        # Get the root window from the parent
        root = self.winfo_toplevel()
        _requestor = 'Debug'
        _active_obj_id = local_state['active_obj_id']
        _active_obj_id = str(_active_obj_id)

        if _active_obj_id in local_state['main_obj_refs']:
            _obj = local_state['main_obj_refs'][_active_obj_id]
        elif _active_obj_id in local_state['sec_obj_refs']:
            _obj = local_state['sec_obj_refs'][_active_obj_id]
        else:
            return   

        # Create a semi-transparent full-screen overlay
        overlay = tk.Frame(root, bg = _obj.inactive_bg)
        overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        overlay.tkraise()  # Ensure the overlay is above all other widgets

        # Add object details
        obj_name = _obj.lbl_title.cget("text")
        obj_reference_name = local_state["config"]["main_object_name"]

        # Add a label to display the message
        message_label = tk.Label(
            overlay,
            text=f"Page received from {_requestor}\n\n{obj_reference_name}: {obj_name}",
            font=("Arial", 48),
            bg = _obj.inactive_bg,
            fg = _obj.fg_color,
        )
        
        message_label.place(relx=0.5, rely=0.4, anchor="center")

        # Event for sound playback control
        sound_event = threading.Event()

        # Dismiss button functionality
        def dismiss():
            sound_event.set()
            overlay.destroy()

        # Add a dismiss button
        dismiss_button = tk.Button(
            overlay,
            text="Dismiss",
            bg="#333333",
            fg="#FFFFFF",
            font=("Arial", 36),
            command=dismiss,
        )

        dismiss_button.place(relx=0.5, rely=0.65, anchor="center")

        # Function to play notification sound
        def play_sound():
            sound_path = os.path.join(RESOURCES_DIR, "notify.wav")
            if os.path.exists(sound_path):
                iteration = 0
                while not sound_event.is_set():
                    if iteration >= 3:  # Play sound up to 3 times
                        break
                    try:
                        sound = pygame.mixer.Sound(sound_path)
                        sound.play()
                        time.sleep(sound.get_length())
                        time.sleep(10)  # Delay between plays
                    except Exception as e:
                        break
                    iteration += 1

        # Start the sound thread
        sound_thread = threading.Thread(target=play_sound, daemon=True)
        sound_thread.start()

    def _delete_object(self):
        pass

    def _exit_program(self):
        exit(0)

class StatusPanel(tk.Frame):
    def __init__(self, parent, height, width, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)

        self.pack_propagate(False)
        self.configure(bg = local_state['side_bg_color'], height = height, width = width)
        
        if local_state['config']['theme'] == 'super_dark':
            _fg_color = local_state['mc_bg_color']
        else:
            _fg_color = local_state['side_fg_color']
        
        _bg_color = local_state['side_bg_color']

        _lbl_connection_title = Label(self, text = 'Connection Status:', 
                                    font = ('Arial', 28), 
                                    fg = _fg_color, 
                                    bg = _bg_color)
        
        self.lbl_connection_state = Label(self, text = 'Not Connected',
                                    font = ('Arial', 28),
                                    fg = _fg_color,
                                    bg = _bg_color)
        
        _frm_spacer = tk.Frame(self,
                               width = int(width / 4), 
                               bg = _bg_color)

        _client_info_text = (f"{local_state['config']['client_name']} @ {local_state['config']['client_position']}")
        self.lbl_client_info = tk.Label(self, text = _client_info_text,
                                     font = ('Arial', 28),
                                     fg = _fg_color,
                                     bg = _bg_color)
        
        self.grid_columnconfigure(0, weight = 0)
        self.grid_columnconfigure(1, weight = 1)
        self.grid_columnconfigure(2, weight = 1)
        self.grid_columnconfigure(3, weight = 1)

        _lbl_connection_title.grid(row = 0, column = 0, sticky = 'ne')
        self.lbl_connection_state.grid(row = 0, column = 1, sticky = 'nw')
        _frm_spacer.grid(row = 0, column = 2)
        self.lbl_client_info.grid(row = 0, column = 3, sticky = 'ne')

def get_timestamp(include_month = False):
    if include_month:
        return time.strftime('%m/%d/%y @ %H:%M:%S')
    else:
        return time.strftime('%H:%M:%S')
    
def get_error_message(err, catagory = 'general'):
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

        'to_logic_thread_queue': {ValueError: lambda e: f'Data returned from queue is not tuple.\nError: {e}',
                                Empty: lambda e: f'Queue is empty and empty queue errors are not ignored.\nError: {e}'
                                },
        
        'psk_encrypt_decrypt': {ValueError: lambda e: f'This error may have occured for several reasons. Please verify the supplied PSKs are of the correct, 32 character hexidecimal format.\nError: {3}',
                                TypeError: lambda e: f'Invalid key type. Supplied key is not in bytes format.\nError: {e}'}
    }
    
    _error_catagory = _error_messages.get(catagory)
    if _error_catagory: 
        _message_function = _error_messages.get(type(err))
        if _message_function: return _message_function(err)
    
    return None

def report_error(error, function, catagory = 'general', err_level = 'warn', interrupt_user = False, write_to_disk = False, stop_program = False, custom_message = ''):
    _admin_message = (f'[{get_timestamp}]    Level: {err_level}    Function: {function}    Error: {error}')
    
    def show_interrupt(): # Sends request to tk thread to notify user of issue
        ui_ready_event.wait()
        local_state['req_to_tk_thread'].put(('interrupt_user', _user_message, stop_program))
        
        if write_failure: # Hijacks the event to ensure users have time to write down errors if error cannot be written to disk
            ui_ready_event.clear()
            ui_ready_event.wait()

        return
    
    if not custom_message == '': # Custom messages override default messages
        _user_message = custom_message
    else:
        get_error_message(error, catagory)
            
    if write_to_disk: # Tries to write to disk, on failure alerts user for manual reporting
        try:
            with open(LOG_FILE, 'a') as file:
                file.write(_admin_message)
        except:
            _user_message = 'An error has occured but was not able to be logged.\nPlease write this down and give it to your administrator:\n{_admin_message}'
            interrupt_user = True
            write_failure = True
            
    if interrupt_user:
        show_interrupt()
    
    if stop_program:
        exit(0)
        
def generate_default_config(parser):
    _default_config = {
        'GUI': {
            'fullscreen': 'True',
            'vkeybaord': 'True',
            'theme': 'dark',
            'main_object_name': 'Order',
            'main_obj_subtitle': 'Phone Number',
            'main_obj_flags_enabled': False,
            'main_obj_flag_a_name': 'Dessert',
            'main_obj_flag_b_name': 'Milkshake',
            'sec_object_name': '86',
            'sec_obj_flag_a_name': 'Limited',
            'sec_obj_flag_b_name': 'O/S',
            'sec_obj_flags_enabled': False,
            'enable_masking': True,
            'debug': 'False'
        },

        'NETWORK': {
            'broker_ip': '',
            'broker_qos': '1',
            'broker_port': '1883',
        },

        'CLIENT': {
            'client_id': '',
            'client_audience': '',
            'client_name': '',
            'client_position': '',
            'client_password': '',
        },

        'SECRETS': {
            'preshared_key': '',
            'backup_preshared_key': '',
            'expiration_date': '',
        }
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
        function = 'write_config_to_file'
        error = e
        level = 'crit'
        catagory = 'disk'
        
        
        report_error(error, 
                    function, 
                    catagory = catagory, 
                    err_level = level, 
                    interrupt_user = True, 
                    write_to_disk = True, 
                    stop_program = False)
        
def get_config():
    ''' Retrieves stored configuration or creates a new config file / loads defaults
        if no config file is found / accessible '''
    global parser
    parser = configparser.ConfigParser()
    config = {}

    if not os.path.exists(CONFIG_FILE):
        parser = generate_default_config(parser)
        write_config_to_file(parser)
            
    else:
        try:
            parser = configparser.ConfigParser()
            parser.read(CONFIG_FILE)
        except Exception as e:
            error = e
            function = 'get_config'
            catagory = 'disk'
            level = 'crit'
            interrupt = True
            write = True
            stop = True
            
            report_error(error,
                         function,
                         catagory,
                         level,
                         interrupt,
                         write,
                         stop)
            
    config = {'fullscreen': parser.getboolean('GUI', 'fullscreen', fallback = True),
            'vkeyboard': parser.getboolean('GUI', 'vkeyboard', fallback = True),
            'theme': parser.get('GUI', 'theme', fallback = 'dark'),
            'main_object_name': parser.get('GUI', 'main_object_name', fallback = 'Order'),
            'main_obj_subtitle': parser.get('GUI', 'main_obj_subtitle', fallback = 'Phone Number'),
            'main_flags_enabled': parser.getboolean('GUI', 'main_flags_enabled', fallback = False),
            'main_obj_flag_a_name': parser.get('GUI', 'main_obj_flag_a_name', fallback = 'Dessert'),
            'main_obj_flag_b_name': parser.get('GUI', 'main_obj_flag_b_name', fallback = 'Milkshake'),
            'main_enable_masking': parser.getboolean('GUI', 'main_enable_masking', fallback = True),
            'main_enable_timer': parser.getboolean('GUI', 'main_enable_timer', fallback = True),
            'sec_object_name': parser.get('GUI', 'sec_object_name', fallback = '86'),
            'sec_flag_a_name': parser.get('GUI', 'sec_flag_a_name', fallback = 'Limited'),
            'sec_flag_b_name': parser.get('GUI', 'sec_flag_b_name', fallback = 'O/S'),
            'sec_flags_enabled': parser.get('GUI', 'sec_flags_enabled', fallback = False),
            'sec_enable_masking': parser.getboolean('GUI', 'secondary_enable_masking', fallback = True),
            'sec_enable_timer': parser.getboolean('GUI', 'secondary_enable_timer', fallback = True),
            'timer_update_delay': parser.get('GUI', 'timer_update_delay', fallback = '5'),
            'enable_debug': parser.get('GUI','debug', fallback = False),
            'broker_ip': parser.get('NETWORK', 'broker_ip', fallback = '192.168.1.1'),
            'broker_port': parser.get('NETWORK', 'broker_port', fallback = '1883'),
            'broker_qos': parser.get('NETWORK', 'broker_qos', fallback = '1'),
            'client_id': parser.get('CLIENT', 'client_id', fallback = 'example_id'),
            'client_audience': parser.get('CLIENT', 'client_audience', fallback = 'example_audience'),
            'client_name': parser.get('CLIENT', 'client_name', fallback = 'Example Name'),
            'client_position': parser.get('CLIENT', 'client_position', fallback = 'example_position'),
            'client_password': parser.get('CLIENT', 'client_password', fallback = 'example_password'),
            'psk': parser.get('SECRETS', 'client_psk', fallback = 'EXAMPLEb712e17c9614e2871657d5eab21faba79a59f37000cf3afac3f9486ec'),
            'backup_psk': parser.get('SECRETS', 'client_backup_psk', fallback = 'EXAMPLEb712e17c9614e2871657d5eab21faba79a59f37000cf3afac3f9486ec'),
            'expiration_date': parser.get('SECRETS', 'client_psk_exp_date', fallback = '01/01/01')
            }

    if config: 
        config_initialized.set()
        return config

#Pre-load images to reduce object creation times.
def load_images(): 
    def _generate_placeholder_img():
        _placeholder = Image.new('RGBA', (38, 38), (200, 200, 200, 255))
        _draw = ImageDraw.Draw(_placeholder)
        _draw.line((0, 0, 38, 38), fill = 'red', width = 2)
        _draw.line((0, 38, 38, 0), fill = 'red', width = 2)

        return _placeholder
    
    _imgs = os.listdir(IMG_DIR)
    _img_list = [item for item in _imgs]
    _img_list.remove('logo.ico')

    for item in _img_list:
        try:
            _path = os.path.join(IMG_DIR, item)
            _img = Image.open(_path).resize((38, 38))
        except Exception as e:
            _img = _generate_placeholder_img()
            
            error = e
            function = 'load_images'
            catagory = 'disk'
            level = 'warn'
            interrupt = False
            write = True
            
            report_error(error, function, catagory, level, interrupt, write)

        _img_obj = ImageTk.PhotoImage(_img)
        _img_name = os.path.splitext(item)[0]
        update_local_state('images', {_img_name: _img_obj})

# Used to safely update program state - queues are updated directly, config changes are written to disk
def update_local_state(key, value, section=None, sub_section=None):
    global local_state

    with lock:
        if section is not None:
            print('Section Detected: {section}')
            if key not in local_state:
                print(f'Key Not Detect: {key}')
                local_state[key] = {}

            if section not in local_state[key]:
                print(f'Section Not Detected: {section}')
                local_state[key][section] = {}

            if sub_section is None:
                print(f'Sub Section Not Provided: {sub_section}')
                local_state[key][section] = value
                print(local_state[key][section])
            else:
                print(f'Sub Section Provided: {sub_section}')
                local_state[key][section][sub_section] = value
                print(local_state[key][section][sub_section])
            
            if key == 'config':
                write_config_to_file()

        else:
            if key not in local_state:
                local_state[key] = {}

            # Handle flat dictionaries like obj_refs
            if isinstance(local_state[key], dict) and isinstance(value, dict):
                local_state[key].update(value)
            else:
                local_state[key] = value

def mqtt_thread():
    '''Handles MQTT client connections, disconnections, authentication, and communications.'''

    # Paho-MQTT requires certain callback functions to accept parameters like client, userdata, rc, msg, properties, and flags.
    # These parameters must be included even if unused. Do not remove them from the function definitions.

    # The client authenticates to the broker using standard protocols.
    # The broker then authenticates to the client using HMACs generated from PSKs and Nonces over the authentication topic.
    # Once the broker is authenticated, the client unsubscribes from the authentication topic and subscribes to the main topic.

    # Each communication has a 30-second timeout for both sides.
    global local_state
    verification_event = threading.Event()
    client = mqtt.Client(local_state['config']['client_id'])

    def _on_disconnect(client, userdata, rc, properties = None):
        if not local_state['manual_reconnect']:
            local_state['broker_verified'] = False
#
# UPDATE QUEUE PUSH
#         
        local_state['req_to_logic_thread'].put(('mqtt_update','broker','diconnected'))
    
    def _on_connect(client, userdata, flags, rc, properties = None):
        if not local_state['manual_reconnect']: # Only for debug. Unsafe to use otherwise.
            _verify_broker()
    
    def _on_message(client, userdata, msg, properties = None):
        message = msg.payload.decode()

        if is_verifying_broker:
            # Expected format: client_id,response_type,payload
            _client_id, _response_type, rec_payload = message.split(',')

            if _client_id == local_state['config']['client']['client_id']:
                verification_event.set()
                
                _functions = {
                    'hmac_auth_req_ok': _verify_broker._generate_nonce,
                    'psk_refr_req_ok': _verify_broker._generate_nonce,
                    'hmac_auth_nonce_echo': _verify_broker._request_hmac,
                    'psk_refr_nonce_echo': _verify_broker._generate_psk,
                    'hmac_auth_hmac_resp': _verify_broker._compare_hmac,
                    'hmac_auth_echo': _verify_broker._set_auth,
                    'psk_refr_echo': _verify_broker._verify_new_psk
                }
                
                _action = _functions.get(_response_type)
                if _action:
                    _action(rec_payload)

        else:
            # Expected format: sender_id,audience_id,request_type,object_id,object_title,object_subtitle,object_flag_a,object_flag_b
            _processed_payload = []

            _split_payload = message.split(',', maxsplit = 7)
            _payload_header = _split_payload[:4]

            if _payload_header[2] in [local_state['config']['CLIENT']['client_id'], 
                                local_state['config']['CLIENT']['client_role']]:
               
                if _payload_header[2] == 'create_object': 
                    _payload_footer = _split_payload[4:]
                    _processed_payload.extend(_payload_header)
                    _processed_payload.extend(_payload_footer)
                else:
                    _processed_payload.extend(_payload_header)

                local_state['to_logic_thread'].put(_processed_payload)

    def _publish(topic, payload):
        _qos = local_state['config']['NETWORK']['broker_qos']
        client.publish(topic, payload, _qos)

    def _verify_broker():
        ''' Handles broker-to-client authentication '''
        # Every step has a 30 second timeout. If a message is not received the connection is terminated.
        global is_verifying_broker
        _nonce = None

        is_verifying_broker = True

        topic = 'authentication'
        client.subscribe(topic)

        psk_exp_obj = datetime.strptime(local_state['config']['SECRETS']['expiration_date'], '%m/%d/%y')
        today = datetime.today()

        # Determines the type of request to send - If PSK is expired, requests a refresh using backup PSK
        if psk_exp_obj >= today.date():
            request_type = f'hmac_auth_req'
        elif psk_exp_obj < today.date():
            request_type = f'hmac_refr_req'
        
        client_id = local_state['config']['CLIENT']['client_id']

        payload = f'{request_type},{client_id}'
        _publish(topic, payload)

        verification_event.wait(timeout = 30)
        if not verification_event.is_set(): _abort_auth('_verify_broker', 'timeout')

        def _abort_auth(function, reason):
            local_state['to_logic_thread'].put((f'report_error,False,True,broker auth failed: {function}: {reason}, Failed to authenticate broker. Please verify network settings and try again.'))
            client.disconnect()
            
        def _generate_nonce(rec_payload):
            _nonce = secrets.token_hex(length = 32)
            payload = f'{client_id},gen_nonce,{_nonce}'
            verification_event.clear()
            # Confirming received nonce with broker
            _publish(topic, payload)

            verification_event.wait(timeout = 30)
            if not verification_event.is_set(): _abort_auth('_generate_nonce', 'timeout')

        def _request_hmac(rec_payload):
            payload = f'{client_id},hmac_auth_req_hmac,none'

            verification_event.clear()
            _publish(topic, payload)

            verification_event.wait(timeout = 30)
            if not verification_event.is_set(): _abort_auth('_request_hmac', 'timeout')
        
        def _compare_hmac(rec_payload):
            _encoded_psk = local_state['config']['SECRETS']['preshared_key'].encode()
            _expected_hmac = hmac.new(_encoded_psk, _nonce, hashlib.sha256).hexdigest()
            del _nonce
            del _encoded_psk

            if not _expected_hmac == rec_payload: 
                payload = f'{client_id},hmac_auth_req_resp,hmac_failure'
                _publish(topic, payload)
                _abort_auth('_compare_hmac', 'received invalid hmac')
            
            else:
                verification_event.clear()
                payload = f'{client_id},hmac_auth_verify_ok,hmac_ok'
                _publish(topic, payload)

                verification_event.wait(timeout = 30)
                if not verification_event.is_set(): _abort_auth('_compare_hmac', 'timeout')
            
        def _set_auth(rec_payload):
            if rec_payload == 'hmac_ok':
                local_state['broker_verified'] = True

            else:
                payload = f'{client_id},hmac_auth_req_final','no_response'
                _publish(topic, payload)
                _abort_auth('_finalize_hmac_auth', "hmac not ok'd")

        def _encrypt_psk(_old_psk, _new_psk):
            
            if isinstance(_old_psk, str):
                _old_psk = _old_psk.encode('utf-8')
            if isinstance(_new_psk, str):
                _new_psk = _new_psk.encode('utf-8')

            if len(_old_psk) == 32 and len(_new_psk) == 32:
                _cipher = Cipher(algorithms.AES(_old_psk), modes.CFB(_nonce), backend=default_backend())
                _encryptor = _cipher.encryptor()

                _padder = padding.PKCS7(algorithms.AES.block_size).padder()
                _padded_new_psk = _padder.update(_new_psk) + _padder.finalize()

                _encrypted_psk = _encryptor.update(_padded_new_psk) + _encryptor.finalize()

                return _encrypted_psk

            else:
                local_state['to_logic_thread'].put('report_error,crit,True,True,_encrypt_psk: None,Unable to encrypt new PSK for transmission. Please ensure PSK is of valid 32 character hexidecimal format.')
                
                return None

        def _generate_psk(rec_payload):
            update_local_state('new_psk', secrets.token_hex(32))
            update_local_state('psk_cipher_text', 
                                _encrypt_psk(local_state['config']['SECRETS']['psk'], 
                                local_state('psk_cipher_text')
                                ))

            payload = f'{client_id},psk_refr_new_psk,{local_state["psk_cipher_text"]}'
            _publish(topic, payload)

            verification_event.wait(timeout = 30)
            if not verification_event.is_set(): 
                with lock:
                    del local_state['new_psk'], local_state['psk_cipher_text']
                _abort_auth('_generate_psk', 'timeout')

        def _verify_new_psk(rec_payload):
            if rec_payload == local_state['psk_cipher_text']:
                _payload = f'{client_id},psk_refr_ok,none'

                verification_event.clear()
                _publish(topic, _payload)

                verification_event.wait(timeout = 30)
                if not verification_event.is_set(): _abort_auth('_verify_new_psk', 'timeout')
        
        def _finalize_new_psk(rec_payload):
            update_local_state('config', local_state['new_psk'],'SECRETS', 'preshared_key')
            with lock:
                del local_state['psk_cipher_text'], local_state['new_psk']

            _new_expiration_date = datetime.today() + relativedelta(months=3)
            _new_expiration_date_str = _new_expiration_date.strftime('%m/%d/%y')
            update_local_state('config', _new_expiration_date_str, 'SECRETS', 'expiration_date')
            
            write_config_to_file()

            client.disconnect()
            client.reconnect()

    client.on_connect = _on_connect
    client.on_disconnect = _on_disconnect
    client.on_message = _on_message

def logic_thread():
    global local_state

    def _notify_user(_title, _message, _timeout=10_000): # 1,000ms = 1s
        # Displays a non-blocking, default-ok messagebox
        """ def create_messagebox():
            msg_box = Toplevel(root)
            msg_box.title(_title)

            _label = Label(msg_box, text=_message, padx=20, pady=10)
            _ok_button = Button(msg_box, text="OK", command=msg_box.destroy)

            _label.pack()
            _ok_button.pack(pady=5)

            # Set a timer to automatically invoke the OK button after `_timeout` ms
            msg_box.after(_timeout, _ok_button.invoke)

        root.after(0, create_messagebox) """

    def _report_error(_level, _stop, _alert_user, _admin_desc, _user_desc):
        ''' Logs and optionally exits the program and / or reports errors to the user '''

        _ts = get_timestamp(True)

        try:
            with open(LOG_FILE, 'a') as file:
                file.write(f'{_ts}   {_admin_desc}')
        
        except Exception as _e:
            messagebox.showerror(f'Error', 'An error has occured while attempting to log an error.\nThis may be a result of several issues.\nError: {_e}')

        if not _stop:
            _exit_message = 'The program will continue to run but user is advised to report this issue.'
        else:
            _exit_message = 'The program cannot continue to run and the user is advised to report this issue.'

        if _alert_user:
            _notify_user(f'Type: {_level}', f'{_user_desc}\n{_exit_message}', None)

    def _create_object(rec_payload = None):
        return
    
    def _edit_object(rec_payload = None):
        return

    def _check_queue():
        _actions = {
            'create_object': _create_object,
            'edit_object': _edit_object,
        }

        while not local_state['to_logic_thread'].empty():
            try:
                rec_payload = local_state['to_logic_thread'].get()
                _action = _actions.get(rec_payload[2])
                _action(rec_payload)
            
            except Exception as e:
                get_error_message(e, 'to_logic_thread_queue')
        
        threading.Timer(1.0, _check_queue).start()

        _check_queue()

def tk_thread():
    global local_state
    global ui_ready_event
    global timer_thread
    
    ui_ready_event = threading.Event() # Signals to the rest of the program that they can it with the UI

    root = tk.Tk()
    root.title(f'No More Running v{PROG_VER}')
    root.config(bg='#2B2B2B')

    _root_min_width = 1024
    _root_min_height = 600
    _root_max_width = 1920
    _root_max_height = 1080
    _screen_width = root.winfo_screenwidth()
    _screen_height = root.winfo_screenheight()
    _root_fullscreen = local_state['config']['fullscreen']
    
    if platform.system() == "Linux":
        _prefix = f'{local_state['icons']}_'
        _icon_path = os.path.join(IMG_DIR, f'{_prefix}logo.png')
        _icon = PhotoImage(file = _icon_path)
        root.iconphoto(True, _icon)
    else:
        root.iconbitmap(ICO_PATH)

    if _screen_height < _root_min_height or _screen_width < _root_min_width:
        exit(0)

    if not _root_fullscreen:
        if _screen_height > _root_max_height:
            _final_height = int(_root_max_height * 0.75)
        else:
            _final_height = int(_screen_height * 0.75)

        if _screen_width > _root_max_width:
            _final_width = int(_root_max_width * 0.75)
        else:
            _final_width = int(_screen_width * 0.75)

        root.minsize(_root_min_width, _root_min_height)
        root.maxsize(_root_max_width, _root_max_height)
        root.geometry(f'{_final_width}x{_final_height}')
        update_local_state('screen_height', int(_final_height))

    else:
        root.attributes('-fullscreen', True)
        update_local_state('screen_height', int(_screen_height))

    update_local_state('screen_width', int(_screen_width))

    min_sidebar_width = int(_root_min_width / 12)
    max_sidebar_width = int(_root_max_width / 8)

    main_content_panel = ContentPanel(root)
    sec_content_panel = ContentPanel(root, mode = 'sec')
    settings_content_panel = ContentPanel(root)

    sidebar = SideBar(root, main_content_panel = main_content_panel, min_width = min_sidebar_width, max_width = max_sidebar_width)
    status_panel = StatusPanel(root, height = (root.winfo_height() / 18), width = int(root.winfo_width() - sidebar.winfo_width()))
    root.grid_rowconfigure(0, weight=1)
    root.grid_columnconfigure(1, weight=1)

    main_content_panel.grid(row = 0, column = 1, stick = 'nsew')
    sidebar.grid(row = 0, rowspan = 2, column = 0, sticky="ns")
    status_panel.grid(row = 1, column = 1, sticky = 'ew')

    sec_content_panel.grid(row = 0, column = 1, stick = 'nsew')
    settings_content_panel.grid(row = 0, column = 1, stick = 'nsew')
    sec_content_panel.grid_remove()
    settings_content_panel.grid_remove()

    update_local_state('active_panel_ref', main_content_panel)

    update_local_state('mc_panel_ref', main_content_panel)
    update_local_state('sec_panel_ref', sec_content_panel)
    update_local_state('set_panel_ref', settings_content_panel)

    root.resizable(False, False)

    def _interpolate_color(color1, color2, factor):
        r1, g1, b1 = color1
        r2, g2, b2 = color2
        r = int(r1 + (r2 - r1) * factor)
        g = int(g1 + (g2 - g1) * factor)
        b = int(b1 + (b2 - b1) * factor)

        return f"#{r:02x}{g:02x}{b:02x}"
    
    def _animate_background():
        global gradient_step, current_color

        pride_colors = [
        (228, 3, 3),    # Red
        (255, 140, 0),  # Orange
        (255, 237, 0),  # Yellow
        (0, 128, 38),   # Green
        (0, 77, 255),   # Blue
        (117, 7, 135)   # Violet
        ]

        factor = (gradient_step % 100) / 100
        next_color = _interpolate_color(pride_colors[current_color], pride_colors[(current_color + 1) % len(pride_colors)], factor)
        main_content_panel.configure(bg=next_color)

        gradient_step += 1
        if gradient_step % 100 == 0:
            current_color = (current_color + 1) % len(pride_colors)
        
        main_content_panel.after(60, _animate_background)

    def _time_tracker():
        _delay = int(local_state['config']['timer_update_delay'])
        _delay = _delay * 1000
        for dictionary in [local_state['main_obj_refs'], local_state['sec_obj_refs']]:
            for _obj in dictionary.values():
                if _obj.winfo_ismapped(): # Only update currently displayed objects
                    if hasattr(_obj, 'creation_time'): 
                        _creation_time = _obj.creation_time
                        _elapsed_time = (time.time() - _creation_time)
                        if not _elapsed_time >= 86400:
                            _formatted_time = time.strftime('%H:%M:%S', time.gmtime(_elapsed_time))
                            _obj.lbl_timer.configure(text = f'{_formatted_time}')
                        else:
                            _obj.lbl_timer.configure(text = '> 24 Hours')

        root.after(_delay, _time_tracker)
    
    timer_thread = threading.Thread(target = _time_tracker, daemon = True)

    if local_state['config']['theme'] == 'pride':
        global gradient_step, current_color
        gradient_step = 0
        current_color = 0
        _animate_background()

    load_images()

    timer_thread.start()
    
    root.update_idletasks() # Sidebar isn't drawn on screen w/o this. Forces redraw.
    root.after(500, ui_ready_event.set()) # Ensures the UI is fully displayed and ready before allowing other threads to send requests to the tk thread.
    root.mainloop()

def app_start():
    global local_state

    local_state = {
        'config':get_config(),
        'images': {},
        'main_obj_refs': {}, # Holds all main and sec obj references with UUID as key
        'sec_obj_refs': {},
        'mc_panel_ref': None,
        'sec_panel_ref': None,
        'set_panel_ref': None,
        'active_panel_ref': None,
        'broker_verified': False,
        'manual_reconnect': False,
        'side_bg_color': '',
        'side_fg_color': '',
        'mc_bg_color': '',
        'mc_fg_color': '',
        'accent_bg_color': '',
        'accent_fg_color': '',
        'icons': '',
        'screen_width': None,
        'screen_height': None,
        'is_object_active': False,
        'active_obj_id': None,
        'req_to_mqtt_thread': Queue(),
        'req_to_tk_thread': Queue(),
        'obj_to_tk_thread': Queue(),
        'req_to_logic_thread': Queue(),
        'obj_to_logic_thread': Queue(),
    }
    
    themes = {
        'user_defined':{
            'mc_bg_color': '',
            'mc_fg_color': '',
            'side_bg_color': '',
            'side_fg_color': '',
            'accent_fg_color': '',
            'accent_bg_color': '',
            'icons': ''
        },
        'light': {
            'mc_bg_color': '#E5D9F2',
            'mc_fg_color': '#000000',
            'side_bg_color': '#A594F9',
            'side_fg_color': '#000000',
            'accent_fg_color': '#000000',
            'accent_bg_color': '#A594F9',
            'icons': 'dark'
        },

        'light_blue': {
            'mc_bg_color': '#89A8B2',
            'mc_fg_color': '#000000', 
            'side_bg_color': '#B3C8CF',
            'side_fg_color': '#000000',
            'accent_fg_color': '#000000',
            'accent_bg_color': '#FFFFFF',
            'icons': 'dark'
        },

        'light_green': {
            'mc_bg_color': '#C2FFC7',
            'mc_fg_color': '#000000',
            'side_bg_color': '#9EDF9C',
            'side_fg_color': '#000000',
            'accent_fg_color': '',
            'accent_bg_color': '',
            'icons': 'dark'
        },

        'dark': {
            'mc_bg_color': '#2B2B2B',
            'mc_fg_color': '#0F0F0F',
            'side_bg_color': '#3C3C3C',
            'side_fg_color': '#F0F0F0',
            'accent_fg_color': '#0F0F0F',
            'accent_bg_color': '#C0C0C0',
            'icons': 'dark'
        },

        'dark_blue': {
            'mc_bg_color': '#000000',
            'mc_fg_color': '#F0F0F0',
            'side_bg_color': '#0000BB',
            'side_fg_color': '#000000',
            'accent_fg_color': '#0F0F0F',
            'accent_bg_color': '#0000BB',
            'icons': 'dark'
        },

        'dark_red': {
            'mc_bg_color': '#000000',
            'mc_fg_color': '#F0F0F0',
            'side_bg_color': '#BB0000',
            'side_fg_color': '#FFFFFF',
            'accent_fg_color': '#0F0F0F',
            'accent_bg_color': '#BB0000',
            'icons': 'dark'
        },

        'dark_purple': {
            'mc_bg_color': '#000000',
            'mc_fg_color': '#F0F0F0',
            'side_bg_color': '#8D00FF',
            'side_fg_color': '#000000',
            'accent_fg_color': '#0F0F0F',
            'accent_bg_color': '#C0C0C0',
            'icons': 'dark'
        },

        'super_dark': {
            'mc_bg_color': '#000000',
            'mc_fg_color': '#3F3F3F',
            'side_bg_color': '#3F3F3F',
            'side_fg_color': '#FFFFFF',
            'accent_fg_color': '#FFFFFF',
            'accent_bg_color': '#3F3F3F',
            'icons': 'dark'
        },

        'h4x0r': {
            'mc_bg_color': '#BB0000',
            'mc_fg_color': '#000000',
            'side_bg_color': '#000000',
            'side_fg_color': '#BB0000',
            'accent_bg_color': '#000000',
            'accent_fg_color': '#BB0000',
            'icons': 'red'
        },

        'pride': {
            'mc_bg_color': '#F0F0F0',
            'mc_fg_color': '#0F0F0F',
            'side_bg_color': '#F0F0F0',
            'side_fg_color': '#000000',
            'accent_fg_color': '#F0F0F0',
            'accent_bg_color': '#0F0F0F',
            'icons': 'dark'
        }
    }


    selected_theme = local_state['config']['theme']
    theme_colors = themes.get(selected_theme, themes['light'])
    local_state.update(theme_colors)

    mqtt_thread_obj = threading.Thread(target = mqtt_thread, daemon = True)
    logic_thread_obj = threading.Thread(target = logic_thread, daemon = True)

    config_initialized.wait(timeout = 30)

    if not config_initialized.is_set():
        with open(LOG_FILE, 'a') as file:
            _ts = get_timestamp(True)
            file.write(f'{_ts}  Configuration initialization timeout.')

    else:
        mqtt_thread_obj.start()
        logic_thread_obj.start()

    tk_thread()

    mqtt_thread_obj.join()
    logic_thread_obj.join()
    timer_thread.join()
    exit(0)

if __name__ == '__main__':
    app_start()
    exit(0)