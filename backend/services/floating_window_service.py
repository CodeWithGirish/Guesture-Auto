import os
import threading
import webview


class _FloatWindowAPI:
    """Minimal JS API exposed only to the floating window for close capability."""
    def __init__(self, parent_service):
        self._svc = parent_service

    def close(self):
        """Called from the float window's close button.
        Schedules destruction asynchronously to avoid destroying the window
        from within its own API call context (which would crash PyWebView).
        """
        threading.Timer(0.05, self._svc.close).start()
        return {"status": "success"}


class FloatingWindowService:
    """Manages a lightweight always-on-top floating camera preview window.

    Design decisions for zero-lag operation:
    - Window creation uses absolute file:// paths (prevents 404 on relative pathing)
    - Frame pushes are fire-and-forget with exception swallowing
    - The float window gets a minimal JS payload (no JSON parsing overhead)
    - Frames are pushed at half the main window rate (15fps vs 30fps)
    - Thread-safe window lifecycle via reentrant lock
    """

    def __init__(self):
        import time
        self.window = None
        self._lock = threading.Lock()
        self._push_lock = threading.Lock()
        self._push_lock_time = 0
        self._frame_skip = 0
        self._root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    def toggle(self):
        """Thread-safe toggle: opens the window if closed, closes it if open."""
        with self._lock:
            if self.window:
                self._destroy_window()
                return {"status": "success", "action": "closed"}
            else:
                self._create_window()
                return {"status": "success", "action": "opened"}

    def _create_window(self):
        """Creates the floating window with absolute path and its own JS API."""
        html_path = os.path.join(
            self._root, 'frontend', 'user_app',
            '2_Gusture Module', 'float_camera.html'
        )

        float_api = _FloatWindowAPI(self)

        self.window = webview.create_window(
            'GestureAuto — Live',
            url=f'file://{html_path}',
            js_api=float_api,
            width=320,
            height=240,
            on_top=True,
            frameless=True,
            easy_drag=True,
            resizable=False
        )
        self.window.events.closed += self._on_window_closed
        self._frame_skip = 0

    def _destroy_window(self):
        """Safely destroys the window and resets state."""
        if self.window:
            try:
                self.window.destroy()
            except Exception:
                pass
            self.window = None

    def _on_window_closed(self):
        """Callback fired if the OS or PyWebView closes the window externally."""
        # Don't acquire lock here — this can be called from the GUI thread
        # during shutdown and could deadlock with toggle()
        self.window = None

    def push_frame(self, img_b64, gesture_name='', confidence=0):
        """Pushes a frame to the float window at half the main frame rate.

        This is called from the camera thread at ~30fps; the frame_skip counter
        ensures only every 2nd frame is actually dispatched to the float window,
        reducing IPC overhead to ~15fps — more than enough for a 320x240 preview.
        """
        win = self.window
        if not win:
            return

        # Skip every other frame → 15fps to the float window
        self._frame_skip += 1
        if self._frame_skip % 2 != 0:
            return

        # Minimal JS payload: no JSON.parse, direct function call
        # Escaping gesture_name to prevent JS injection from gesture names with quotes
        safe_name = (gesture_name or '').replace("'", "\\'").replace("\\", "\\\\")
        js = (
            f"if(typeof updateFloatFrame!=='undefined')"
            f"updateFloatFrame('data:image/jpeg;base64,{img_b64}','{safe_name}',{confidence});"
        )
        import time
        now = time.time()
        # If the lock has been held for >1 second, assume evaluate_js is permanently stuck due to page navigation IPC drop!
        if self._push_lock_time > 0 and now - self._push_lock_time > 1.0:
            self._push_lock = threading.Lock()  # Force replace the hung lock
            self._push_lock_time = 0

        if self._push_lock.acquire(blocking=False):
            self._push_lock_time = time.time()
            def _push():
                try:
                    win.evaluate_js(js)
                except Exception:
                    pass  # Window may be closing — fire-and-forget
                finally:
                    try:
                        self._push_lock.release()
                    except RuntimeError:
                        pass # Lock might have been replaced
                    self._push_lock_time = 0
            threading.Thread(target=_push, daemon=True).start()

    def close(self):
        """Public close method for lifecycle cleanup (stop_scan, shutdown)."""
        with self._lock:
            self._destroy_window()

    @property
    def is_open(self):
        """Returns True if the float window is currently open."""
        return self.window is not None