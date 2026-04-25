import cv2
import mediapipe as mp
import threading
import base64
import math
import time
import numpy as np
try:
    import pyautogui
    HAS_PYAUTOGUI = True
    # SAFETY: Keep failsafe enabled (moving mouse to corner aborts pyautogui).
    pyautogui.FAILSAFE = True
except ImportError:
    HAS_PYAUTOGUI = False

try:
    from webview.errors import JavascriptException
except ImportError:
    JavascriptException = Exception  # fallback if webview not installed

class CameraService:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        """Singleton pattern: ensures only one camera service exists."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(CameraService, cls).__new__(cls)
                cls._instance._init_camera_service()
        return cls._instance

    def _init_camera_service(self):
        """Internal initialization logic."""
        self.is_scanning = False
        self.current_frame = None
        self.hand_detected = False
        self.thread = None
        self.camera_index = 0  # Configurable — users with multiple cameras can change this
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            model_complexity=1,  # Enhanced precision for noisy images
            min_detection_confidence=0.7, 
            min_tracking_confidence=0.7
        )
        self.mp_draw = mp.solutions.drawing_utils

        self.pending_gesture = None
        self.stability_count = 0
        self.current_gesture = None
        # 6 frames of stability prevents gesture bleed/conflicts
        self.stability_frames = 6

        # Persist mouse tracking state on boot
        try:
            import os
            import json
            settings_path = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'app_settings.json')
            with open(settings_path, 'r') as f:
                self.mouse_tracking_enabled = json.load(f).get('mouse_tracking_enabled', False)
        except Exception:
            self.mouse_tracking_enabled = False

        self.motion_buffer = []
        self.is_recording_motion = False
        self.recorded_motion = []
        from engine.detection.motion_engine import MotionEngine
        self.motion_engine = MotionEngine()

    def set_camera_index(self, index):
        """Switch the active camera device by index (0 = default, 1 = second camera, etc.)."""
        try:
            self.camera_index = int(index)
            return {"status": "success", "camera_index": self.camera_index}
        except (ValueError, TypeError) as e:
            return {"status": "error", "message": f"Invalid camera index: {e}"}

    def start(self, frame_callback, predictor=None, executor=None):
        with self._lock:
            if self.thread and self.thread.is_alive():
                return
            
            self.is_scanning = True
            self.pending_gesture = None
            self.stability_count = 0
            self.current_gesture = None
            
            self.thread = threading.Thread(target=self._run_loop, args=(frame_callback, predictor, executor), daemon=True)
            self.thread.start()

    def stop(self):
        self.is_scanning = False

    @staticmethod
    def _is_index_only(landmarks):
        """
        Returns True ONLY if the index finger is fully extended and all other
        fingers (middle, ring, pinky) are folded down.
        Uses raw MediaPipe y-coordinates: a finger tip below its PIP joint = folded.
        Landmark indices (MediaPipe hand model):
          Thumb:  tip=4, IP=3, MCP=2
          Index:  tip=8, PIP=6
          Middle: tip=12, PIP=10
          Ring:   tip=16, PIP=14
          Pinky:  tip=20, PIP=18
        NOTE: y increases downward in image coordinates.
        """
        try:
            # Index finger must be UP: tip ABOVE PIP (smaller y)
            index_up = landmarks[8].y < landmarks[6].y
            # All other fingers must be DOWN: tip BELOW their PIP (larger y)
            middle_down = landmarks[12].y > landmarks[10].y
            ring_down   = landmarks[16].y > landmarks[14].y
            pinky_down  = landmarks[20].y > landmarks[18].y
            return index_up and middle_down and ring_down and pinky_down
        except (IndexError, AttributeError):
            return False

    def _run_loop(self, callback, predictor=None, executor=None):
        from engine.detection.predictor import ModelNotReadyError
        cap = cv2.VideoCapture(self.camera_index)  # Use configured index, not hardcoded 0
        frame_counter = 0
        # 30 fps cap to prevent flooding the PyWebView JS bridge
        MIN_FRAME_INTERVAL = 1.0 / 30.0
        last_push_time = 0.0

        while self.is_scanning:
            success, frame = cap.read()
            if not success or not self.is_scanning: 
                break
            
            frame_counter += 1
            frame = cv2.flip(frame, 1)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self.hands.process(rgb_frame)
            confidence = 0
            self.hand_detected = False
            candidate = None
            is_motion_candidate = False
            
            hand_crop = None
            if results.multi_hand_landmarks:
                self.hand_detected = True
                if results.multi_handedness:
                    confidence = int(results.multi_handedness[0].classification[0].score * 100)
                
                # Extract first hand's landmarks for accurate mathematical recognition
                first_hand = results.multi_hand_landmarks[0]
                
                for handLms in results.multi_hand_landmarks:
                    self.mp_draw.draw_landmarks(
                        frame, 
                        handLms, 
                        self.mp_hands.HAND_CONNECTIONS,
                        self.mp_draw.DrawingSpec(color=(0, 255, 0), thickness=2, circle_radius=2),
                        self.mp_draw.DrawingSpec(color=(0, 0, 255), thickness=2)
                    )

                # 1. RECOGNITION PIPELINE
                if predictor and first_hand and first_hand.landmark:
                    try:
                        gesture_name, pred_conf = predictor.predict_from_landmarks(first_hand.landmark)
                        
                        # Trust the Predictor's internal confidence threshold check. 
                        # Only reject if it definitively returns "Unknown"
                        if gesture_name != "Unknown":
                            candidate = gesture_name
                    except ModelNotReadyError as e:
                        if not getattr(self, '_model_error_reported', False):
                            print(f"[CameraService] {e}")
                            self._model_error_reported = True

                # --- MOTION TRACKING PIPELINE (Centroid Trajectory) ---
                if first_hand and first_hand.landmark:
                    # Track roughly the center of the hand (e.g. wrist or middle finger MCP)
                    centroid_x = sum(lm.x for lm in first_hand.landmark) / len(first_hand.landmark)
                    centroid_y = sum(lm.y for lm in first_hand.landmark) / len(first_hand.landmark)
                    
                    if self.is_recording_motion:
                        self.recorded_motion.append((centroid_x, centroid_y))
                    else:
                        self.motion_buffer.append((centroid_x, centroid_y))
                        if len(self.motion_buffer) > 30: # 1-second rolling buffer
                            self.motion_buffer.pop(0)
                        
                        # Only query the motion engine if we're actively automating (executor exists)
                        # or if we want motion to override static
                        m_gesture, m_conf = self.motion_engine.detect_motion(list(self.motion_buffer))
                        if m_conf > 70:  # Strong motion matched
                            candidate = m_gesture
                            pred_conf = m_conf / 100.0
                            is_motion_candidate = True
                            
                # 1.5 MOUSE TRACKING PIPELINE
                # Only tracks if index finger is isolated (landmark geometry, not gesture name)
                if getattr(self, 'mouse_tracking_enabled', False) and HAS_PYAUTOGUI:
                    if self._is_index_only(first_hand.landmark):
                        lm_index_tip = first_hand.landmark[8]
                        lm_thumb_tip = first_hand.landmark[4]
                        screen_w, screen_h = pyautogui.size()
                        
                        # Dynamic mapping with np.interp bounds
                        margin = 0.1
                        target_x = int(np.interp(lm_index_tip.x, (margin, 1-margin), (0, screen_w)))
                        target_y = int(np.interp(lm_index_tip.y, (margin, 1-margin), (0, screen_h)))
                        
                        # Smooth movements
                        if not hasattr(self, 'smooth_x'):
                            self.smooth_x, self.smooth_y = target_x, target_y
                            self.mouse_active = False
                        
                        alpha = 0.5
                        self.smooth_x = int(alpha * target_x + (1 - alpha) * self.smooth_x)
                        self.smooth_y = int(alpha * target_y + (1 - alpha) * self.smooth_y)
                        
                        try:
                            pyautogui.moveTo(self.smooth_x, self.smooth_y)
                        except Exception:
                            pass
                            
                        # Pinch detection: index-thumb close = hold mouse button (Drag-and-Drop)
                        dist = math.sqrt((lm_index_tip.x - lm_thumb_tip.x)**2 + (lm_index_tip.y - lm_thumb_tip.y)**2)
                        click_threshold = 0.05
                        
                        if dist < click_threshold:
                            if not getattr(self, 'mouse_active', False):
                                try:
                                    pyautogui.mouseDown()
                                    self.mouse_active = True
                                except Exception:
                                    pass
                        else:
                            if getattr(self, 'mouse_active', False):
                                try:
                                    pyautogui.mouseUp()
                                    self.mouse_active = False
                                except Exception:
                                    pass
                    else:
                        # Non-index-finger gesture: release any held button so cursor doesn't stick
                        if getattr(self, 'mouse_active', False):
                            try:
                                pyautogui.mouseUp()
                                self.mouse_active = False
                            except Exception:
                                pass

            # 2. STABILITY PIPELINE
            if is_motion_candidate:
                # Fast path for motion sequences: temporal paths are naturally stable
                self.current_gesture = candidate
                self.pending_gesture = candidate
                self.stability_count = self.stability_frames
                self.motion_buffer = [] # clear buffer to avoid immediate double-fires
            else:
                # Standard path for Static Poses
                if candidate:
                    if candidate == self.pending_gesture:
                        self.stability_count += 1
                    else:
                        self.pending_gesture = candidate
                        self.stability_count = 0
                else:
                    self.pending_gesture = None
                    self.stability_count = 0

                # If stable enough, lock it in
                if self.stability_count >= self.stability_frames:
                    self.current_gesture = self.pending_gesture
                else:
                    self.current_gesture = None

            # 3. MAPPING & EXECUTION PIPELINE
            if self.current_gesture and executor:
                # Trigger action exactly once on state change
                if getattr(self, 'last_executed_gesture', None) != self.current_gesture:
                    mappings = executor.mapping_service.get_mappings()
                    
                    # Only execute if the gesture is actively mapped in the database
                    is_mapped = any(
                        m.get('gesture_name') == self.current_gesture and m.get('is_active', True)
                        for m in mappings
                    )
                    
                    if is_mapped:
                        executor.execute(self.current_gesture)
                        self.last_executed_gesture = self.current_gesture
            elif not self.current_gesture:
                self.last_executed_gesture = None

            if hand_crop is not None and hand_crop.size != 0:
                self.current_frame = hand_crop.copy()
            else:
                self.current_frame = frame.copy()

            # Gate frame pushes to max 30fps to avoid saturating the PyWebView JS bridge.
            # Rapid evaluate_js calls cause promise UID races (JavascriptException).
            now = time.time()
            if now - last_push_time >= MIN_FRAME_INTERVAL:
                last_push_time = now
                _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
                gesture_confidence = int(pred_conf * 100) if 'pred_conf' in locals() else 0
                try:
                    callback(base64.b64encode(buffer).decode('utf-8'), confidence, gesture_confidence)
                except JavascriptException:
                    pass  # Bridge UID mismatch — transient, safe to ignore
                except Exception:
                    pass
        
        cap.release()