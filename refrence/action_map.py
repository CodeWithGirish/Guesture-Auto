import pyautogui
import time
import logging
import threading
import platform
import os
import json
import ctypes # Required for LockWorkStation
import subprocess # Better for launching apps
import numpy as np # Required for Smart Mouse

# Relative imports
from .config import Config
from .voice_engine import VoiceEngine

logger = logging.getLogger(__name__)

# Cross-platform guards
IS_WINDOWS = platform.system() == "Windows"
pyautogui.FAILSAFE = False  # Prevent crash when mouse hits corner

class ActionMap:
    def __init__(self):
        self.config_file = os.path.join(Config.PROJECT_ROOT, 'data', 'action_config.json')
        self.mapping = {}

        # Pass self to VoiceEngine so it can trigger actions
        self.voice_engine = VoiceEngine(self)

        # State for continuous actions (Smart Mouse, Scrolling)
        self.active_continuous_action = None
        self.scroll_speed = 0
        self.mouse_active = False

        # Smoothing variables for mouse
        self.prev_x, self.prev_y = 0, 0
        self.smoothening = 5

        self.load_mapping()

    def load_mapping(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        self.mapping = {item["gesture"]: item["action"] for item in data}
                    else:
                        self.mapping = data.get("mappings", {})
                logger.info(f"Loaded {len(self.mapping)} mappings.")
            except Exception as e:
                logger.error(f"Failed to load action config: {e}")
                self.mapping = {}
        else:
            logger.warning("No action_config.json found. Using defaults.")
            self.mapping = {}

    def save_mapping(self):
        try:
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            with open(self.config_file, 'w') as f:
                json.dump({"mappings": self.mapping}, f, indent=4)
            return True
        except Exception as e:
            logger.error(f"Failed to save mapping: {e}")
            return False

    def get_available_actions(self):
        """Returns list of all supported action keys."""
        actions = [
            # Media
            "volume_up", "volume_down", "mute",
            "play_pause", "next_track", "prev_track",

            # Scrolling
            "scroll_up", "scroll_down", "scroll_left", "scroll_right",

            # Productivity
            "copy", "paste", "save", "undo", "redo",

            # Browser
            "new_tab", "close_tab", "switch_tab", "refresh",
            "browser_history", "browser_downloads", # [NEW]

            # Windows / System
            "win_left", "win_right", "maximize", "minimize",
            "desktop", "alt_tab", "screenshot", "task_view", "snap_layout", # [NEW]
            "lock_screen",

            # Apps (New Category)
            "open_calc", "open_notepad", "open_settings",
            "open_file_explorer", "open_task_manager", "open_cmd", # [NEW]

            # Power (New Category)
            "system_shutdown", "system_restart", "system_sleep", "sign_out", # [NEW]

            # Mouse / Text
            "mouse_click", "mouse_right", "mouse_double",
            "type_hello", "smart_mouse"
        ]
        return sorted(actions)

    def map_gesture(self, gesture_name, action_name):
        self.mapping[gesture_name] = action_name
        self.save_mapping()

    def rename_mapping(self, old_name, new_name):
        if old_name in self.mapping:
            self.mapping[new_name] = self.mapping.pop(old_name)
            self.save_mapping()

    def is_continuous(self, gesture_name):
        """Returns True if the mapped action requires continuous updates."""
        action = self.mapping.get(gesture_name)
        return action in ["smart_mouse", "dynamic_scroll"]

    def execute(self, gesture_name, landmarks=None):
        action = self.mapping.get(gesture_name)
        if not action: return None

        if self.active_continuous_action and action != self.active_continuous_action:
            self._stop_continuous()

        try:
            return self.perform_action(action, landmarks)
        except Exception as e:
            logger.error(f"Error executing {action}: {e}")
            return None

    def perform_action(self, action, landmarks=None):
        if not action: return None

        # --- Media Controls ---
        if action == "volume_up": pyautogui.press("volumeup")
        elif action == "volume_down": pyautogui.press("volumedown")
        elif action == "mute": pyautogui.press("volumemute")
        elif action == "play_pause": pyautogui.press("playpause")
        elif action == "next_track": pyautogui.press("nexttrack")
        elif action == "prev_track": pyautogui.press("prevtrack")

        # --- Browser / Nav ---
        elif action == "new_tab": pyautogui.hotkey("ctrl", "t")
        elif action == "close_tab": pyautogui.hotkey("ctrl", "w")
        elif action == "switch_tab": pyautogui.hotkey("ctrl", "tab")
        elif action == "refresh": pyautogui.press("f5")
        elif action == "browser_history": pyautogui.hotkey("ctrl", "h") # [NEW]
        elif action == "browser_downloads": pyautogui.hotkey("ctrl", "j") # [NEW]

        # --- Productivity ---
        elif action == "copy": pyautogui.hotkey("ctrl", "c")
        elif action == "paste": pyautogui.hotkey("ctrl", "v")
        elif action == "save": pyautogui.hotkey("ctrl", "s")
        elif action == "undo": pyautogui.hotkey("ctrl", "z")
        elif action == "redo": pyautogui.hotkey("ctrl", "y")
        elif action == "screenshot": pyautogui.screenshot(f"screenshot_{int(time.time())}.png")

        # --- Window Management ---
        elif action == "win_left": pyautogui.hotkey("win", "left")
        elif action == "win_right": pyautogui.hotkey("win", "right")
        elif action == "maximize": pyautogui.hotkey("win", "up")
        elif action == "minimize": pyautogui.hotkey("win", "down")
        elif action == "desktop": pyautogui.hotkey("win", "d")
        elif action == "alt_tab": pyautogui.hotkey("alt", "tab")
        elif action == "task_view": pyautogui.hotkey("win", "tab") # [NEW]
        elif action == "snap_layout": pyautogui.hotkey("win", "z") # [NEW] Windows 11 feature

        # --- Application Launchers [NEW] ---
        elif action == "open_calc":
            os.system("start calc") if IS_WINDOWS else None
        elif action == "open_notepad":
            os.system("start notepad") if IS_WINDOWS else None
        elif action == "open_settings":
            os.system("start ms-settings:") if IS_WINDOWS else None
        elif action == "open_file_explorer":
            pyautogui.hotkey("win", "e")
        elif action == "open_task_manager":
            pyautogui.hotkey("ctrl", "shift", "esc")
        elif action == "open_cmd":
            os.system("start cmd") if IS_WINDOWS else None

        # --- System Power [NEW] ---
        elif action == "system_shutdown":
            # Shows prompt instead of immediate shutdown for safety
            os.system("shutdown /s /t 60") if IS_WINDOWS else None
        elif action == "system_restart":
            os.system("shutdown /r /t 60") if IS_WINDOWS else None
        elif action == "system_sleep":
            os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0") if IS_WINDOWS else None
        elif action == "sign_out":
            os.system("shutdown /l") if IS_WINDOWS else None
        elif action == "lock_screen":
            ctypes.windll.user32.LockWorkStation() if IS_WINDOWS else None

        # --- Mouse Emulation ---
        elif action == "mouse_click": pyautogui.click()
        elif action == "mouse_right": pyautogui.rightClick()
        elif action == "mouse_double": pyautogui.doubleClick()
        elif action == "smart_mouse": self._action_smart_mouse(landmarks)

        # --- Scrolling ---
        elif action == "scroll_up": pyautogui.scroll(300)
        elif action == "scroll_down": pyautogui.scroll(-300)
        elif action == "scroll_left": pyautogui.hscroll(-100)
        elif action == "scroll_right": pyautogui.hscroll(100)

        # --- Text / Custom ---
        elif action == "type_hello": pyautogui.write("Hello World!")
        elif action.startswith("type:"):
            text = action.split("type:", 1)[1]
            pyautogui.write(text)
        elif action.startswith("cmd:"):
            cmd = action.split("cmd:", 1)[1]
            if IS_WINDOWS and cmd.strip().startswith("open "):
                cmd = cmd.replace("open ", "explorer ", 1)
            os.system(cmd)

        return action

    def _action_smart_mouse(self, landmarks):
        if not landmarks: return
        w_scr, h_scr = pyautogui.size()
        index_tip = landmarks[8]
        thumb_tip = landmarks[4]

        margin = 0.1
        x = np.interp(index_tip.x, (margin, 1-margin), (0, w_scr))
        y = np.interp(index_tip.y, (margin, 1-margin), (0, h_scr))

        curr_x = self.prev_x + (x - self.prev_x) / self.smoothening
        curr_y = self.prev_y + (y - self.prev_y) / self.smoothening

        pyautogui.moveTo(curr_x, curr_y)
        self.prev_x, self.prev_y = curr_x, curr_y

        dist = ((index_tip.x - thumb_tip.x)**2 + (index_tip.y - thumb_tip.y)**2)**0.5
        click_threshold = 0.05

        if dist < click_threshold:
            if not self.mouse_active:
                pyautogui.mouseDown()
                self.mouse_active = True
        else:
            if self.mouse_active:
                pyautogui.mouseUp()
                self.mouse_active = False

    def _stop_continuous(self):
        self.active_continuous_action = None
        self.scroll_speed = 0
        self.mouse_active = False

    def type_text(self, text):
        pyautogui.write(text)