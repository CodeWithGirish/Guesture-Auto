from backend.api.dashboard_api import DashboardAPI
from backend.api.gesture_api import GestureAutoAPI
from backend.api.integration_api import IntegrationAPI
from backend.services.camera_service import CameraService
from backend.api.action_mapping_api import ActionMappingAPI
from backend.api.training_api import TrainingAPI
import webview.window
from webview.errors import JavascriptException

# --- CRITICAL FIX: PyWebView Promise UID Navigation Race Condition ---
# When navigating between screens, the JS context is destroyed. If Python was
# processing a heavy API call (like generating thumbnails) and tries to return
# its value via _returnValuesCallbacks after the page has unloaded, PyWebView's
# internal thread crashes with an unhandled JavascriptException.
_original_evaluate_js = webview.window.Window.evaluate_js

def _safe_evaluate_js(self, script, *args, **kwargs):
    try:
        return _original_evaluate_js(self, script, *args, **kwargs)
    except JavascriptException as e:
        # If the failure is purely a return-value callback mapping that no longer exists
        if "_returnValuesCallbacks" in script:
            import logging
            logging.debug("PyWebView dropped an orphaned API return value harmlessly due to UI navigation.")
        else:
            raise e

# Apply the global patch to prevent Thread-N (_call) stack trace spam
webview.window.Window.evaluate_js = _safe_evaluate_js


class MasterAPI:
    """This class bundles all APIs together for the frontend."""
    def __init__(self):   

        # Resource Fix: Sharing the Singleton camera service across modules
        self.dashboard_api = DashboardAPI()
        self.camera_service = CameraService() 
        self.gesture_api = GestureAutoAPI()
        self.integration_api = IntegrationAPI()
        self.mapping_api = ActionMappingAPI()
        self.training_api = TrainingAPI()

    
    # ==========================================
    # DASHBOARD MODULE METHODS
    # ==========================================
    def get_dashboard_metrics(self):
        """Bridge to the Dashboard API."""
        return self.dashboard_api.get_dashboard_metrics()

    def search_items(self, category, query):
        """Routes search queries to the correct API module."""
        if category == "gestures":
            return self.gesture_api.search_items(category, query)
        elif category == "mappings":
            return self.mapping_api.search_mappings(query)
        
    # ==========================================
    # ACTION MAPPING MODULE METHODS
    # ==========================================
    def get_system_actions(self):
        return self.mapping_api.get_system_actions()

    def get_smart_sorted_gestures(self, search_term=""):
        return self.mapping_api.get_smart_sorted_gestures(search_term)

    def get_paginated_mappings(self, search_term="", status_filter="All", page=1, limit=4):
        return self.mapping_api.get_paginated_mappings(search_term, status_filter, page, limit)

    def toggle_mapping_status(self, gesture_name, target_app, is_active):
        return self.mapping_api.toggle_mapping_status(gesture_name, target_app, is_active)
    
    def save_mapping(self, mapping_data):
        """Bridge to the mapping API."""
        return self.mapping_api.save_mapping(mapping_data)

    def get_mappings(self):
        return self.mapping_api.get_mappings()

    def get_mouse_tracking_state(self):
        return self.mapping_api.get_mouse_tracking_state()

    def validate_index_finger_dataset(self):
        """Checks if any scanned image passes the index-only landmark test."""
        return self.mapping_api.validate_index_finger_dataset()

    def toggle_mouse_tracking(self, is_enabled):
        return self.mapping_api.toggle_mouse_tracking(is_enabled)

    # UPDATED: Add target_app argument here
    def delete_mapping(self, gesture_name, target_app="Global"):
        return self.mapping_api.delete_mapping(gesture_name, target_app)

    def get_app_specific_actions(self, app_name):
        return self.mapping_api.get_app_specific_actions(app_name)


    # ==========================================
    # INTEGRATION MODULE METHODS (Preserved)
    # ==========================================
    def scan_system_apps(self):
        return self.integration_api.scan_system_apps()

    def stage_app_connection(self, app_data):
        return self.integration_api.stage_app_connection(app_data)

    def unstage_app_connection(self, app_name):
        return self.integration_api.unstage_app_connection(app_name)

    def save_staged_integrations(self):
        return self.integration_api.save_staged_integrations()

    def clear_staged_integrations(self):
        return self.integration_api.clear_staged_integrations()

    def get_connected_apps(self, search_term=None):
        return self.integration_api.get_connected_apps(search_term)

    def disconnect_app(self, app_name):
        return self.integration_api.disconnect_app(app_name)

    # ==========================================
    # GESTURE MODULE METHODS (Fixing Bridge Flaws)
    # ==========================================
    def get_current_session(self):
        """Fixes TypeError: pywebview.api.get_current_session is not a function"""
        return self.gesture_api.get_current_session()

    def capture_image(self):
        """Bridges the manual image capture trigger"""
        return self.gesture_api.capture_image()

    def delete_images(self, temp_ids):
        """Fixes TypeError: pywebview.api.delete_images is not a function"""
        return self.gesture_api.delete_images(temp_ids)

    def edit_gesture(self, gesture_name):
        """Fixes TypeError: pywebview.api.edit_gesture is not a function"""
        return self.gesture_api.edit_gesture(gesture_name)

    def delete_gesture(self, gesture_name):
        """Fixes TypeError: pywebview.api.delete_gesture is not a function"""
        return self.gesture_api.delete_gesture(gesture_name)

    def get_gesture_images(self, gesture_name):
        """Fixes TypeError: pywebview.api.get_gesture_images is not a function"""
        return self.gesture_api.get_gesture_images(gesture_name)

    def delete_saved_images(self, gesture_name, filenames):
        """Fixes TypeError: pywebview.api.delete_saved_images is not a function"""
        return self.gesture_api.delete_saved_images(gesture_name, filenames)

    def start_scan(self):
        return self.gesture_api.start_scan()

    def start_automation(self):
        """Starts the full gesture recognition + automation pipeline via the gesture API."""
        return self.gesture_api.start_automation()

    def set_camera_index(self, index):
        """Allows the user to choose a camera device by index."""
        return self.gesture_api.set_camera_index(index)

    def stop_scan(self):
        return self.gesture_api.stop_scan()

    def get_saved_gestures(self):
        return self.gesture_api.get_saved_gestures()

    def save_session(self, gesture_name):
        return self.gesture_api.save_session(gesture_name)

    def start_motion_scan(self):
        return self.gesture_api.start_motion_scan()
        
    def save_motion_session(self, gesture_name):
        return self.gesture_api.save_motion_session(gesture_name)

    def shutdown(self):
        """Architectural Fix: Centralized cleanup for singleton resources."""
        self.gesture_api.stop_scan()
        self.camera_service.stop()

    # ==========================================
    # FLOATING WINDOW
    # ==========================================
    def toggle_float_window(self):
        """Bridge to toggle the floating camera preview window."""
        return self.gesture_api.toggle_float_window()

#########################################
    # Augumentation Logic
    #########################################

    def get_batch_progress(self):
        """Bridge to fetch real-time batch processing progress."""
        return self.gesture_api.get_batch_progress()
    
    def get_augmentation_params(self):
        """Bridge for JS to retrieve saved settings on load."""
        return self.gesture_api.get_augmentation_params()

    def save_augmentation_params(self, params):
        """Bridge to save parameters from frontend sliders."""
        return self.gesture_api.save_augmentation_params(params)

    def get_gesture_summary(self, gesture_name):
        """Bridge to fetch gesture image count."""
        return self.gesture_api.get_gesture_summary(gesture_name)

    def start_augmentation_batch(self, gesture_name, target_count, use_params=True):
        """Bridge to start batch processing."""
        return self.gesture_api.start_augmentation_batch(gesture_name, target_count, use_params)
    
    def abort_augmentation_batch(self):
        """Bridge to stop batch processing and trigger cleanup."""
        return self.gesture_api.abort_augmentation_batch()
    
    def get_augmentation_kpis(self):
        return self.gesture_api.get_augmentation_kpis()
    
    def get_augmented_images(self, gesture_name, limit=200):
        """Bridge to fetch recent augmented images for the live stream."""
        return self.gesture_api.get_augmented_images(gesture_name, int(limit))

    #####################################
    # Preview Gallary
    #####################################

    def get_augmented_gestures_summary(self):
            """Bridge to fetch augmented dataset summary for the Preview Gallery."""
            return self.gesture_api.get_augmented_gestures_summary()
    
    def delete_augmented_gesture(self, gesture_name):
        """Bridge to completely delete an augmented dataset."""
        return self.gesture_api.delete_augmented_gesture(gesture_name)
    
    # ==========================================
    # TRAINING MODULE METHODS
    # ==========================================
    def get_training_init_data(self):
        return self.training_api.get_training_init_data()

    def save_training_config(self, config):
        return self.training_api.save_training_config(config)

    def start_model_training(self):
        return self.training_api.start_model_training()
        
    def stop_model_training(self):
        return self.training_api.stop_model_training()