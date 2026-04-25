import time
import sys
import subprocess
# Safe dependency check
HAS_PYAUTOGUI = False
try:
    import pyautogui
    HAS_PYAUTOGUI = True
    # SAFETY: Keep FAILSAFE enabled. Moving the mouse to any corner will abort.
    # We add a short pause between actions to prevent runaway loops.
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.05  # 50 ms inter-action safety gap
except ImportError:
    print("[Warning] pyautogui module missing. Automation actions will fail safely.")

from backend.services.action_mapping_service import ActionMappingService

class AutomationExecutor:
    def __init__(self):
        self.mapping_service = ActionMappingService()
        self.last_execution = {}
        self.drag_active = False # State tracker for toggling Drag and Drop

    def _get_active_window_title(self):
        """Returns the focused window title — cross-platform."""
        try:
            if sys.platform == 'win32':
                import ctypes
                hwnd = ctypes.windll.user32.GetForegroundWindow()
                length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
                buf = ctypes.create_unicode_buffer(length + 1)
                ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
                return buf.value.lower()
            elif sys.platform == 'darwin':
                # macOS: query via AppleScript
                result = subprocess.run(
                    ['osascript', '-e',
                     'tell application "System Events" to get name of first process whose frontmost is true'],
                    capture_output=True, text=True, timeout=1
                )
                return result.stdout.strip().lower()
            else:
                # Linux/X11: use xdotool if available
                result = subprocess.run(
                    ['xdotool', 'getactivewindow', 'getwindowname'],
                    capture_output=True, text=True, timeout=1
                )
                return result.stdout.strip().lower()
        except Exception:
            return ""

    def _is_app_running(self, app_name):
        """Checks if an application is running by checking the active window and process list."""
        app_lower = app_name.lower()
        
        # 1. Fast check: is it currently focused?
        active_window = self._get_active_window_title()
        if app_lower in active_window:
            return True
            
        # 2. Deep check: is the process running in the background?
        try:
            import psutil
            for proc in psutil.process_iter(['name']):
                try:
                    if proc.info['name'] and app_lower in proc.info['name'].lower():
                        return True
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
        except ImportError:
            print("[Warning] psutil not installed. Cannot reliably check background processes.")
            
        return False

    def execute(self, gesture_name):
        current_time = time.time()
        mappings = self.mapping_service.get_mappings()
        active_window = self._get_active_window_title()

        # --- Context-Aware Mapping Resolution ---
        # Step 1: All active mappings for this gesture
        active_mappings = [
            m for m in mappings
            if m.get('gesture_name') == gesture_name and m.get('is_active', True) is not False
        ]

        print(f"[Executor] Executing Gesture Request: {gesture_name}. Total Mappings Found: {len(mappings)}. Active Mapped for Gesture: {len(active_mappings)}")

        if not active_mappings:
            print(f"[Executor] Blocked: No active mappings for {gesture_name}.")
            return {"status": "error", "message": "No active mapping found for this gesture."}

        # Step 2: Context Resolution Priorities
        chosen_mapping = None

        # Priority 1: App-specific mapping actively focused (e.g., "Next Track" while Spotify is open)
        for m in active_mappings:
            t_app = m.get('target_app', 'Global')
            a_type = m.get('action_type', '')
            if t_app != 'Global' and a_type != 'Open Application':
                if t_app.lower() in active_window:
                    chosen_mapping = m
                    break
        
        # Priority 2: "Open Application" mappings (target_app is the launch argument, not context restriction)
        if not chosen_mapping:
            for m in active_mappings:
                if m.get('action_type') == 'Open Application' and m.get('target_app', 'Global') != 'Global':
                    chosen_mapping = m
                    break

        # Priority 3: Fall back to Global mapping if no app-specific match
        if not chosen_mapping:
            chosen_mapping = next(
                (m for m in active_mappings if m.get('target_app', 'Global') == 'Global'),
                None
            )

        print(f"[Executor] Chosen mapping after resolution: {chosen_mapping}")

        if not chosen_mapping:
            # App-specific mapping exists but the app isn't focused — skip silently
            print(f"[Executor] Blocked: App-specific mapping exists but target not focused.")
            return {"status": "skipped", "message": "App not in focus, skipping app-specific mapping."}

        # Use detection delay configured by the user
        delay_ms = chosen_mapping.get('detection_delay_ms', 250)
        cooldown = max(0.1, delay_ms / 1000.0)

        if gesture_name in self.last_execution:
            if current_time - self.last_execution[gesture_name] < cooldown:
                return {"status": "cooldown", "message": "Cooldown active for this gesture."}

        action_type = chosen_mapping.get('action_type')
        target_app = chosen_mapping.get('target_app', 'Global')
        mapping_mode = chosen_mapping.get('mapping_mode', 'System Level')

        success = self.perform_action(action_type, target_app, mapping_mode)
        print(f"[Executor] perform_action returned {success} for action {action_type} (mode: {mapping_mode})")

        if success:
            self.last_execution[gesture_name] = current_time
            return {"status": "success", "action": action_type}
        else:
            return {"status": "error", "message": f"Failed to perform {action_type}"}

    def perform_action(self, action_type, target_app="Global", mapping_mode="System Level"):
        if not HAS_PYAUTOGUI:
            print(f"[AutomationExecutor] Cannot execute '{action_type}'. Required libraries (pyautogui) are not installed.")
            return False

        try:
            # ==========================================
            # APPLICATION LEVEL ACTIONS (App-Specific)
            # ==========================================
            if mapping_mode == "Application Level":
                # --- Browser actions ---
                if action_type == "New Tab":
                    pyautogui.hotkey('ctrl', 't')
                elif action_type == "Close Tab":
                    pyautogui.hotkey('ctrl', 'w')
                elif action_type == "Reload Page":
                    pyautogui.hotkey('ctrl', 'r')
                elif action_type == "Go Back":
                    pyautogui.hotkey('alt', 'left')
                elif action_type == "Go Forward":
                    pyautogui.hotkey('alt', 'right')
                elif action_type == "Zoom In":
                    pyautogui.hotkey('ctrl', '=')
                elif action_type == "Zoom Out":
                    pyautogui.hotkey('ctrl', '-')
                elif action_type == "Open Bookmarks":
                    pyautogui.hotkey('ctrl', 'shift', 'b')
                elif action_type == "Open History":
                    pyautogui.hotkey('ctrl', 'h')
                elif action_type == "Open Downloads":
                    pyautogui.hotkey('ctrl', 'j')
                elif action_type == "Toggle DevTools":
                    pyautogui.hotkey('f12')
                elif action_type == "Find on Page (Ctrl+F)":
                    pyautogui.hotkey('ctrl', 'f')
                elif action_type == "Open New Window":
                    pyautogui.hotkey('ctrl', 'n')

                # --- Media Player actions ---
                elif action_type == "Play / Pause":
                    pyautogui.press('playpause')
                elif action_type == "Next Track":
                    pyautogui.press('nexttrack')
                elif action_type == "Previous Track":
                    pyautogui.press('prevtrack')
                elif action_type == "Volume Up":
                    pyautogui.press('volumeup')
                elif action_type == "Volume Down":
                    pyautogui.press('volumedown')
                elif action_type == "Mute / Unmute":
                    pyautogui.press('volumemute')
                elif action_type == "Seek Forward":
                    pyautogui.hotkey('shift', 'right')
                elif action_type == "Seek Backward":
                    pyautogui.hotkey('shift', 'left')
                elif action_type == "Toggle Fullscreen":
                    pyautogui.press('f')
                elif action_type == "Toggle Shuffle":
                    pyautogui.hotkey('ctrl', 's')
                elif action_type == "Toggle Repeat":
                    pyautogui.hotkey('ctrl', 'r')

                # --- Code Editor / IDE actions ---
                elif action_type == "Save File (Ctrl+S)":
                    pyautogui.hotkey('ctrl', 's')
                elif action_type == "Undo (Ctrl+Z)":
                    pyautogui.hotkey('ctrl', 'z')
                elif action_type == "Redo (Ctrl+Y)":
                    pyautogui.hotkey('ctrl', 'y')
                elif action_type == "Find (Ctrl+F)":
                    pyautogui.hotkey('ctrl', 'f')
                elif action_type == "Replace (Ctrl+H)":
                    pyautogui.hotkey('ctrl', 'h')
                elif action_type == "Toggle Terminal":
                    pyautogui.hotkey('ctrl', '`')
                elif action_type == "Comment Line (Ctrl+/)":
                    pyautogui.hotkey('ctrl', '/')
                elif action_type == "Format Document":
                    pyautogui.hotkey('shift', 'alt', 'f')
                elif action_type == "Go to Definition":
                    pyautogui.press('f12')
                elif action_type == "Run Code":
                    pyautogui.press('f5')
                elif action_type == "Stop Execution":
                    pyautogui.hotkey('shift', 'f5')
                elif action_type == "Split Editor":
                    pyautogui.hotkey('ctrl', '\\')

                # --- File Manager actions ---
                elif action_type == "Go to Parent Folder":
                    pyautogui.hotkey('alt', 'up')
                elif action_type == "New Folder":
                    pyautogui.hotkey('ctrl', 'shift', 'n')
                elif action_type == "Rename Selected":
                    pyautogui.press('f2')
                elif action_type == "Delete Selected":
                    pyautogui.press('delete')
                elif action_type == "Copy (Ctrl+C)":
                    pyautogui.hotkey('ctrl', 'c')
                elif action_type == "Paste (Ctrl+V)":
                    pyautogui.hotkey('ctrl', 'v')
                elif action_type == "Refresh View":
                    pyautogui.press('f5')
                elif action_type == "Toggle Hidden Files":
                    pyautogui.hotkey('ctrl', 'h')
                elif action_type == "Select All (Ctrl+A)":
                    pyautogui.hotkey('ctrl', 'a')

                # --- Video Conferencing actions ---
                elif action_type == "Mute / Unmute Mic":
                    pyautogui.hotkey('ctrl', 'd')
                elif action_type == "Toggle Camera":
                    pyautogui.hotkey('ctrl', 'e')
                elif action_type == "Share Screen":
                    pyautogui.hotkey('ctrl', 'shift', 's')
                elif action_type == "Raise Hand":
                    pyautogui.hotkey('alt', 'y')
                elif action_type == "End Call":
                    pyautogui.hotkey('alt', 'f4')
                elif action_type == "Open Chat":
                    pyautogui.hotkey('ctrl', 'shift', 'h')
                elif action_type == "Toggle Participants List":
                    pyautogui.hotkey('ctrl', 'shift', 'p')
                elif action_type == "Record Meeting":
                    pyautogui.hotkey('ctrl', 'shift', 'r')
                elif action_type == "Leave Meeting":
                    pyautogui.hotkey('ctrl', 'w')

                # --- Generic fallback actions ---
                elif action_type == "Save (Ctrl+S)":
                    pyautogui.hotkey('ctrl', 's')
                elif action_type == "Close Window (Alt+F4)":
                    pyautogui.hotkey('alt', 'f4')
                elif action_type == "Minimize Window":
                    pyautogui.hotkey('win', 'down')
                elif action_type == "Maximize Window":
                    pyautogui.hotkey('win', 'up')
                elif action_type == "Switch Window (Alt+Tab)":
                    pyautogui.hotkey('alt', 'tab')
                elif action_type == "Scroll Up":
                    pyautogui.scroll(500)
                elif action_type == "Scroll Down":
                    pyautogui.scroll(-500)
                else:
                    print(f"[AutomationExecutor] Unhandled app action: {action_type}")
                    return False
                return True

            # ==========================================
            # SYSTEM LEVEL ACTIONS (System Specific)
            # ==========================================
            
            # --- Mouse Control ---
            if action_type == "Left click":
                pyautogui.click()
            elif action_type == "Right click":
                pyautogui.rightClick()
            elif action_type == "Double-click":
                pyautogui.doubleClick()
            elif action_type == "Middle click":
                pyautogui.middleClick()
            elif action_type == "Drag and Drop":
                # Toggle logic: First gesture grabs, second gesture releases
                if self.drag_active:
                    pyautogui.mouseUp()
                    self.drag_active = False
                else:
                    pyautogui.mouseDown()
                    self.drag_active = True
                
            # --- Media Control ---
            elif action_type == "Play / Pause":
                pyautogui.press("playpause")
            elif action_type == "Next Track":
                pyautogui.press("nexttrack")
            elif action_type == "Previous Track":
                pyautogui.press("prevtrack")
            elif action_type == "Volume Up":
                pyautogui.press("volumeup")
            elif action_type == "Volume Down":
                pyautogui.press("volumedown")
            elif action_type == "Mute":
                pyautogui.press("volumemute")

            # --- Scrolling And Navigation ---
            elif action_type == "Scroll Up":
                pyautogui.scroll(500)
            elif action_type == "Scroll Down":
                pyautogui.scroll(-500)
            elif action_type == "Scroll Left":
                pyautogui.hscroll(-500)
            elif action_type == "Scroll Right":
                pyautogui.hscroll(500)
            elif action_type == "Page Up":
                pyautogui.press("pageup")
            elif action_type == "Page Down":
                pyautogui.press("pagedown")
            elif action_type == "Browser Back":
                pyautogui.press("browserback")
            elif action_type == "Browser Forward":
                pyautogui.press("browserforward")

            # --- Keyboard Shortcuts ---
            elif action_type == "Copy (Ctrl+C)":
                pyautogui.hotkey('ctrl', 'c')
            elif action_type == "Paste (Ctrl+V)":
                pyautogui.hotkey('ctrl', 'v')
            elif action_type == "Cut (Ctrl+X)":
                pyautogui.hotkey('ctrl', 'x')
            elif action_type == "Undo (Ctrl+Z)":
                pyautogui.hotkey('ctrl', 'z')
            elif action_type == "Select All (Ctrl+A)":
                pyautogui.hotkey('ctrl', 'a')
            elif action_type == "Enter":
                pyautogui.press('enter')
            elif action_type == "Escape":
                pyautogui.press('escape')

            # --- Application Control ---
            elif action_type == "Open Application":
                if target_app and target_app != "Global":
                    if self._is_app_running(target_app):
                        print(f"[AutomationExecutor] {target_app} is already running. Skipping launch.")
                        return True
                    
                    # Use PyAutoGUI to search and launch via the Start Menu
                    pyautogui.press('win')
                    time.sleep(0.5)
                    pyautogui.write(target_app)
                    time.sleep(0.5)
                    pyautogui.press('enter')
                else:
                    pyautogui.press('win')
            elif action_type == "Close Application":
                pyautogui.hotkey('alt', 'f4')
            elif action_type == "Minimize Window":
                pyautogui.hotkey('win', 'down')
            elif action_type == "Maximize Window":
                pyautogui.hotkey('win', 'up')
            elif action_type == "Switch Window (Alt+Tab)":
                pyautogui.hotkey('alt', 'tab')
            elif action_type == "Task View (Win+Tab)":
                pyautogui.hotkey('win', 'tab')
            elif action_type == "Snap Layout (Win+Z)":
                pyautogui.hotkey('win', 'z')
            
            # --- Application Launchers ---
            elif action_type == "Open Calculator":
                if not self._is_app_running("calc"):
                    subprocess.Popen("calc.exe", shell=True) if sys.platform == "win32" else None
            elif action_type == "Open Notepad":
                if not self._is_app_running("notepad"):
                    subprocess.Popen("notepad.exe", shell=True) if sys.platform == "win32" else None
            elif action_type == "Windows Settings":
                if not self._is_app_running("settings"):
                    subprocess.Popen("start ms-settings:", shell=True) if sys.platform == "win32" else None
            elif action_type == "Command Prompt":
                if not self._is_app_running("cmd"):
                    subprocess.Popen("start cmd", shell=True) if sys.platform == "win32" else None
            elif action_type == "File Explorer":
                if not self._is_app_running("explorer"):
                    pyautogui.hotkey('win', 'e')

            # --- Screenshot & Screen Recording ---
            elif action_type == "Capture Full Screen":
                pyautogui.press("printscreen")
            elif action_type == "Capture Active Window":
                pyautogui.hotkey("alt", "printscreen")
            elif action_type == "Snipping Tool":
                if sys.platform == 'win32':
                    subprocess.Popen(['explorer.exe', 'ms-screenclip:'], shell=False)
                elif sys.platform == 'darwin':
                    subprocess.Popen(['screencapture', '-i', '-c'])
                else:
                    subprocess.Popen(['gnome-screenshot', '-i'])
            elif action_type == "Start/Stop Recording":
                if sys.platform == 'win32':
                    pyautogui.hotkey("win", "alt", "r")
                else:
                    print("[AutomationExecutor] Screen recording shortcut is Windows-only.")

            # --- System Controls ---
            elif action_type == "Lock Screen":
                if sys.platform == 'win32':
                    subprocess.run(['rundll32.exe', 'user32.dll,LockWorkStation'], shell=False)
                elif sys.platform == 'darwin':
                    subprocess.run(['pmset', 'displaysleepnow'])
                else:
                    subprocess.run(['loginctl', 'lock-session'])
            elif action_type == "Sleep":
                if sys.platform == 'win32':
                    subprocess.run(['rundll32.exe', 'powrprof.dll,SetSuspendState', '0,1,0'], shell=False)
                elif sys.platform == 'darwin':
                    subprocess.run(['pmset', 'sleepnow'])
                else:
                    subprocess.run(['systemctl', 'suspend'])
            elif action_type == "Open Task Manager":
                pyautogui.hotkey("ctrl", "shift", "esc")
            elif action_type == "Show Desktop (Win+D)":
                pyautogui.hotkey("win", "d")
            elif action_type == "Open Action Center":
                pyautogui.hotkey("win", "a")
                
            # --- PowerPoint Control ---
            elif action_type == "Start Presentation (F5)":
                pyautogui.press("f5")
            elif action_type == "End Presentation (Esc)":
                pyautogui.press("escape")
            elif action_type == "Next Slide":
                pyautogui.press("right")
            elif action_type == "Previous Slide":
                pyautogui.press("left")
            elif action_type == "Blank Screen (B)":
                pyautogui.press("b")

            else:
                print(f"[AutomationExecutor] Unhandled action: {action_type}")
                return False
                
            print(f"[AutomationExecutor] Executed action: {action_type}")
            return True
        except Exception as e:
            print(f"[AutomationExecutor] Error executing {action_type}: {str(e)}")
            return False