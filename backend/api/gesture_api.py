import webview
import json
import base64
import cv2
import os
import time
import threading

from ..services.camera_service import CameraService
from ..services.storage_service import StorageService
from ..services.floating_window_service import FloatingWindowService
from ..services.search_service import SearchService
# CRITICAL FIX: Removed global import of AugmentationEngine to prevent Circular Import crashing

class GestureAutoAPI:
    def __init__(self):
        self.camera = CameraService()
        self.storage = StorageService()
        self.float_service = FloatingWindowService()
        self.search_service = SearchService()
        self.session_frames = {}
        self.frame_counter = 0
        self.editing_gesture = None
        
        # Concurrency & Tracking variables
        self.current_engine = None
        self.batch_result = None
        self.is_processing = False
        self.thumbnail_cache = {}
        # Lock to prevent concurrent gallery summary calls from racing in the PyWebView JS bridge
        self._summary_lock = threading.Lock()
        # Lock to prevent concurrent augmented-images calls racing the JS bridge
        self._images_lock = threading.Lock()

    def toggle_float_window(self):
        """Toggles the floating camera preview window on/off."""
        # Check if the system is started and the background thread is actively running
        if not self.camera.is_scanning or not getattr(self.camera.thread, 'is_alive', lambda: False)():
            return {"status": "error", "message": "Camera is currently inactive or being used by another application. Please start the system."}
        
        # Verify OpenCV actually established a connection and pulled a frame
        if getattr(self.camera, 'current_frame', None) is None:
            return {"status": "error", "message": "Camera feed is blocked or used by another application."}
            
        return self.float_service.toggle()

    def start_scan(self):
        if not self.camera.is_scanning:
            self.camera.start(self._ui_frame_callback) 
        return {"status": "success"} 

    # CRITICAL FIX: Removed the duplicate start_automation function that was underneath this one.
    def start_automation(self):
        if not self.camera.is_scanning:
            def _init_and_start():
                try:
                    from engine.detection.predictor import GesturePredictor
                    from engine.automation.executor import AutomationExecutor
                    # CRITICAL FIX 2: This loads the TF model, which takes seconds. 
                    # Doing it in a background thread prevents PyWebView from freezing.
                    predictor = GesturePredictor()
                    executor = AutomationExecutor()
                    self.camera.start(self._ui_frame_callback, predictor=predictor, executor=executor)
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    print(f"Error starting automation: {e}")
            
            # Start the initialization process seamlessly in the background
            threading.Thread(target=_init_and_start, daemon=True).start()
            return {"status": "success"}
        return {"status": "success"}

    def stop_scan(self):
        self.camera.stop()
        self.float_service.close()
        return {"status": "success"}

    def _ui_frame_callback(self, img_b64, confidence, gesture_confidence=0):
        """
        Pushes a video frame and confidence metrics to the active windows.

        Architecture:
        - Main window (windows[0]) gets full payload with metrics via a single
          evaluate_js call (prevents PyWebView promise UID race condition).
        - Float window gets a lightweight frame-only push at half frame rate
          via FloatingWindowService.push_frame() to prevent degrading main app.
        - The base64 data is stored in a JS variable and referenced once,
          halving the IPC payload size vs embedding it inline twice.
        """
        if not webview.windows:
            return
        try:
            from webview.errors import JavascriptException
        except ImportError:
            JavascriptException = Exception

        # Single-variable JS: base64 data stored once, referenced by both branches.
        # This halves the IPC payload vs the old approach of embedding it inline twice.
        is_float = self.float_service.is_open
        js = f"""(function(){{
        var f='data:image/jpeg;base64,{img_b64}';
        var isFloat = {'true' if is_float else 'false'};
        if(typeof updateScanFrame!=='undefined')updateScanFrame({{frame:f,confidence:{confidence},gesture_confidence:{gesture_confidence}}});
        else if(typeof updateFrame!=='undefined'){{updateFrame(f, isFloat);if(typeof updateGestureMetrics!=='undefined')updateGestureMetrics({confidence},{gesture_confidence});}}
        }})();"""

        # Push to main window non-blocking to prevent freezing during navigation
        if not hasattr(self, '_main_ui_lock'):
            self._main_ui_lock = __import__('threading').Lock()
            self._main_ui_lock_time = 0
            
        now = __import__('time').time()
        # If the lock has been held for >1 second, recreate it to recover from PyWebView evaluate_js IPC drop
        if getattr(self, '_main_ui_lock_time', 0) > 0 and now - self._main_ui_lock_time > 1.0:
            self._main_ui_lock = __import__('threading').Lock()
            self._main_ui_lock_time = 0

        if self._main_ui_lock.acquire(blocking=False):
            self._main_ui_lock_time = now
            def _push_main():
                try:
                    if webview.windows:
                        webview.windows[0].evaluate_js(js)
                except Exception:
                    pass  # Transient bridge UID mismatch or window closing
                finally:
                    try:
                        self._main_ui_lock.release()
                    except RuntimeError:
                        pass
                    self._main_ui_lock_time = 0
            __import__('threading').Thread(target=_push_main, daemon=True).start()

        # Push to float window via dedicated lightweight path (15fps, no JSON)
        gesture_name = getattr(self.camera, 'current_gesture', None) or ''
        self.float_service.push_frame(img_b64, gesture_name, gesture_confidence)

    def get_current_session(self):
        data = {"gesture_name": self.editing_gesture or "", "frames": []}
        if not self.editing_gesture:
            return data
        self.session_frames.clear()
        self.frame_counter = 0
        folder_path = os.path.join(self.storage.dataset_dir, self.editing_gesture)
        if os.path.exists(folder_path):
            images = sorted([f for f in os.listdir(folder_path) if f.endswith(('.jpg', '.png', '.jpeg'))])
            for img_name in images:
                frame = cv2.imread(os.path.join(folder_path, img_name))
                if frame is not None:
                    tid = f"frame_{self.frame_counter}"
                    self.session_frames[tid] = frame
                    _, buf = cv2.imencode('.jpg', frame)
                    img_b64 = base64.b64encode(buf).decode('utf-8')
                    data["frames"].append({"temp_id": tid, "base64": f"data:image/jpeg;base64,{img_b64}"})
                    self.frame_counter += 1
        return data

    def capture_image(self):
        if not self.camera.is_scanning or self.camera.current_frame is None:
            return {"status": "error", "message": "Camera not active."}
        
        if not self.camera.hand_detected:
            return {
                "status": "error", 
                "message": "No hand detected! Please position your hand in front of the camera."
            }

        tid = f"frame_{self.frame_counter}"
        self.session_frames[tid] = self.camera.current_frame.copy()
        self.frame_counter += 1
        
        _, buf = cv2.imencode('.jpg', self.camera.current_frame)
        img_b64 = base64.b64encode(buf).decode('utf-8')
        data = {"base64": f"data:image/jpeg;base64,{img_b64}", "temp_id": tid}
        
        if webview.windows:
            webview.windows[0].evaluate_js(f"addScannedImage({json.dumps(data)})")
            
        return {"status": "success"}

    def clear_session(self):
        self.session_frames.clear()
        self.frame_counter = 0
        return {"status": "success"}

    def delete_images(self, temp_ids):
        for tid in temp_ids:
            if tid in self.session_frames:
                del self.session_frames[tid]
        return {"status": "success"}

    def save_session(self, gesture_name):
        count = self.storage.save_session_to_disk(gesture_name, self.session_frames)
        self.session_frames.clear()
        self.frame_counter = 0
        self.editing_gesture = None
        self.camera.stop()
        if webview.windows:
            redirection_script = "window.location.href = '1_Saved Guesture Screen.html';"
            webview.windows[0].evaluate_js(redirection_script)
        return {"status": "success", "message": f"Saved {count} images and redirecting..."}

    def start_motion_scan(self):
        """Prepares the camera to record a temporal 30-frame hand trajectory."""
        self.camera.recorded_motion = []
        self.camera.is_recording_motion = True
        return {"status": "success"}

    def save_motion_session(self, gesture_name):
        """Takes the recorded sequence trajectory and saves it to the DTW templates."""
        self.camera.is_recording_motion = False
        if not self.camera.recorded_motion:
            return {"status": "error", "message": "No motion data was captured."}
            
        result = self.camera.motion_engine.save_motion(gesture_name, self.camera.recorded_motion)
        self.camera.recorded_motion = []
        # DO NOT stop the camera or redirect here, so the user can see the alert and continue scanning.
        return result

    def get_saved_gestures(self):
        return self.storage.get_all_gestures()

    def get_gesture_images(self, gesture_name):
        return self.storage.get_gesture_sample_images(gesture_name)

    def delete_saved_images(self, gesture_name, filenames):
        count, removed = self.storage.delete_specific_images(gesture_name, filenames)
        return {"status": "success", "message": f"Deleted {count} images.", "folder_deleted": removed}
    
    def delete_gesture(self, name):
        from backend.services.action_mapping_service import ActionMappingService
        mapping_service = ActionMappingService()
        mappings = mapping_service.get_mappings()
        
        is_mapped = any(m.get('gesture_name') == name for m in mappings)
        if is_mapped:
            return {"status": "error", "message": f"Cannot delete: Gesture '{name}' is actively mapped to an action. Please remove the mapping first."}

        if self.storage.delete_gesture_folder(name):
            return {"status": "success"}
        return {"status": "error"}

    def edit_gesture(self, name):
        self.editing_gesture = name
        return {"status": "success"}

    def set_camera_index(self, index):
        """Switch the active camera device. Delegates to CameraService."""
        return self.camera.set_camera_index(index)

    def search_items(self, category, query):
        data = []
        key = "name"
        if category == "gestures":
            data = self.storage.get_all_gestures() 
        filtered = self.search_service.filter_data(query, data, key) 
        return {"status": "success", "results": filtered}
    
    def get_gesture_summary(self, name):
        gestures = self.storage.get_all_gestures() 
        for g in gestures:
            if g['name'] == name:
                return {"status": "success", "count": g['count']}
        return {"status": "error", "count": 0}

    def save_augmentation_params(self, params):
        success = self.storage.save_augmentation_config(params)
        if success:
            return {"status": "success", "message": "Parameters saved for model training."}
        return {"status": "error", "message": "Failed to save parameters."}
    
    def get_augmentation_params(self):
        data = self.storage.get_augmentation_config()
        return {"status": "success", "data": data}

    def start_augmentation_batch(self, gesture_name, target_count, use_params=True):
        if self.is_processing:
            return {"status": "error", "message": "A batch is already running."}
            
        try:
            # Inline import prevents circular dependency loops
            from engine.augumentation.processor import AugmentationEngine
            self.current_engine = AugmentationEngine()
            params = self.storage.get_augmentation_config()
            
            self.is_processing = True
            self.batch_result = None

            def background_worker():
                try:
                    res = self.current_engine.run_batch(gesture_name, params, int(target_count), use_params)
                    self.batch_result = res
                except Exception as e:
                    self.batch_result = {"status": "error", "message": str(e)}
                finally:
                    self.is_processing = False
                    self.current_engine = None

            thread = threading.Thread(target=background_worker, daemon=True)
            thread.start()
            
            return {"status": "started", "message": "Processing started in background."}
            
        except Exception as e:
            self.is_processing = False
            self.current_engine = None
            return {"status": "error", "message": str(e)}

    def get_batch_progress(self):
        if self.is_processing and self.current_engine:
            return {
                "status": "processing",
                "processed": self.current_engine.processed_count,
                "target": self.current_engine.target_count
            }
        elif self.batch_result is not None:
            res = self.batch_result
            self.batch_result = None 
            return res
            
        return {"status": "idle"}

    def abort_augmentation_batch(self):
        if self.is_processing and self.current_engine:
            self.current_engine.abort()
            return {"status": "success", "message": "Abort signal sent."}
        return {"status": "error", "message": "No active batch to abort."}
    
    def get_augmentation_kpis(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        aug_dir = os.path.join(base_dir, 'data', 'augumented_data')
        sample_dir = os.path.join(base_dir, 'data', 'sample_images')

        total_images = 0
        for directory in [aug_dir, sample_dir]:
            if os.path.exists(directory):
                for root, _, files in os.walk(directory):
                    total_images += len([f for f in files if f.endswith(('.jpg', '.png', '.jpeg'))])

        try:
            import psutil
            mem = psutil.virtual_memory()
            used_gb = round(mem.used / (1024**3), 1)
            total_gb = round(mem.total / (1024**3), 1)
            memory_str = f"{used_gb} GB / {total_gb} GB"
        except ImportError:
            memory_str = "N/A"

        last_run_time = 0
        proc_speed = 0
        
        if os.path.exists(aug_dir):
            for folder in os.listdir(aug_dir):
                settings_path = os.path.join(aug_dir, folder, 'last_run_settings.json')
                if os.path.exists(settings_path):
                    try:
                        with open(settings_path, 'r') as f:
                            data = json.load(f)
                            if data.get('timestamp', 0) > last_run_time:
                                last_run_time = data.get('timestamp', 0)
                                proc_speed = data.get('proc_speed_ms', 0)
                    except: pass

        if last_run_time == 0:
            last_run_str = "Never"
        else:
            diff = time.time() - last_run_time
            if diff < 60: last_run_str = "Just now"
            elif diff < 3600: last_run_str = f"{int(diff//60)}m ago"
            elif diff < 86400: last_run_str = f"{int(diff//3600)}h ago"
            else: last_run_str = f"{int(diff//86400)}d ago"

        return {
            "status": "success",
            "dataset_size": f"{total_images:,}",
            "proc_speed": f"{int(proc_speed)}",
            "memory": memory_str,
            "last_run": last_run_str
        }
    
    def get_augmented_images(self, gesture_name, limit=200):
        # Non-blocking guard: skip if a previous heavy image-encode call is still running.
        # Without this, simultaneous polled calls register two JS bridge callback UIDs
        # for the same function, causing the '...is not a function' JavascriptException.
        if not self._images_lock.acquire(blocking=False):
            return {"status": "busy", "images": []}
        try:
            return self._get_augmented_images_impl(gesture_name, limit)
        finally:
            self._images_lock.release()

    def _get_augmented_images_impl(self, gesture_name, limit=200):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        aug_dir = os.path.join(base_dir, 'Data', 'augumented_data', gesture_name)
        images_data = []

        if os.path.exists(aug_dir):
            files = [f for f in os.listdir(aug_dir) if f.lower().endswith(('.jpg', '.png', '.jpeg'))]
            
            safe_files = []
            for f in files:
                file_path = os.path.join(aug_dir, f)
                try:
                    mtime = os.path.getmtime(file_path)
                    safe_files.append((f, mtime))
                except OSError:
                    pass 
            
            safe_files.sort(key=lambda x: x[1], reverse=True)
            sorted_files = [item[0] for item in safe_files]

            for img_name in sorted_files[:limit]:
                img_path = os.path.join(aug_dir, img_name)
                try:
                    if img_path in self.thumbnail_cache:
                        encoded = self.thumbnail_cache[img_path]
                    else:
                        img = cv2.imread(img_path)
                        if img is not None:
                            thumb = cv2.resize(img, (150, 150), interpolation=cv2.INTER_AREA)
                            _, buffer = cv2.imencode('.jpg', thumb, [cv2.IMWRITE_JPEG_QUALITY, 80])
                            encoded = base64.b64encode(buffer).decode('utf-8')
                            
                            if len(self.thumbnail_cache) > 1000:
                                self.thumbnail_cache.pop(next(iter(self.thumbnail_cache)))
                            
                            self.thumbnail_cache[img_path] = encoded
                        else:
                            continue

                    images_data.append({
                        "filename": img_name, 
                        "base64": f"data:image/jpeg;base64,{encoded}"
                    })
                except Exception:
                    pass
                    
        return {"status": "success", "images": images_data}

    def get_augmented_gestures_summary(self):
        # Non-blocking guard: if a previous poll is still computing, skip this call immediately
        # so PyWebView does not register two simultaneous return-value callbacks for the same
        # function, which causes the '...is not a function' JavascriptException.
        if not self._summary_lock.acquire(blocking=False):
            return {"status": "busy"}
        try:
            return self._get_augmented_gestures_summary_impl()
        finally:
            self._summary_lock.release()

    def _get_augmented_gestures_summary_impl(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        aug_dir = os.path.join(base_dir, 'Data', 'augumented_data')
        
        summary = []
        if os.path.exists(aug_dir):
            for folder_name in os.listdir(aug_dir):
                folder_path = os.path.join(aug_dir, folder_name)
                
                if os.path.isdir(folder_path):
                    files = [f for f in os.listdir(folder_path) if f.lower().endswith(('.jpg', '.png', '.jpeg'))]
                    if not files: 
                        continue
                        
                    count = len(files)
                    safe_files = []
                    for f in files:
                        try:
                            mtime = os.path.getmtime(os.path.join(folder_path, f))
                            safe_files.append((f, mtime))
                        except OSError:
                            pass
                            
                    safe_files.sort(key=lambda x: x[1], reverse=True)
                    thumbnail_encoded = ""
                    
                    if safe_files:
                        img_path = os.path.join(folder_path, safe_files[0][0])
                        
                        if img_path in self.thumbnail_cache:
                            thumbnail_encoded = self.thumbnail_cache[img_path]
                        else:
                            try:
                                img = cv2.imread(img_path)
                                if img is not None:
                                    thumb = cv2.resize(img, (200, 200), interpolation=cv2.INTER_AREA)
                                    _, buffer = cv2.imencode('.jpg', thumb, [cv2.IMWRITE_JPEG_QUALITY, 85])
                                    encoded = base64.b64encode(buffer).decode('utf-8')
                                    
                                    if len(self.thumbnail_cache) > 1000:
                                        self.thumbnail_cache.pop(next(iter(self.thumbnail_cache)))
                                    self.thumbnail_cache[img_path] = encoded
                                    thumbnail_encoded = encoded
                            except Exception:
                                pass
                                
                    if thumbnail_encoded:
                        summary.append({
                            "name": folder_name,
                            "count": count,
                            "thumbnail": f"data:image/jpeg;base64,{thumbnail_encoded}"
                        })
                        
        return {"status": "success", "gestures": summary}
    
    def delete_augmented_gesture(self, gesture_name):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        aug_dir = os.path.join(base_dir, 'Data', 'augumented_data', gesture_name)
        
        try:
            import shutil, stat
            def rmtree_onerror(func, path, exc_info):
                try:
                    os.chmod(path, stat.S_IWRITE)
                    func(path)
                except Exception:
                    pass
            
            deleted_anything = False
            
            if os.path.exists(aug_dir):
                shutil.rmtree(aug_dir, onerror=rmtree_onerror)
                deleted_anything = True
                
            if deleted_anything:
                keys_to_delete = [k for k in self.thumbnail_cache.keys() if f"\\{gesture_name}\\" in k or f"/{gesture_name}/" in k]
                for k in keys_to_delete:
                    self.thumbnail_cache.pop(k, None)
                    
                return {"status": "success", "message": f"Successfully deleted augmented data for '{gesture_name}'."}
            else:
                return {"status": "error", "message": "Augmented dataset not found."}
                
        except Exception as e:
            return {"status": "error", "message": f"Failed to delete: {str(e)}"}